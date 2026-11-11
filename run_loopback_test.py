#!/usr/bin/env python3
"""One-command end-to-end test, no Motive required:

    MockNatNetServer.py  --NatNet-->  NatNetToDDS.py  --DDS-->  DDSTestClient.py --verify-mock

Exits 0 if every frame arrived over DDS with the exact values the mock sent.

    python run_loopback_test.py
    python run_loopback_test.py --unicast --fps 240 --dds cyclone
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--unicast", action="store_true", help="test NatNet unicast instead of multicast")
    p.add_argument("--fps", type=float, default=120.0)
    p.add_argument("--dds", default="auto", choices=["auto", "rti", "cyclone"])
    p.add_argument("--domain", type=int, default=0)
    p.add_argument("--seconds", type=float, default=5.0, help="how long the test client listens")
    args = p.parse_args()

    py = [sys.executable, "-u"]
    cast = ["--unicast"] if args.unicast else []
    dds = ["--dds", args.dds, "--domain", str(args.domain)]

    mock = subprocess.Popen(py + [os.path.join(HERE, "MockNatNetServer.py"), "--fps", str(args.fps)] + cast)
    bridge = None
    try:
        time.sleep(1.0)
        bridge = subprocess.Popen(py + [os.path.join(HERE, "NatNetToDDS.py"),
                                        "--duration", str(args.seconds + 4)] + cast + dds)
        time.sleep(2.0)
        result = subprocess.call(py + [os.path.join(HERE, "DDSTestClient.py"), "--quiet", "--verify-mock",
                                       "--mock-fps", str(args.fps), "--duration", str(args.seconds)] + dds)
    finally:
        for proc in (bridge, mock):
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
    print("\nLOOPBACK TEST %s" % ("PASSED" if result == 0 else "FAILED"))
    return result


if __name__ == "__main__":
    sys.exit(main())
