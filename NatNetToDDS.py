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

    Everything else (sockets, handshake, version negotiation, unpacking) is
    the unmodified SDK code.
    """

    def __init__(self):
        super().__init__()
        self.data_descriptions_listener = None

    # Overrides NatNetClient.__process_message (name-mangled private method).
    def _NatNetClient__process_message(self, data, print_level=0):
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

    def request_data_descriptions(self):
        self.send_request(self.command_socket, self.NAT_REQUEST_MODELDEF, "",
                          (self.server_ip_address, self.command_port))

    def send_connect(self):
        """Re-send the NatNet connect request (run() sends it once)."""
        self.send_request(self.command_socket, self.NAT_CONNECT, "",
                          (self.server_ip_address, self.command_port))


class NatNetToDDSBridge:
    """Converts SDK MoCapData frames to DDS samples and writes them."""

    def __init__(self, backend, publish_frames=True, publish_rigid_bodies=True, reliable=False):
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

    def on_frame(self, data_dict):
        try:
            self._publish(data_dict["mocap_data"])
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

    def _publish(self, mocap):
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
                marker_sets=marker_sets))

        if self.rigid_body_writer:
            for p in rigid_bodies:
                self.rigid_body_writer.write(T.RigidBody(
                    id=p.id, name=p.name, frame_number=frame_number,
                    timestamp=float(suffix.timestamp), position=p.position,
                    orientation=p.orientation, mean_error=p.mean_error,
                    tracking_valid=p.tracking_valid))

        self.frames_published += 1
        self.last_frame_number = frame_number
        self.last_frame_time = time.monotonic()
        self.latest_rigid_bodies = rigid_bodies
        if suffix.tracked_models_changed and self.on_models_changed:
            self.on_models_changed()


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
    client.new_frame_with_data_listener = bridge.on_frame
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
    p.add_argument("--duration", type=float, default=0, help="exit after N seconds (0 = run until Ctrl+C)")
    return p.parse_args()


def main():
    args = parse_args()

    backend = create_backend(args.dds, args.domain)
    print("[dds] using %s, domain %d, topics: %s%s" % (
        backend.name, args.domain,
        "" if args.no_frames else FRAME_TOPIC + " ",
        "" if args.no_rigid_bodies else RIGID_BODY_TOPIC))
    bridge = NatNetToDDSBridge(backend, publish_frames=not args.no_frames,
                               publish_rigid_bodies=not args.no_rigid_bodies,
                               reliable=args.reliable)

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
    last_count, last_t = bridge.frames_published, start
    try:
        while args.duration <= 0 or time.monotonic() - start < args.duration:
            time.sleep(1.0)
            now = time.monotonic()
            count = bridge.frames_published
            subs = []
            if bridge.frame_writer:
                subs.append("frame subs %d" % bridge.frame_writer.matched_count())
            if bridge.rigid_body_writer:
                subs.append("rigid body subs %d" % bridge.rigid_body_writer.matched_count())
            print("[bridge] frame %s  %.1f fps  published %d  %s%s" % (
                bridge.last_frame_number, (count - last_count) / (now - last_t), count,
                ", ".join(subs),
                ("  last error: " + bridge.last_error) if bridge.last_error else ""))
            last_count, last_t = count, now
    except KeyboardInterrupt:
        pass
    finally:
        print("[bridge] shutting down")
        client.shutdown()
        backend.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
