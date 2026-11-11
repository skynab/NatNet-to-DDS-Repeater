#!/usr/bin/env python3
"""NatNet -> DDS bridge.

Receives motion capture data from Motive (or any NatNet server) using the
NatNet SDK's Python client (natnet_sdk/NatNetClient.py, unmodified from the
SDK's Samples/PythonClient) and republishes every frame on DDS:

  Topic "NatNet_FrameOfMocapData"  type NatNet::FrameOfMocapData
      One sample per mocap frame: rigid bodies, skeletons, labeled markers,
      marker sets and frame timing.

  Topic "NatNet_RigidBody"         type NatNet::RigidBody   (keyed by id)
      One sample per rigid body per frame. Each rigid body is its own DDS
      instance, so subscribers can filter/track bodies individually.

Types are defined in idl/NatNetDDS.idl. Works with RTI Connext DDS, or with
Eclipse Cyclone DDS when no RTI license is available (see --dds).

Examples
    # Motive on this machine, multicast (Motive default)
    python NatNetToDDS.py

    # Motive on another machine, unicast
    python NatNetToDDS.py --server 192.168.1.10 --client 192.168.1.20 --unicast

    # DDS domain 5, force RTI Connext
    python NatNetToDDS.py --domain 5 --dds rti
"""
import argparse
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "natnet_sdk"))

from NatNetClient import NatNetClient  # noqa: E402  (NatNet SDK sample client)

from natnet_dds import FRAME_TOPIC, RIGID_BODY_TOPIC, create_backend  # noqa: E402
from natnet_dds.metrics import DEFAULT_WINDOW_S, StreamStats, fmt, format_utc_ns  # noqa: E402


def _to_str(value):
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return str(value) if value is not None else ""


class BridgeNatNetClient(NatNetClient):
    """The SDK's NatNetClient with two small hooks added by subclassing:

    * data_descriptions_listener(DataDescriptions) is called whenever Motive
      sends model definitions, so we can attach names to rigid bodies and
      skeletons. (The stock client only prints them.)
    * Frames are decoded without the stock client's per-frame console
      print, which would otherwise throttle high frame-rate streams.
    * The arrival time of each packet is recorded (packet_received_ns) and
      the server's high-resolution clock frequency, which the stock client
      skips, is read from the server info (clock_frequency).

    Everything else (sockets, handshake, version negotiation, unpacking) is
    the unmodified SDK code.
    """

    def __init__(self):
        super().__init__()
        self.data_descriptions_listener = None
        self.packet_received_ns = None   # wall clock (ns since UNIX epoch) of the packet being processed
        self.clock_frequency = None      # Motive's high-res clock ticks per second

    # Overrides NatNetClient.__process_message (name-mangled private method).
    # It runs on the SDK's receive thread right after recvfrom().
    def _NatNetClient__process_message(self, data, print_level=0):
        self.packet_received_ns = time.time_ns()
        message_id = int.from_bytes(data[0:2], byteorder="little", signed=True)
        packet_size = int.from_bytes(data[2:4], byteorder="little", signed=True)
        major, minor = self.get_major(), self.get_minor()

        if message_id == self.NAT_FRAMEOFDATA:
            # Invokes new_frame_with_data_listener with the decoded MoCapData.
            self._NatNetClient__unpack_mocap_data(data[4:], packet_size, major, minor)
            return message_id

        if message_id == self.NAT_MODELDEF:
            result = self._NatNetClient__unpack_data_descriptions(data[4:], packet_size, major, minor)
            # The SDK returns just an offset (not a tuple) on decode errors.
            if isinstance(result, tuple) and self.data_descriptions_listener:
                self.data_descriptions_listener(result[1])
            return message_id

        return super()._NatNetClient__process_message(data, print_level)

    # Overrides NatNetClient.__unpack_server_info to also read the
    # high-resolution clock frequency that follows the version numbers
    # (sSender_Server: name[256], version[4], NatNet version[4], uint64 freq).
    def _NatNetClient__unpack_server_info(self, data, packet_size, major, minor):
        offset = super()._NatNetClient__unpack_server_info(data, packet_size, major, minor)
        if len(data) >= 272:
            freq = int.from_bytes(bytes(data[264:272]), byteorder="little", signed=False)
            if freq > 0:
                self.clock_frequency = freq
        return offset

    def request_data_descriptions(self):
        self.send_request(self.command_socket, self.NAT_REQUEST_MODELDEF, "",
                          (self.server_ip_address, self.command_port))

    def send_connect(self):
        """Re-send the NatNet connect request (run() sends it once)."""
        self.send_request(self.command_socket, self.NAT_CONNECT, "",
                          (self.server_ip_address, self.command_port))


class NatNetToDDSBridge:
    """Converts SDK MoCapData frames to DDS samples and writes them."""

    def __init__(self, backend, publish_frames=True, publish_rigid_bodies=True, reliable=False,
                 stats_window_s=DEFAULT_WINDOW_S):
        self.types = backend.types
        self.frame_writer = (backend.create_writer(FRAME_TOPIC, self.types.FrameOfMocapData, reliable)
                             if publish_frames else None)
        self.rigid_body_writer = (backend.create_writer(RIGID_BODY_TOPIC, self.types.RigidBody, reliable)
                                  if publish_rigid_bodies else None)

        # Names from Motive data descriptions
        self.rigid_body_names = {}      # rigid body id -> name
        self.skeleton_names = {}        # skeleton id -> name
        self.bone_names = {}            # (skeleton id, bone id) -> name
        self.descriptions_received = threading.Event()
        self.on_models_changed = None   # callback to re-request descriptions

        self.frames_published = 0
        self.last_frame_number = None
        self.last_frame_time = None     # time.monotonic() of the last published frame
        self.latest_rigid_bodies = []   # RigidBodyPose list from the last frame
        self.last_error = None

        # Metrics on the NatNet input: rate, frame-number gaps (UDP packets
        # lost between Motive and the bridge) and Motive's own latency.
        self.stats = StreamStats(stats_window_s)
        # Time from receiving the NatNet packet to finishing the DDS writes.
        self.processing_stats = StreamStats(stats_window_s)
        self.last_source = None         # SourceTimes of the last frame

    # -- NatNet callbacks ------------------------------------------------

    def on_data_descriptions(self, descs):
        self.rigid_body_names = {rb.id_num: _to_str(rb.sz_name) for rb in descs.rigid_body_list}
        self.skeleton_names = {sk.id_num: _to_str(sk.name) for sk in descs.skeleton_list}
        self.bone_names = {(sk.id_num, bone.id_num & 0xFFFF): _to_str(bone.sz_name)
                           for sk in descs.skeleton_list
                           for bone in sk.rigid_body_description_list}
        print("[natnet] data descriptions: %d rigid bodies, %d skeletons, %d marker sets"
              % (len(descs.rigid_body_list), len(descs.skeleton_list), len(descs.marker_set_list)))
        for rb_id, name in sorted(self.rigid_body_names.items()):
            print("           rigid body %3d  %s" % (rb_id, name))
        for sk_id, name in sorted(self.skeleton_names.items()):
            print("           skeleton   %3d  %s" % (sk_id, name))
        self.descriptions_received.set()

    def on_frame(self, data_dict, received_ns=None, clock_frequency=None):
        """received_ns: wall clock time the NatNet packet arrived (ns since
        the UNIX epoch). It becomes the DDS source timestamp of every sample
        made from this frame. clock_frequency: Motive's high-res clock ticks
        per second, used to turn its hardware stamps into a latency."""
        try:
            self._publish(data_dict["mocap_data"], received_ns or time.time_ns(), clock_frequency)
        except Exception as e:  # never let an exception kill the NatNet thread
            self.last_error = repr(e)

    # -- conversion ------------------------------------------------------

    def _pose(self, rb, name):
        T = self.types
        return T.RigidBodyPose(
            id=rb.id_num,
            name=name,
            position=T.Vector3(*rb.pos),
            orientation=T.Quaternion(*rb.rot),
            mean_error=rb.error,
            tracking_valid=bool(rb.tracking_valid))

    def _publish(self, mocap, received_ns, clock_frequency):
        T = self.types
        suffix = mocap.suffix_data
        frame_number = mocap.prefix_data.frame_number

        rigid_bodies = [self._pose(rb, self.rigid_body_names.get(rb.id_num, ""))
                        for rb in mocap.rigid_body_data.rigid_body_list]

        skeletons = []
        for sk in mocap.skeleton_data.skeleton_list:
            bones = []
            for bone in sk.rigid_body_list:
                # NatNet 3+ encodes bone ids as (skeleton id << 16) | bone id
                bone_id = bone.id_num & 0xFFFF
                bones.append(self._pose(bone, self.bone_names.get((sk.id_num, bone_id), "")))
            skeletons.append(T.Skeleton(id=sk.id_num, name=self.skeleton_names.get(sk.id_num, ""),
                                        bones=bones))

        labeled_markers = [
            T.LabeledMarker(id=m.id_num, model_id=m.id_num >> 16, marker_id=m.id_num & 0xFFFF,
                            position=T.Vector3(*m.pos), size=m.size,
                            occluded=bool(m.param & 0x01), residual=m.residual)
            for m in mocap.labeled_marker_data.labeled_marker_list]

        marker_sets = [T.MarkerSet(name=_to_str(ms.model_name),
                                   markers=[T.Vector3(*p) for p in ms.marker_pos_list])
                       for ms in mocap.marker_set_data.marker_data_list]

        source = SourceTimes(suffix, received_ns, clock_frequency)
        self.stats.record(frame_number, source_time_s=float(suffix.timestamp),
                          latency_s=source.motive_latency_s)

        if self.frame_writer:
            self.frame_writer.write(T.FrameOfMocapData(
                frame_number=frame_number,
                timestamp=float(suffix.timestamp),
                timecode=suffix.timecode & 0xFFFFFFFF,
                timecode_sub=suffix.timecode_sub & 0xFFFFFFFF,
                stamp_camera_mid_exposure=suffix.stamp_camera_mid_exposure,
                stamp_data_received=suffix.stamp_data_received,
                stamp_transmit=suffix.stamp_transmit,
                is_recording=bool(suffix.is_recording),
                tracked_models_changed=bool(suffix.tracked_models_changed),
                rigid_bodies=rigid_bodies,
                skeletons=skeletons,
                labeled_markers=labeled_markers,
                marker_sets=marker_sets), received_ns)

        if self.rigid_body_writer:
            for p in rigid_bodies:
                self.rigid_body_writer.write(T.RigidBody(
                    id=p.id, name=p.name, frame_number=frame_number,
                    timestamp=float(suffix.timestamp), position=p.position,
                    orientation=p.orientation, mean_error=p.mean_error,
                    tracking_valid=p.tracking_valid), received_ns)

        self.processing_stats.record(frame_number, latency_s=(time.time_ns() - received_ns) / 1e9)
        self.frames_published += 1
        self.last_frame_number = frame_number
        self.last_frame_time = time.monotonic()
        self.latest_rigid_bodies = rigid_bodies
        self.last_source = source
        if suffix.tracked_models_changed and self.on_models_changed:
            self.on_models_changed()


class SourceTimes:
    """Timestamps of one frame: Motive's, and when the bridge received it."""

    def __init__(self, suffix, received_ns, clock_frequency):
        self.motive_timestamp = float(suffix.timestamp)     # seconds since Motive started
        self.mid_exposure = suffix.stamp_camera_mid_exposure  # Motive high-res clock ticks
        self.data_received = suffix.stamp_data_received
        self.transmit = suffix.stamp_transmit
        self.received_ns = received_ns                      # bridge wall clock = DDS source timestamp
        self.clock_frequency = clock_frequency
        # Motive's latency from the middle of the camera exposure until the
        # frame was sent. Needs the clock frequency and live (non-zero) stamps.
        self.motive_latency_s = None
        if clock_frequency and self.mid_exposure > 0 and self.transmit >= self.mid_exposure:
            self.motive_latency_s = (self.transmit - self.mid_exposure) / clock_frequency


def create_natnet_client(bridge, server="127.0.0.1", client_address="127.0.0.1", multicast=True,
                         multicast_address="239.255.42.99", command_port=1510, data_port=1511):
    """Create a BridgeNatNetClient wired to `bridge` (not started yet).

    Returns (client, request_descriptions), where request_descriptions()
    asks the server for model definitions at most once per second.
    """
    client = BridgeNatNetClient()
    client.set_print_level(0)
    client.set_client_address(client_address)
    client.set_server_address(server)
    client.set_use_multicast(multicast)
    client.multicast_address = multicast_address
    client.command_port = command_port
    client.data_port = data_port
    client.new_frame_with_data_listener = lambda data: bridge.on_frame(
        data, client.packet_received_ns, client.clock_frequency)
    client.data_descriptions_listener = bridge.on_data_descriptions

    # Re-request names when Motive reports the tracked models changed,
    # at most once per second.
    last_request = [0.0]

    def request_descriptions():
        now = time.monotonic()
        if now - last_request[0] > 1.0:
            last_request[0] = now
            client.request_data_descriptions()
    bridge.on_models_changed = request_descriptions
    return client, request_descriptions


def parse_args():
    p = argparse.ArgumentParser(description="Republish OptiTrack NatNet data on DDS.")
    p.add_argument("--server", default="127.0.0.1", help="NatNet server (Motive) IP address")
    p.add_argument("--client", default="127.0.0.1", help="local IP address of the interface facing Motive")
    cast = p.add_mutually_exclusive_group()
    cast.add_argument("--multicast", dest="multicast", action="store_true", default=True,
                      help="receive NatNet via multicast (default, Motive default)")
    cast.add_argument("--unicast", dest="multicast", action="store_false",
                      help="receive NatNet via unicast")
    p.add_argument("--multicast-address", default="239.255.42.99", help="NatNet multicast group")
    p.add_argument("--command-port", type=int, default=1510)
    p.add_argument("--data-port", type=int, default=1511)
    p.add_argument("--domain", type=int, default=0, help="DDS domain id")
    p.add_argument("--dds", default="auto", choices=["auto", "rti", "cyclone"],
                   help="DDS implementation (auto: RTI Connext, else Cyclone DDS)")
    p.add_argument("--reliable", action="store_true",
                   help="use RELIABLE writers (default BEST_EFFORT, typical for streaming sensor data)")
    p.add_argument("--no-frames", action="store_true", help=f"don't publish {FRAME_TOPIC}")
    p.add_argument("--no-rigid-bodies", action="store_true", help=f"don't publish {RIGID_BODY_TOPIC}")
    p.add_argument("--stats-window", type=float, default=DEFAULT_WINDOW_S,
                   help="seconds of history used for rate, jitter and packet loss (default %(default)s)")
    p.add_argument("--duration", type=float, default=0, help="exit after N seconds (0 = run until Ctrl+C)")
    return p.parse_args()


def format_metrics(st, proc):
    """One line of input metrics for the console."""
    return ("rate %s Hz (source %s Hz)  interval %s ms ±%s, max %s  "
            "missed %d in last %gs (%.2f%%), %d total  Motive latency avg %s / max %s ms  "
            "bridge processing avg %s / max %s ms" % (
                fmt(st.rate_hz), fmt(st.source_rate_hz), fmt(st.interval_mean_ms, "%.2f"),
                fmt(st.interval_std_ms, "%.2f"), fmt(st.interval_max_ms, "%.2f"),
                st.missed_window, st.window_s, st.loss_percent_window, st.missed_total,
                fmt(st.latency_mean_ms, "%.2f"), fmt(st.latency_max_ms, "%.2f"),
                fmt(proc.latency_mean_ms, "%.2f"), fmt(proc.latency_max_ms, "%.2f")))


def format_source_times(src):
    return ("source: Motive t=%.4f s  mid-exposure %d  transmit %d ticks%s  received %s" % (
        src.motive_timestamp, src.mid_exposure, src.transmit,
        " @ %d Hz" % src.clock_frequency if src.clock_frequency else "",
        format_utc_ns(src.received_ns)))


def main():
    args = parse_args()

    backend = create_backend(args.dds, args.domain)
    print("[dds] using %s, domain %d, topics: %s%s" % (
        backend.name, args.domain,
        "" if args.no_frames else FRAME_TOPIC + " ",
        "" if args.no_rigid_bodies else RIGID_BODY_TOPIC))
    bridge = NatNetToDDSBridge(backend, publish_frames=not args.no_frames,
                               publish_rigid_bodies=not args.no_rigid_bodies,
                               reliable=args.reliable, stats_window_s=args.stats_window)

    client, request_descriptions = create_natnet_client(
        bridge, args.server, args.client, args.multicast, args.multicast_address,
        args.command_port, args.data_port)

    print("[natnet] connecting to %s from %s (%s)" % (
        args.server, args.client, "multicast " + args.multicast_address if args.multicast else "unicast"))
    if not client.run():
        print("ERROR: could not start NatNet client")
        return 1

    time.sleep(1)
    if not client.connected():
        print("ERROR: could not connect to the NatNet server. Check that Motive streaming is "
              "enabled and the server/client addresses and transport type match.")
        client.shutdown()
        return 2

    server_ver = client.get_server_version()
    nn_ver = client.get_nat_net_version_server()
    print("[natnet] connected to %s %d.%d.%d.%d (NatNet %d.%d)" % (
        client.get_application_name(), *server_ver, nn_ver[0], nn_ver[1]))
    request_descriptions()

    start = time.monotonic()
    try:
        while args.duration <= 0 or time.monotonic() - start < args.duration:
            time.sleep(1.0)
            subs = []
            if bridge.frame_writer:
                subs.append("frame subs %d" % bridge.frame_writer.matched_count())
            if bridge.rigid_body_writer:
                subs.append("rigid body subs %d" % bridge.rigid_body_writer.matched_count())
            st = bridge.stats.snapshot()
            print("[bridge] frame %s  published %d  %s%s" % (
                bridge.last_frame_number, bridge.frames_published, ", ".join(subs),
                ("  last error: " + bridge.last_error) if bridge.last_error else ""))
            print("         " + format_metrics(st, bridge.processing_stats.snapshot()))
            if bridge.last_source:
                print("         " + format_source_times(bridge.last_source))
    except KeyboardInterrupt:
        pass
    finally:
        st = bridge.stats.snapshot()
        print("[bridge] totals: %d frames received from NatNet, %d missed, %d out of order" % (
            st.received_total, st.missed_total, st.out_of_order_total))
        print("[bridge] shutting down")
        client.shutdown()
        backend.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
