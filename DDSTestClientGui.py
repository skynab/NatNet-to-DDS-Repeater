#!/usr/bin/env python3
"""GUI for the DDS test client (DDSTestClient.py).

Pick the DDS implementation and domain, press Start, and the status lights
show whether the bridge's data is reaching this machine:

    DDS participant -> matched publishers -> data flow -> data integrity

The tables show the latest frame and every rigid body's pose. With
"Verify against mock" (when the bridge is fed by MockNatNetServer.py) every
received value is checked against the mock's known scene.

    python DDSTestClientGui.py
"""
import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from DDSTestClient import FlowMonitor, MockVerifier
from natnet_dds import FRAME_TOPIC, RIGID_BODY_TOPIC, create_backend
from natnet_dds.gui_common import (BAD, IDLE, OK, WARN, Lamp, LogPane, RigidBodyTable,
                                   command_line, labeled)

SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".natnet_dds_client_gui.json")
DEFAULTS = {"dds": "auto", "domain": 0, "verify_mock": False, "mock_fps": 120}
STALE_S = 1.0


class ClientSession:
    """Creates the DDS readers and polls them on a worker thread."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.lock = threading.Lock()
        self.state = "starting"      # starting -> running -> stopped | error
        self.error = None
        self.backend = None
        self.monitor = None
        self.started_at = time.monotonic()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        c = self.cfg
        try:
            self.backend = create_backend(c["dds"], c["domain"])
            T = self.backend.types
            frame_reader = self.backend.create_reader(FRAME_TOPIC, T.FrameOfMocapData, depth=256)
            rb_reader = self.backend.create_reader(RIGID_BODY_TOPIC, T.RigidBody, depth=64)
            verifier = MockVerifier(c["mock_fps"]) if c["verify_mock"] else None
            self.monitor = FlowMonitor(frame_reader, rb_reader, verifier)
            print("[dds] %s domain %d, subscribed to %s and %s" % (
                self.backend.name, c["domain"], FRAME_TOPIC, RIGID_BODY_TOPIC))
        except Exception as e:  # noqa: BLE001 - show anything that goes wrong
            self.error = str(e) or repr(e)
            self.state = "error"
            print("ERROR: %s" % self.error)
            return
        if self.state == "starting":
            self.state = "running"
        while not self._stop.is_set():
            try:
                with self.lock:
                    self.monitor.poll()
            except Exception as e:  # noqa: BLE001
                print("[dds] read error: %r" % e)
                time.sleep(0.5)
            time.sleep(0.005)
        try:
            self.backend.close()
        except Exception as e:  # noqa: BLE001
            print("[dds] close error: %r" % e)
        print("[dds] stopped")

    def stop(self, done=None):
        self.state = "stopped"
        self._stop.set()

        def _wait():
            self._thread.join()
            if done:
                done()
        threading.Thread(target=_wait, daemon=True).start()


class ClientApp:
    def __init__(self, root):
        self.root = root
        self.session = None
        self.rate_frames = 0
        self.rate_t = time.monotonic()
        self.fps = 0.0
        self.failures_shown = 0
        root.title("DDS Test Client")
        root.minsize(760, 600)

        cfg = dict(DEFAULTS)
        try:
            with open(SETTINGS_FILE) as f:
                cfg.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass
        self.v = {
            "dds": tk.StringVar(value=cfg["dds"]),
            "domain": tk.StringVar(value=str(cfg["domain"])),
            "verify_mock": tk.BooleanVar(value=cfg["verify_mock"]),
            "mock_fps": tk.StringVar(value=str(cfg["mock_fps"])),
        }
        self._build()
        for var in self.v.values():
            var.trace_add("write", lambda *_: self._update_cmdline())
        self._update_cmdline()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.after(250, self._tick)

    # -- layout ---------------------------------------------------------------

    def _build(self):
        pad = {"padx": 8, "pady": 4}
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="both", expand=True)
        top.columnconfigure(0, weight=1)

        sf = ttk.LabelFrame(top, text="DDS", padding=8)
        sf.grid(row=0, column=0, sticky="we", **pad)
        self.dds_combo = labeled(sf, 0, "Implementation", ttk.Combobox(
            sf, textvariable=self.v["dds"], state="readonly", values=("auto", "rti", "cyclone"), width=10))
        self.domain_spin = labeled(sf, 0, "Domain ID", ttk.Spinbox(
            sf, from_=0, to=232, textvariable=self.v["domain"], width=6), column=2, padx=(0, 16))
        sf.columnconfigure(1, pad=16)
        self.verify_cb = ttk.Checkbutton(sf, text="Verify against mock server at", variable=self.v["verify_mock"])
        self.verify_cb.grid(row=1, column=0, columnspan=2, sticky="w", pady=2)
        vf = ttk.Frame(sf)
        vf.grid(row=1, column=2, columnspan=2, sticky="w")
        self.fps_spin = ttk.Spinbox(vf, from_=1, to=1000, textvariable=self.v["mock_fps"], width=6)
        self.fps_spin.pack(side="left")
        ttk.Label(vf, text="fps (only when the bridge is fed by MockNatNetServer.py)",
                  foreground="#666666").pack(side="left", padx=4)
        self.settings_widgets = (self.dds_combo, self.domain_spin, self.verify_cb, self.fps_spin)

        bf = ttk.Frame(top)
        bf.grid(row=1, column=0, sticky="we", **pad)
        self.start_btn = ttk.Button(bf, text="Start listening", command=self._toggle)
        self.start_btn.pack(side="left")
        ttk.Button(bf, text="Reset counters", command=self._reset).pack(side="left", padx=8)

        stf = ttk.LabelFrame(top, text="Status", padding=8)
        stf.grid(row=2, column=0, sticky="we", **pad)
        for i in range(4):
            stf.columnconfigure(i, weight=1, uniform="lamp")
        self.lamp_dds = Lamp(stf, "1. DDS participant")
        self.lamp_pubs = Lamp(stf, "2. Matched publishers")
        self.lamp_flow = Lamp(stf, "3. Data flow")
        self.lamp_check = Lamp(stf, "4. Integrity")
        for i, lamp in enumerate((self.lamp_dds, self.lamp_pubs, self.lamp_flow, self.lamp_check)):
            lamp.grid(row=0, column=i, sticky="nw", padx=4)
            lamp.set(IDLE, "stopped")

        ff = ttk.LabelFrame(top, text="Latest " + FRAME_TOPIC, padding=6)
        ff.grid(row=3, column=0, sticky="we", **pad)
        self.frame_info = ttk.Label(ff, text="—", font=("TkFixedFont", 10), justify="left")
        self.frame_info.pack(anchor="w")

        rf = ttk.LabelFrame(top, text="Rigid bodies (" + RIGID_BODY_TOPIC + ")", padding=4)
        rf.grid(row=4, column=0, sticky="nsew", **pad)
        top.rowconfigure(4, weight=1)
        self.table = RigidBodyTable(rf, height=6)
        self.table.pack(fill="both", expand=True)

        lf = ttk.LabelFrame(top, text="Log", padding=4)
        lf.grid(row=5, column=0, sticky="nsew", **pad)
        top.rowconfigure(5, weight=1)
        self.log = LogPane(lf, height=7)
        self.log.pack(fill="both", expand=True)
        self.log.install()

        cf = ttk.Frame(top)
        cf.grid(row=6, column=0, sticky="we", **pad)
        ttk.Label(cf, text="Command line:").pack(side="left")
        self.cmdline = tk.StringVar()
        ttk.Entry(cf, textvariable=self.cmdline, state="readonly").pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(cf, text="Copy", command=self._copy_cmdline).pack(side="left")

    # -- settings ---------------------------------------------------------------

    def _read_config(self):
        cfg = {"dds": self.v["dds"].get(), "verify_mock": bool(self.v["verify_mock"].get())}
        try:
            cfg["domain"] = int(self.v["domain"].get())
            if not 0 <= cfg["domain"] <= 232:
                raise ValueError
        except ValueError:
            raise ValueError("domain must be a number from 0 to 232")
        try:
            cfg["mock_fps"] = float(self.v["mock_fps"].get())
            if cfg["mock_fps"] <= 0:
                raise ValueError
        except ValueError:
            raise ValueError("mock fps must be a positive number")
        return cfg

    def _update_cmdline(self):
        args = ["--dds", self.v["dds"].get(), "--domain", self.v["domain"].get()]
        if self.v["verify_mock"].get():
            args += ["--verify-mock", "--mock-fps", self.v["mock_fps"].get()]
        self.cmdline.set(command_line("DDSTestClient.py", args))

    def _copy_cmdline(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.cmdline.get())

    def _set_settings_enabled(self, enabled):
        for w in self.settings_widgets:
            if w is self.dds_combo:
                w.configure(state="readonly" if enabled else "disabled")
            else:
                w.configure(state="normal" if enabled else "disabled")

    # -- actions ----------------------------------------------------------------

    def _toggle(self):
        if self.session:
            self.start_btn.configure(state="disabled", text="Stopping…")
            session, self.session = self.session, None
            session.stop(done=lambda: self.root.after(0, self._stopped))
            return
        try:
            cfg = self._read_config()
        except ValueError as e:
            messagebox.showerror("Invalid setting", str(e), parent=self.root)
            return
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(cfg, f, indent=2)
        except OSError:
            pass
        self.table.clear()
        self.frame_info.configure(text="—")
        self.rate_frames, self.rate_t, self.fps = 0, time.monotonic(), 0.0
        self.failures_shown = 0
        self.session = ClientSession(cfg)
        self._set_settings_enabled(False)
        self.start_btn.configure(text="Stop listening")

    def _stopped(self):
        self.start_btn.configure(state="normal", text="Start listening")
        self._set_settings_enabled(True)

    def _reset(self):
        s = self.session
        if not (s and s.monitor):
            return
        with s.lock:
            m = s.monitor
            fresh = FlowMonitor(m.frame_reader, m.rb_reader,
                                MockVerifier(s.cfg["mock_fps"]) if m.verifier else None)
            s.monitor = fresh
        self.rate_frames, self.rate_t, self.failures_shown = 0, time.monotonic(), 0
        self.table.clear()
        print("[gui] counters reset")

    def _on_close(self):
        if self.session:
            self.session.stop(done=lambda: self.root.after(0, self.root.destroy))
            self.session = None
            self.root.after(3000, self.root.destroy)
        else:
            self.root.destroy()

    # -- status -----------------------------------------------------------------

    def _tick(self):
        try:
            self._refresh()
        finally:
            self.root.after(250, self._tick)

    def _refresh(self):
        s = self.session
        if not s:
            for lamp in (self.lamp_dds, self.lamp_pubs, self.lamp_flow, self.lamp_check):
                lamp.set(IDLE, "stopped")
            return
        c = s.cfg
        if s.state == "error":
            self.lamp_dds.set(BAD, s.error)
            for lamp in (self.lamp_pubs, self.lamp_flow, self.lamp_check):
                lamp.set(IDLE, "")
            return
        if not s.monitor:
            self.lamp_dds.set(WARN, "creating participant…")
            return

        now = time.monotonic()
        with s.lock:
            m = s.monitor
            matched = m.matched_publishers()
            frames, missed, ooo, rb_samples = m.frames, m.missed, m.out_of_order, m.rb_samples
            last = m.last_sample_time
            f = m.latest_frame
            rbs = list(m.latest_rbs.values())
            stale = {i for i, t in m.rb_last_seen.items() if now - t > STALE_S}
            if not rbs and f:   # bridge started with --no-rigid-bodies: use the frame topic
                rbs = list(f.rigid_bodies)
                stale = {rb.id for rb in rbs} if last is None or now - last > STALE_S else set()
            v = m.verifier
            checks = v.checks if v else 0
            new_failures = v.failures[self.failures_shown:self.failures_shown + 20] if v else []
            n_failures = len(v.failures) if v else 0
            named = v.named_frames if v else 0
            frame_text = self._frame_text(f) if f else None

        # 1. participant
        self.lamp_dds.set(OK, "%s, domain %d" % (s.backend.name, c["domain"]))

        # 2. publishers
        detail = "frame topic %d, rigid body topic %d" % matched
        if any(matched):
            self.lamp_pubs.set(OK, detail)
        else:
            waited = now - s.started_at
            self.lamp_pubs.set(WARN if waited < 5 else BAD, detail + (
                "\nNo bridge found. Is NatNetToDDS running on domain %d, and is "
                "multicast allowed between the machines?" % c["domain"] if waited >= 5 else "\ndiscovering…"))

        # 3. flow
        dt = now - self.rate_t
        if dt >= 1.0:
            self.fps = (frames - self.rate_frames) / dt
            self.rate_frames, self.rate_t = frames, now
        if last is not None and now - last < 1.0:
            self.lamp_flow.set(OK, "%.1f fps\n%d frames, %d rigid body samples" % (self.fps, frames, rb_samples))
        elif last is not None:
            self.lamp_flow.set(BAD, "no data for %.0fs\n%d frames received" % (now - last, frames))
        elif any(matched):
            self.lamp_flow.set(WARN, "publisher matched but no samples yet. Is the bridge receiving "
                                     "frames from Motive?")
        else:
            self.lamp_flow.set(IDLE, "waiting…")

        # 4. integrity
        if v:
            if n_failures:
                self.lamp_check.set(BAD, "FAIL: %d of %d checks failed\nmissed %d, out of order %d" % (
                    n_failures, checks, missed, ooo))
            elif checks:
                self.lamp_check.set(OK, "PASS: %d checks, %d frames named\nmissed %d, out of order %d" % (
                    checks, named, missed, ooo))
            else:
                self.lamp_check.set(IDLE, "verifying against mock…")
        elif frames:
            color = OK if missed == 0 else WARN
            self.lamp_check.set(color, "missed %d frames (%.2f%%)\nout of order / restarts %d" % (
                missed, 100.0 * missed / (frames + missed), ooo))
        else:
            self.lamp_check.set(IDLE, "")
        for msg in new_failures:
            print("[verify] " + msg)
        self.failures_shown += len(new_failures)

        if frame_text:
            self.frame_info.configure(text=frame_text)
        self.table.update_rows(rbs, stale_ids=stale)

    @staticmethod
    def _frame_text(f):
        lines = ["frame %d   t=%.3f s   timecode %d.%d%s" % (
                     f.frame_number, f.timestamp, f.timecode, f.timecode_sub,
                     "   [RECORDING]" if f.is_recording else ""),
                 "rigid bodies %d   skeletons %d   labeled markers %d   marker sets %d" % (
                     len(f.rigid_bodies), len(f.skeletons), len(f.labeled_markers), len(f.marker_sets))]
        for sk in f.skeletons[:4]:
            lines.append("skeleton %d %s: %s" % (sk.id, sk.name or "?",
                                                 ", ".join(b.name or str(b.id & 0xFFFF) for b in sk.bones)))
        return "\n".join(lines)


def main():
    root = tk.Tk()
    if sys.platform.startswith("linux"):
        ttk.Style(root).theme_use("clam")
    ClientApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
