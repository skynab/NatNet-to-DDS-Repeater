#!/usr/bin/env python3
"""Minimal NatNet 4.5 server that simulates Motive, for testing the
NatNet -> DDS bridge without a camera system.

It answers the NatNet handshake (connect / server info), model definition
requests and commands, and streams synthetic frames containing:

  * rigid bodies   1 "Wand"   (circle), 2 "Drone" (figure eight),
                   3 "Flicker" (loses tracking every 50th frame)
  * skeleton       1 "Actor"  with bones Hip, Spine, Head
  * labeled markers on the Wand, plus a "Wand" marker set

Every value is a pure function of the frame number (expected_* functions
below), so DDSTestClient.py --verify-mock can check that what arrives over
DDS is bit-for-bit what was sent over NatNet.

Examples
    python MockNatNetServer.py                 # multicast (Motive default), 120 Hz
    python MockNatNetServer.py --unicast --fps 240
"""
import argparse
import math
import socket
import struct
import threading
import time

NAT_CONNECT = 0
NAT_SERVERINFO = 1
NAT_REQUEST = 2
NAT_RESPONSE = 3
NAT_REQUEST_MODELDEF = 4
NAT_MODELDEF = 5
NAT_FRAMEOFDATA = 7
NAT_KEEPALIVE = 10

NATNET_VERSION = (4, 5, 0, 0)
SERVER_VERSION = (3, 2, 0, 0)
APP_NAME = b"MockNatNetServer"

RIGID_BODIES = {1: "Wand", 2: "Drone", 3: "Flicker"}
SKELETON_ID, SKELETON_NAME = 1, "Actor"
BONES = {1: ("Hip", 0), 2: ("Spine", 1), 3: ("Head", 2)}       # id: (name, parent)
WAND_MARKER_OFFSETS = [(0.0, 0.05, 0.0), (0.03, 0.0, 0.0), (-0.03, 0.0, 0.0)]
DEFAULT_FPS = 120.0


# ---------------------------------------------------------------------------
# Deterministic scene (shared with DDSTestClient.py --verify-mock)
# ---------------------------------------------------------------------------

def _yaw_quat(angle):
    """Quaternion (x, y, z, w) for a rotation of `angle` radians about +Y."""
    return (0.0, math.sin(angle / 2.0), 0.0, math.cos(angle / 2.0))


def _f32(values):
    """Round to float32, as NatNet transmits them."""
    return tuple(struct.unpack("<%df" % len(values), struct.pack("<%df" % len(values), *values)))


def expected_rigid_body(rb_id, frame, fps=DEFAULT_FPS):
    """Return (position, orientation, mean_error, tracking_valid) as float32 tuples."""
    t = frame / fps
    if rb_id == 1:
        pos = (math.cos(t), 1.0, math.sin(t))
        rot = _yaw_quat(t)
    elif rb_id == 2:
        pos = (0.5 * math.sin(2 * t), 1.5 + 0.1 * math.sin(t), 0.5 * math.sin(t))
        rot = _yaw_quat(-t)
    else:
        pos = (0.0, 0.25, -1.0)
        rot = (0.0, 0.0, 0.0, 1.0)
    valid = not (rb_id == 3 and frame % 50 == 0)
    return _f32(pos), _f32(rot), _f32((0.0002 * rb_id,))[0], valid


def expected_bone(bone_id, frame, fps=DEFAULT_FPS):
    t = frame / fps
    pos = (0.0, 0.9 + 0.3 * (bone_id - 1), 0.02 * math.sin(t * bone_id))
    return _f32(pos), _f32(_yaw_quat(0.1 * t * bone_id))


def expected_wand_markers(frame, fps=DEFAULT_FPS):
    (px, py, pz), _, _, _ = expected_rigid_body(1, frame, fps)
    return [_f32((px + ox, py + oy, pz + oz)) for ox, oy, oz in WAND_MARKER_OFFSETS]


# ---------------------------------------------------------------------------
# NatNet 4.5 packet encoding (matches natnet_sdk/NatNetClient.py decoding)
# ---------------------------------------------------------------------------

def _cstr(s):
    return s.encode("utf-8") + b"\0"


def _packet(message_id, payload):
    return struct.pack("<HH", message_id, len(payload)) + payload


def _section(count, body):
    """NatNet 4.1+ section: item count, byte count, items."""
    return struct.pack("<ii", count, len(body)) + body


def _rigid_body(rb_id, pos, rot, error, valid):
    return struct.pack("<i3f4ffh", rb_id, *pos, *rot, error, 1 if valid else 0)


def encode_frame(frame, fps):
    out = struct.pack("<i", frame)

    # Marker sets
    markers = expected_wand_markers(frame, fps)
    ms = _cstr("Wand") + struct.pack("<i", len(markers)) + b"".join(struct.pack("<3f", *m) for m in markers)
    out += _section(1, ms)

    # Legacy "other" (unlabeled) markers
    out += _section(0, b"")

    # Rigid bodies
    rbs = b"".join(_rigid_body(rb_id, *expected_rigid_body(rb_id, frame, fps)) for rb_id in RIGID_BODIES)
    out += _section(len(RIGID_BODIES), rbs)

    # Skeletons: bone ids are (skeleton id << 16) | bone id
    bones = b"".join(_rigid_body((SKELETON_ID << 16) | b, *expected_bone(b, frame, fps), 0.0, True)
                     for b in BONES)
    out += _section(1, struct.pack("<ii", SKELETON_ID, len(BONES)) + bones)

    # Assets (4.1+)
    out += _section(0, b"")

    # Labeled markers: id = (model id << 16) | marker id
    lms = b"".join(struct.pack("<i3ffhf", (1 << 16) | (i + 1), *m, 0.014, 0x04, 0.0003)
                   for i, m in enumerate(markers))
    out += _section(len(markers), lms)

    # Force plates, devices, IMUs (4.5+), GPIO (4.5+)
    out += _section(0, b"") * 4

    # Frame suffix (4.5): timecode, subframe, timestamp, 3 hi-res stamps,
    # precision timestamp secs/fraction, params
    timestamp = frame / fps
    ticks = int(timestamp * 1e7)
    out += struct.pack("<iidqqqiih", 0, 0, timestamp, ticks, ticks + 5000, ticks + 9000,
                       int(timestamp), 0, 0)
    return _packet(NAT_FRAMEOFDATA, out)


def _rigid_body_description(name, rb_id, parent_id):
    return (_cstr(name) + struct.pack("<ii3f4fi", rb_id, parent_id, 0, 0, 0, 0, 0, 0, 1, 0))


def encode_model_def():
    datasets = []
    # type 0: marker set
    datasets.append((0, _cstr("Wand") + struct.pack("<i", 3) + b"".join(_cstr("Marker%d" % i) for i in (1, 2, 3))))
    # type 1: rigid bodies
    for rb_id, name in RIGID_BODIES.items():
        datasets.append((1, _rigid_body_description(name, rb_id, -1)))
    # type 2: skeleton
    sk = _cstr(SKELETON_NAME) + struct.pack("<ii", SKELETON_ID, len(BONES))
    sk += b"".join(_rigid_body_description(name, bone_id, parent) for bone_id, (name, parent) in BONES.items())
    datasets.append((2, sk))

    payload = struct.pack("<i", len(datasets))
    for data_type, body in datasets:
        payload += struct.pack("<ii", data_type, len(body)) + body
    return _packet(NAT_MODELDEF, payload)


def encode_server_info(multicast_group, data_port):
    payload = APP_NAME.ljust(256, b"\0")
    payload += bytes(SERVER_VERSION) + bytes(NATNET_VERSION)
    # C++ SDK extras (ignored by the Python client): hi-res clock frequency,
    # data port, multicast flag, multicast group.
    payload += struct.pack("<QH?", 10_000_000, data_port, True) + socket.inet_aton(multicast_group)
    return _packet(NAT_SERVERINFO, payload)


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

class MockNatNetServer:
    def __init__(self, bind, command_port, data_port, multicast_group, multicast_if, fps, drop_every=0):
        """multicast_group=None streams unicast to each connected client instead.
        drop_every=N skips sending every Nth frame to simulate packet loss."""
        self.fps = fps
        self.drop_every = drop_every
        self.data_port = data_port
        self.multicast_group = multicast_group
        self.unicast_clients = set()
        self.lock = threading.Lock()
        self.running = True

        self.cmd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.cmd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.cmd.bind((bind, command_port))
        self.cmd.settimeout(0.5)

        self.mcast = None
        if multicast_group:
            self.mcast = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.mcast.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            self.mcast.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            self.mcast.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(multicast_if))

    def command_loop(self):
        while self.running:
            try:
                data, addr = self.cmd.recvfrom(65536)
            except socket.timeout:
                continue
            except OSError:
                break
            if len(data) < 4:
                continue
            message_id = struct.unpack_from("<H", data)[0]
            if message_id == NAT_CONNECT:
                print("[mock] client connected from %s:%d" % addr)
                if not self.mcast:
                    with self.lock:
                        self.unicast_clients.add(addr)
                self.cmd.sendto(encode_server_info(self.multicast_group or "0.0.0.0", self.data_port), addr)
            elif message_id == NAT_REQUEST_MODELDEF:
                print("[mock] model definitions requested by %s:%d" % addr)
                self.cmd.sendto(encode_model_def(), addr)
            elif message_id == NAT_REQUEST:
                command = data[4:].split(b"\0", 1)[0].decode("utf-8", "replace")
                if command == "Bitstream":
                    reply = _cstr("Bitstream,%d.%d" % NATNET_VERSION[:2])
                else:
                    reply = struct.pack("<i", 0)
                self.cmd.sendto(_packet(NAT_RESPONSE, reply), addr)
            elif message_id == NAT_KEEPALIVE:
                pass

    def stream_loop(self):
        frame = 0
        period = 1.0 / self.fps
        next_t = time.monotonic()
        last_report = next_t
        while self.running:
            packet = encode_frame(frame, self.fps)
            with self.lock:
                clients = list(self.unicast_clients)
            if self.drop_every and frame % self.drop_every == self.drop_every - 1:
                clients, packet = [], None   # simulated packet loss
            for addr in clients:
                try:
                    self.cmd.sendto(packet, addr)
                except OSError:
                    with self.lock:
                        self.unicast_clients.discard(addr)
            if self.mcast and packet:
                self.mcast.sendto(packet, (self.multicast_group, self.data_port))
            frame += 1
            next_t += period
            now = time.monotonic()
            if now - last_report >= 5.0:
                print("[mock] streaming frame %d (%d unicast clients)" % (frame, len(clients)))
                last_report = now
            time.sleep(max(0.0, next_t - now))

    def run(self):
        threading.Thread(target=self.command_loop, daemon=True).start()
        try:
            self.stream_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            self.cmd.close()
            if self.mcast:
                self.mcast.close()


def main():
    p = argparse.ArgumentParser(description="Simulated Motive NatNet 4.5 server for testing.")
    p.add_argument("--bind", default="127.0.0.1", help="address to bind the command port on")
    p.add_argument("--command-port", type=int, default=1510)
    p.add_argument("--data-port", type=int, default=1511)
    p.add_argument("--unicast", action="store_true",
                   help="stream unicast to connected clients instead of multicast")
    p.add_argument("--multicast-group", default="239.255.42.99")
    p.add_argument("--multicast-interface", default="127.0.0.1", help="interface to send multicast on")
    p.add_argument("--fps", type=float, default=DEFAULT_FPS)
    p.add_argument("--drop-every", type=int, default=0, metavar="N",
                   help="don't send every Nth frame, to test packet loss reporting (default 0 = off)")
    args = p.parse_args()

    group = None if args.unicast else args.multicast_group
    print("[mock] NatNet %d.%d server on %s:%d, %.0f fps, %s" % (
        NATNET_VERSION[0], NATNET_VERSION[1], args.bind, args.command_port, args.fps,
        "multicast %s:%d" % (group, args.data_port) if group else "unicast"))
    MockNatNetServer(args.bind, args.command_port, args.data_port, group,
                     args.multicast_interface, args.fps, args.drop_every).run()


if __name__ == "__main__":
    main()
