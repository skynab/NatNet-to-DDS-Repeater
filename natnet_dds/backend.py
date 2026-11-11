"""Thin DDS abstraction so the bridge and test client run on either:

  * "rti"     - RTI Connext DDS (pip install rti.connext). Needs an RTI
                license file (RTI_LICENSE_FILE env var or rti_license.dat in
                the working directory); free evaluation licenses are
                available from https://www.rti.com/free-trial
  * "cyclone" - Eclipse Cyclone DDS (pip install cyclonedds). No license.
  * "auto"    - try RTI first, fall back to Cyclone if RTI is not installed
                or cannot create a DomainParticipant (e.g. no license).

Both speak the standard OMG DDS-RTPS wire protocol and use identical type
definitions (see idl/NatNetDDS.idl), so a bridge on one vendor can feed
subscribers on the other.
"""
import sys

FRAME_TOPIC = "NatNet_FrameOfMocapData"
RIGID_BODY_TOPIC = "NatNet_RigidBody"


class _RtiBackend:
    name = "rti"

    def __init__(self, domain_id, quiet=False):
        import rti.connextdds as dds
        from . import types_rti
        self._dds = dds
        self.types = types_rti
        logger = dds.Logger.instance
        saved_verbosity = logger.verbosity
        if quiet:  # "auto" probing: don't flood the console if RTI can't start
            logger.verbosity = dds.Verbosity.SILENT
        try:
            self.participant = dds.DomainParticipant(domain_id)
        finally:
            logger.verbosity = saved_verbosity
        self._topics = {}

    def _topic(self, topic_name, data_type):
        if topic_name not in self._topics:
            self._topics[topic_name] = self._dds.Topic(self.participant, topic_name, data_type)
        return self._topics[topic_name]

    def create_writer(self, topic_name, data_type, reliable=False):
        dds = self._dds
        qos = self.participant.implicit_publisher.default_datawriter_qos
        qos.reliability = dds.Reliability.reliable() if reliable else dds.Reliability.best_effort
        qos.history = dds.History.keep_last(1)
        return _RtiWriter(dds.DataWriter(self.participant.implicit_publisher,
                                         self._topic(topic_name, data_type), qos))

    def create_reader(self, topic_name, data_type, depth=64, reliable=False):
        dds = self._dds
        qos = self.participant.implicit_subscriber.default_datareader_qos
        qos.reliability = dds.Reliability.reliable() if reliable else dds.Reliability.best_effort
        qos.history = dds.History.keep_last(depth)
        return _RtiReader(dds.DataReader(self.participant.implicit_subscriber,
                                         self._topic(topic_name, data_type), qos))

    def close(self):
        self.participant.close()


class _RtiWriter:
    def __init__(self, writer):
        self._w = writer

    def write(self, sample):
        self._w.write(sample)

    def matched_count(self):
        return len(self._w.matched_subscriptions)


class _RtiReader:
    def __init__(self, reader):
        self._r = reader

    def take(self):
        return list(self._r.take_data())

    def matched_count(self):
        return len(self._r.matched_publications)


class _CycloneBackend:
    name = "cyclone"

    def __init__(self, domain_id):
        from cyclonedds.domain import DomainParticipant
        from . import types_cyclone
        self.types = types_cyclone
        self.participant = DomainParticipant(domain_id)
        self._topics = {}

    def _topic(self, topic_name, data_type):
        from cyclonedds.topic import Topic
        if topic_name not in self._topics:
            self._topics[topic_name] = Topic(self.participant, topic_name, data_type)
        return self._topics[topic_name]

    @staticmethod
    def _qos(reliable, depth):
        from cyclonedds.core import Policy, Qos
        from cyclonedds.util import duration
        rel = (Policy.Reliability.Reliable(duration(milliseconds=100)) if reliable
               else Policy.Reliability.BestEffort)
        return Qos(rel, Policy.History.KeepLast(depth))

    def create_writer(self, topic_name, data_type, reliable=False):
        from cyclonedds.pub import DataWriter
        return _CycloneWriter(DataWriter(self.participant, self._topic(topic_name, data_type),
                                         qos=self._qos(reliable, 1)))

    def create_reader(self, topic_name, data_type, depth=64, reliable=False):
        from cyclonedds.sub import DataReader
        return _CycloneReader(DataReader(self.participant, self._topic(topic_name, data_type),
                                         qos=self._qos(reliable, depth)), data_type)

    def close(self):
        # Cyclone entities are released when garbage collected.
        self._topics.clear()
        self.participant = None


class _CycloneWriter:
    def __init__(self, writer):
        self._w = writer

    def write(self, sample):
        self._w.write(sample)

    def matched_count(self):
        return len(self._w.get_matched_subscriptions())


class _CycloneReader:
    def __init__(self, reader, data_type):
        self._r = reader
        self._type = data_type

    def take(self):
        # take() can also return InvalidSample objects (e.g. disposes): skip them.
        return [s for s in self._r.take(N=256) if isinstance(s, self._type)]

    def matched_count(self):
        return len(self._r.get_matched_publications())


def create_backend(name="auto", domain_id=0):
    """Create a DDS backend by name ("auto", "rti" or "cyclone")."""
    name = name.lower()
    if name == "rti":
        return _RtiBackend(domain_id)
    if name == "cyclone":
        return _CycloneBackend(domain_id)
    if name != "auto":
        raise ValueError("unknown DDS backend %r (use auto, rti or cyclone)" % name)

    try:
        return _RtiBackend(domain_id, quiet=True)
    except ImportError:
        print("[dds] RTI Connext (rti.connext) not installed, using Cyclone DDS", file=sys.stderr)
    except Exception as e:  # noqa: BLE001 - most commonly a missing license
        print("[dds] RTI Connext unavailable (%s) - check RTI_LICENSE_FILE. "
              "Falling back to Cyclone DDS" % e, file=sys.stderr)
    return _CycloneBackend(domain_id)
