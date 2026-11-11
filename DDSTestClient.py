#!/usr/bin/env python3
"""DDS test client for the NatNet -> DDS bridge.

Subscribes to the bridge's topics, prints what arrives, and reports the
data rate, dropped frames (gaps in Motive frame numbers) over a rolling
window, and the source timestamps of the data:

  Topic "NatNet_FrameOfMocapData"  type NatNet::FrameOfMocapData
  Topic "NatNet_RigidBody"         type NatNet::RigidBody

With --verify-mock (when the bridge is fed by MockNatNetServer.py) every
received value is checked against the mock's known trajectories, so a pass
means the data made it NatNet -> bridge -> DDS -> here unchanged.

Latency is measured from the DDS source timestamp (set by the bridge to the
time it received the NatNet packet) to the time the sample is taken here. It
is only meaningful when both machines' clocks are synchronized (same machine,
or NTP/PTP).

Exit code is 0 if data was received (and verification passed), else 1,
so it can be used in automated tests with --duration.

Examples
    python DDSTestClient.py                       # watch live, Ctrl+C to stop
    python DDSTestClient.py --duration 10 --verify-mock
    python DDSTestClient.py --domain 5 --dds rti
"""
import argparse
import sys
import time

from natnet_dds import FRAME_TOPIC, RIGID_BODY_TOPIC, create_backend
from natnet_dds.metrics import DEFAULT_WINDOW_S, StreamStats, fmt, format_utc_ns


def _v3(v):
    return (v.x, v.y, v.z)


def _q(q):
    return (q.x, q.y, q.z, q.w)


def _close(a, b, tol=1e-6):
    return len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b))


class MockVerifier:
    """Checks samples against MockNatNetServer's deterministic scene."""

    def __init__(self, fps):
        import MockNatNetServer as mock
        self.mock = mock
        self.fps = fps
        self.checks = 0
        self.failures = []
        self.named_frames = 0   # frames where names (from data descriptions) were present

    def _check(self, ok, msg):
        self.checks += 1
        if not ok and len(self.failures) < 1000:
            self.failures.append(msg)

    def _check_pose(self, where, rb_id, frame, pos, rot, err, valid, name):
        m = self.mock
        exp_pos, exp_rot, exp_err, exp_valid = m.expected_rigid_body(rb_id, frame, self.fps)
        self._check(rb_id in m.RIGID_BODIES, "%s: unexpected rigid body id %d" % (where, rb_id))
        self._check(_close(pos, exp_pos), "%s rb %d frame %d: position %s != %s" % (where, rb_id, frame, pos, exp_pos))
        self._check(_close(rot, exp_rot), "%s rb %d frame %d: orientation %s != %s" % (where, rb_id, frame, rot, exp_rot))
        self._check(abs(err - exp_err) < 1e-9, "%s rb %d frame %d: mean_error %s != %s" % (where, rb_id, frame, err, exp_err))
        self._check(valid == exp_valid, "%s rb %d frame %d: tracking_valid %s != %s" % (where, rb_id, frame, valid, exp_valid))
        # Names arrive with the data descriptions, shortly after connecting.
        self._check(name in ("", m.RIGID_BODIES.get(rb_id)), "%s rb %d: name %r" % (where, rb_id, name))

    def frame(self, f):
        m, n = self.mock, f.frame_number
        self._check(abs(f.timestamp - n / self.fps) < 1e-9,
                    "frame %d: timestamp %r != %r" % (n, f.timestamp, n / self.fps))
        self._check(len(f.rigid_bodies) == len(m.RIGID_BODIES),
                    "frame %d: %d rigid bodies" % (n, len(f.rigid_bodies)))
        for rb in f.rigid_bodies:
            self._check_pose("frame", rb.id, n, _v3(rb.position), _q(rb.orientation),
                             rb.mean_error, rb.tracking_valid, rb.name)

        self._check(len(f.skeletons) == 1, "frame %d: %d skeletons" % (n, len(f.skeletons)))
        for sk in f.skeletons:
            self._check(sk.id == m.SKELETON_ID and sk.name in ("", m.SKELETON_NAME),
                        "frame %d: skeleton %d %r" % (n, sk.id, sk.name))
            self._check(len(sk.bones) == len(m.BONES), "frame %d: %d bones" % (n, len(sk.bones)))
            for bone in sk.bones:
                bone_id = bone.id & 0xFFFF
                exp_pos, exp_rot = m.expected_bone(bone_id, n, self.fps)
                self._check(bone.id >> 16 == m.SKELETON_ID, "frame %d: bone id %#x" % (n, bone.id))
                self._check(bone.name in ("", m.BONES.get(bone_id, ("?",))[0]),
                            "frame %d: bone %d name %r" % (n, bone_id, bone.name))
                self._check(_close(_v3(bone.position), exp_pos) and _close(_q(bone.orientation), exp_rot),
                            "frame %d: bone %d pose mismatch" % (n, bone_id))

        exp_markers = m.expected_wand_markers(n, self.fps)
        self._check(len(f.labeled_markers) == len(exp_markers),
                    "frame %d: %d labeled markers" % (n, len(f.labeled_markers)))
        for i, lm in enumerate(f.labeled_markers):
            self._check(lm.model_id == 1 and lm.marker_id == i + 1 and not lm.occluded,
                        "frame %d: labeled marker ids %d/%d" % (n, lm.model_id, lm.marker_id))
            self._check(_close(_v3(lm.position), exp_markers[i]),
                        "frame %d: labeled marker %d position mismatch" % (n, i + 1))
            self._check(abs(lm.residual - 0.3) < 1e-4, "frame %d: residual %r" % (n, lm.residual))

        self._check(len(f.marker_sets) == 1 and f.marker_sets[0].name == "Wand"
                    and all(_close(_v3(a), b) for a, b in zip(f.marker_sets[0].markers, exp_markers)),
                    "frame %d: marker set mismatch" % n)

        if f.rigid_bodies and all(rb.name for rb in f.rigid_bodies):
            self.named_frames += 1

    def rigid_body(self, rb):
        self._check_pose("topic", rb.id, rb.frame_number, _v3(rb.position), _q(rb.orientation),
                         rb.mean_error, rb.tracking_valid, rb.name)


class FlowMonitor:
    """Takes samples from both readers and keeps the flow statistics."""

    def __init__(self, frame_reader, rb_reader, verifier=None, stats_window_s=DEFAULT_WINDOW_S):
        self.frame_reader = frame_reader
        self.rb_reader = rb_reader
        self.verifier = verifier
        self.frames = self.rb_samples = self.missed = self.out_of_order = 0
        self.last_frame_number = None
        self.latest_frame = None
        self.latest_frame_source_ns = None   # DDS source timestamp of latest_frame
        self.latest_rbs = {}            # rigid body id -> latest NatNet::RigidBody
        self.latest_rb_source_ns = None  # DDS source timestamp of the latest rigid body sample
        self.rb_last_seen = {}          # rigid body id -> time.monotonic() of its last sample
        self.last_sample_time = None    # time.monotonic() of the last sample
        # Rolling metrics per topic. Rigid body gaps are counted per body id.
        self.frame_stats = StreamStats(stats_window_s)
        self.rb_stats = StreamStats(stats_window_s)

    @staticmethod
    def _latency_s(source_ns, now_ns):
        return (now_ns - source_ns) / 1e9 if source_ns else None

    def poll(self):
        """Take every available sample. Returns the number taken."""
        taken = 0
        frames = self.frame_reader.take_with_info()
        now_ns = time.time_ns()
        for f, source_ns in frames:
            taken += 1
            self.frames += 1
            if self.last_frame_number is not None:
                if f.frame_number > self.last_frame_number + 1:
                    self.missed += f.frame_number - self.last_frame_number - 1
                elif f.frame_number <= self.last_frame_number:
                    self.out_of_order += 1   # also happens when Motive playback loops
            self.last_frame_number = f.frame_number
            self.latest_frame = f
            self.latest_frame_source_ns = source_ns
            self.frame_stats.record(f.frame_number, source_time_s=f.timestamp,
                                    latency_s=self._latency_s(source_ns, now_ns))
            if self.verifier:
                self.verifier.frame(f)

        now = time.monotonic()
        rbs = self.rb_reader.take_with_info()
        now_ns = time.time_ns()
        for rb, source_ns in rbs:
            taken += 1
            self.rb_last_seen[rb.id] = now
            self.rb_samples += 1
            self.latest_rbs[rb.id] = rb
            self.latest_rb_source_ns = source_ns
            self.rb_stats.record(rb.frame_number, key=rb.id, source_time_s=rb.timestamp,
                                 latency_s=self._latency_s(source_ns, now_ns))
            if self.verifier:
                self.verifier.rigid_body(rb)

        if taken:
            self.last_sample_time = now
        return taken

    def matched_publishers(self):
        """(frame topic publishers, rigid body topic publishers)"""
        return self.frame_reader.matched_count(), self.rb_reader.matched_count()

    def passed(self):
        ok = self.frames > 0 or self.rb_samples > 0
        if self.verifier:
            ok = ok and not self.verifier.failures and self.verifier.checks > 0
        return ok


def format_metrics(name, st):
    """One line of metrics for one topic."""
    return ("%s: rate %s Hz (source %s Hz)  interval %s ms ±%s, max %s  missed %d in last %gs (%.2f%%), "
            "%d total  latency avg %s / max %s ms" % (
                name, fmt(st.rate_hz), fmt(st.source_rate_hz), fmt(st.interval_mean_ms, "%.2f"),
                fmt(st.interval_std_ms, "%.2f"), fmt(st.interval_max_ms, "%.2f"),
                st.missed_window, st.window_s, st.loss_percent_window, st.missed_total,
                fmt(st.latency_mean_ms, "%.2f"), fmt(st.latency_max_ms, "%.2f")))


def print_frame(f, rigid_bodies, source_ns=None):
    print("    frame %d  t=%.3fs  rigid bodies %d  skeletons %d  labeled markers %d  marker sets %d%s" % (
        f.frame_number, f.timestamp, len(f.rigid_bodies), len(f.skeletons),
        len(f.labeled_markers), len(f.marker_sets), "  [recording]" if f.is_recording else ""))
    print("    source: Motive t=%.4f s  mid-exposure %d  transmit %d ticks  DDS source timestamp %s" % (
        f.timestamp, f.stamp_camera_mid_exposure, f.stamp_transmit, format_utc_ns(source_ns)))
    for rb in sorted(rigid_bodies.values(), key=lambda r: r.id):
        print("    rb %3d %-12s pos (% .4f, % .4f, % .4f)  quat (% .4f, % .4f, % .4f, % .4f)  %s" % (
            rb.id, rb.name or "?", rb.position.x, rb.position.y, rb.position.z,
            rb.orientation.x, rb.orientation.y, rb.orientation.z, rb.orientation.w,
            "tracked" if rb.tracking_valid else "LOST"))
    for sk in f.skeletons:
        print("    skeleton %d %s: %s" % (sk.id, sk.name or "?",
                                         ", ".join(b.name or str(b.id & 0xFFFF) for b in sk.bones)))


def main():
    p = argparse.ArgumentParser(description="Subscribe to NatNet data on DDS and check that it flows.")
    p.add_argument("--domain", type=int, default=0, help="DDS domain id")
    p.add_argument("--dds", default="auto", choices=["auto", "rti", "cyclone"])
    p.add_argument("--duration", type=float, default=0, help="exit after N seconds (0 = until Ctrl+C)")
    p.add_argument("--quiet", action="store_true", help="only print the per-second statistics line")
    p.add_argument("--verify-mock", action="store_true",
                   help="check every value against MockNatNetServer.py's synthetic scene")
    p.add_argument("--mock-fps", type=float, default=120.0, help="--fps the mock server was started with")
    p.add_argument("--stats-window", type=float, default=DEFAULT_WINDOW_S,
                   help="seconds of history used for rate, jitter, packet loss and latency (default %(default)s)")
    args = p.parse_args()

    backend = create_backend(args.dds, args.domain)
    T = backend.types
    frame_reader = backend.create_reader(FRAME_TOPIC, T.FrameOfMocapData, depth=256)
    rb_reader = backend.create_reader(RIGID_BODY_TOPIC, T.RigidBody, depth=64)
    verifier = MockVerifier(args.mock_fps) if args.verify_mock else None
    print("[dds] %s domain %d, subscribed to %s and %s" % (
        backend.name, args.domain, FRAME_TOPIC, RIGID_BODY_TOPIC))

    mon = FlowMonitor(frame_reader, rb_reader, verifier, args.stats_window)

    start = time.monotonic()
    last_report = start
    try:
        while args.duration <= 0 or time.monotonic() - start < args.duration:
            mon.poll()
            now = time.monotonic()
            if now - last_report >= 1.0:
                fps = mon.frame_stats.snapshot().rate_hz or 0.0
                line = "[dds] frames %d (%.1f fps)  missed %d  rigid body samples %d  publishers: frame %d, rigid body %d" % (
                    (mon.frames, fps, mon.missed, mon.rb_samples) + mon.matched_publishers())
                if verifier:
                    line += "  verify: %d checks, %d failures" % (verifier.checks, len(verifier.failures))
                print(line)
                if mon.frames:
                    print("      " + format_metrics("frame topic", mon.frame_stats.snapshot()))
                if mon.rb_samples:
                    print("      " + format_metrics("rigid body topic", mon.rb_stats.snapshot()))
                if mon.latest_frame and not args.quiet:
                    print_frame(mon.latest_frame, mon.latest_rbs, mon.latest_frame_source_ns)
                last_report = now
            time.sleep(0.005)
    except KeyboardInterrupt:
        pass

    print("\n==== summary ====")
    print("frames received        : %d" % mon.frames)
    print("missed frames (gaps)   : %d" % mon.missed)
    print("out-of-order / restarts: %d" % mon.out_of_order)
    print("rigid body samples     : %d (%d bodies)" % (mon.rb_samples, len(mon.latest_rbs)))
    print("rigid body gaps        : %d missed, %d out of order" % (
        mon.rb_stats.missed_total, mon.rb_stats.out_of_order_total))
    if not (mon.frames or mon.rb_samples):
        print("FAIL: no data received. Is NatNetToDDS.py running on the same DDS domain?")
    if verifier:
        print("verification checks    : %d" % verifier.checks)
        print("frames with names      : %d" % verifier.named_frames)
        print("verification failures  : %d" % len(verifier.failures))
        for msg in verifier.failures[:10]:
            print("    " + msg)
    ok = mon.passed()
    print("RESULT: %s" % ("PASS" if ok else "FAIL"))
    backend.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
