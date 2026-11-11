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
from natnet_dds.gui_common import (BAD, IDLE, OK, WARN, LanguagePicker, Lamp, LogPane, RigidBodyTable,
                                   command_line, labeled)
from natnet_dds.i18n import load_saved_language, tr

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
        self.top = None
        self._stopping = False   # True between pressing Stop and the readers closing
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
        self.cmdline = tk.StringVar()
        self._build()
        for var in self.v.values():
            var.trace_add("write", lambda *_: self._update_cmdline())
        self._update_cmdline()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.after(250, self._tick)

    # -- layout ---------------------------------------------------------------

    def _build(self):
        """Create every widget in the current language. Called again on a
        language change; settings live in self.v, so they survive."""
        self.root.title(tr("client.title"))
        pad = {"padx": 8, "pady": 4}
        top = self.top = ttk.Frame(self.root, padding=8)
        top.pack(fill="both", expand=True)
        top.columnconfigure(0, weight=1)

        sf = ttk.LabelFrame(top, text=tr("client.dds_group"), padding=8)
        sf.grid(row=0, column=0, sticky="we", **pad)
        self.dds_combo = labeled(sf, 0, tr("common.implementation"), ttk.Combobox(
            sf, textvariable=self.v["dds"], state="readonly", values=("auto", "rti", "cyclone"), width=10))
        self.domain_spin = labeled(sf, 0, tr("common.domain_id"), ttk.Spinbox(
            sf, from_=0, to=232, textvariable=self.v["domain"], width=6), column=2, padx=(0, 16))
        sf.columnconfigure(1, pad=16)
        self.verify_cb = ttk.Checkbutton(sf, text=tr("client.verify"), variable=self.v["verify_mock"])
        self.verify_cb.grid(row=1, column=0, columnspan=2, sticky="w", pady=2)
        vf = ttk.Frame(sf)
        vf.grid(row=1, column=2, columnspan=2, sticky="w")
        self.fps_spin = ttk.Spinbox(vf, from_=1, to=1000, textvariable=self.v["mock_fps"], width=6)
        self.fps_spin.pack(side="left")
        ttk.Label(vf, text=tr("client.verify_hint"), foreground="#666666").pack(side="left", padx=4)
        self.settings_widgets = (self.dds_combo, self.domain_spin, self.verify_cb, self.fps_spin)

        bf = ttk.Frame(top)
        bf.grid(row=1, column=0, sticky="we", **pad)
        self.start_btn = ttk.Button(bf, command=self._toggle)
        self.start_btn.pack(side="left")
        ttk.Button(bf, text=tr("client.reset"), command=self._reset).pack(side="left", padx=8)
        LanguagePicker(bf, self._on_language).pack(side="right")

        stf = ttk.LabelFrame(top, text=tr("common.status"), padding=8)
        stf.grid(row=2, column=0, sticky="we", **pad)
        for i in range(4):
            stf.columnconfigure(i, weight=1, uniform="lamp")
        self.lamp_dds = Lamp(stf, tr("client.lamp_dds"))
        self.lamp_pubs = Lamp(stf, tr("client.lamp_pubs"))
        self.lamp_flow = Lamp(stf, tr("client.lamp_flow"))
        self.lamp_check = Lamp(stf, tr("client.lamp_check"))
        for i, lamp in enumerate((self.lamp_dds, self.lamp_pubs, self.lamp_flow, self.lamp_check)):
            lamp.grid(row=0, column=i, sticky="nw", padx=4)
            lamp.set(IDLE, tr("common.stopped"))

        ff = ttk.LabelFrame(top, text=tr("client.latest_frame", topic=FRAME_TOPIC), padding=6)
        ff.grid(row=3, column=0, sticky="we", **pad)
        self.frame_info = ttk.Label(ff, text="—", font=("TkFixedFont", 10), justify="left")
        self.frame_info.pack(anchor="w")

        rf = ttk.LabelFrame(top, text=tr("client.rigid_bodies_group", topic=RIGID_BODY_TOPIC), padding=4)
        rf.grid(row=4, column=0, sticky="nsew", **pad)
        top.rowconfigure(4, weight=1)
        self.table = RigidBodyTable(rf, height=6)
        self.table.pack(fill="both", expand=True)

        lf = ttk.LabelFrame(top, text=tr("common.log"), padding=4)
        lf.grid(row=5, column=0, sticky="nsew", **pad)
        top.rowconfigure(5, weight=1)
        self.log = LogPane(lf, height=7)
        self.log.pack(fill="both", expand=True)
        self.log.install()

        cf = ttk.Frame(top)
        cf.grid(row=6, column=0, sticky="we", **pad)
        ttk.Label(cf, text=tr("common.command_line")).pack(side="left")
        ttk.Entry(cf, textvariable=self.cmdline, state="readonly").pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(cf, text=tr("common.copy"), command=self._copy_cmdline).pack(side="left")

        self._sync_buttons()

    def _sync_buttons(self):
        """Set the start button and enabled widgets from the current state."""
        if self._stopping:
            self.start_btn.configure(state="disabled", text=tr("common.stopping"))
        else:
            self.start_btn.configure(state="normal",
                                     text=tr("client.stop" if self.session else "client.start"))
        enabled = not self.session and not self._stopping
        for w in self.settings_widgets:
            if w is self.dds_combo:
                w.configure(state="readonly" if enabled else "disabled")
            else:
                w.configure(state="normal" if enabled else "disabled")

    def _on_language(self, _code):
        log_text = self.log.get_text()
        self.top.destroy()
        self._build()
        self.log.set_text(log_text)
        self._refresh()

    # -- settings ---------------------------------------------------------------

    def _read_config(self):
        cfg = {"dds": self.v["dds"].get(), "verify_mock": bool(self.v["verify_mock"].get())}
        try:
            cfg["domain"] = int(self.v["domain"].get())
            if not 0 <= cfg["domain"] <= 232:
                raise ValueError
        except ValueError:
            raise ValueError(tr("common.err_domain"))
        try:
            cfg["mock_fps"] = float(self.v["mock_fps"].get())
            if cfg["mock_fps"] <= 0:
                raise ValueError
        except ValueError:
            raise ValueError(tr("client.err_fps"))
        return cfg

    def _update_cmdline(self):
        args = ["--dds", self.v["dds"].get(), "--domain", self.v["domain"].get()]
        if self.v["verify_mock"].get():
            args += ["--verify-mock", "--mock-fps", self.v["mock_fps"].get()]
        self.cmdline.set(command_line("DDSTestClient.py", args))

    def _copy_cmdline(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.cmdline.get())

    # -- actions ----------------------------------------------------------------

    def _toggle(self):
        if self.session:
            self._stopping = True
            session, self.session = self.session, None
            self._sync_buttons()
            session.stop(done=lambda: self.root.after(0, self._stopped))
            return
        try:
            cfg = self._read_config()
        except ValueError as e:
            messagebox.showerror(tr("common.invalid_setting"), str(e), parent=self.root)
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
        self._sync_buttons()

    def _stopped(self):
        self._stopping = False
        self._sync_buttons()

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
                lamp.set(IDLE, tr("common.stopped"))
            return
        c = s.cfg
        if s.state == "error":
            self.lamp_dds.set(BAD, s.error)
            for lamp in (self.lamp_pubs, self.lamp_flow, self.lamp_check):
                lamp.set(IDLE, "")
            return
        if not s.monitor:
            self.lamp_dds.set(WARN, tr("common.creating_participant"))
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
        self.lamp_dds.set(OK, tr("common.backend_domain", backend=s.backend.name, domain=c["domain"]))

        # 2. publishers
        detail = tr("client.pubs_counts", frame=matched[0], rigid_body=matched[1])
        if any(matched):
            self.lamp_pubs.set(OK, detail)
        else:
            waited = now - s.started_at
            if waited < 5:
                self.lamp_pubs.set(WARN, detail + "\n" + tr("client.discovering"))
            else:
                self.lamp_pubs.set(BAD, detail + "\n" + tr("client.no_bridge", domain=c["domain"]))

        # 3. flow
        dt = now - self.rate_t
        if dt >= 1.0:
            self.fps = (frames - self.rate_frames) / dt
            self.rate_frames, self.rate_t = frames, now
        if last is not None and now - last < 1.0:
            self.lamp_flow.set(OK, tr("client.flow_ok", fps=self.fps, frames=frames, rb_samples=rb_samples))
        elif last is not None:
            self.lamp_flow.set(BAD, tr("client.flow_stopped", seconds=now - last, frames=frames))
        elif any(matched):
            self.lamp_flow.set(WARN, tr("client.flow_no_samples"))
        else:
            self.lamp_flow.set(IDLE, tr("common.waiting"))

        # 4. integrity
        if v:
            if n_failures:
                self.lamp_check.set(BAD, tr("client.verify_fail", failures=n_failures, checks=checks,
                                            missed=missed, out_of_order=ooo))
            elif checks:
                self.lamp_check.set(OK, tr("client.verify_pass", checks=checks, named=named,
                                           missed=missed, out_of_order=ooo))
            else:
                self.lamp_check.set(IDLE, tr("client.verifying"))
        elif frames:
            self.lamp_check.set(OK if missed == 0 else WARN, tr(
                "client.integrity", missed=missed, percent=100.0 * missed / (frames + missed), out_of_order=ooo))
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
        line = tr("client.frame_line", frame=f.frame_number, t=f.timestamp,
                  timecode=f.timecode, timecode_sub=f.timecode_sub)
        if f.is_recording:
            line += tr("client.recording")
        lines = [line, tr("client.frame_counts", rigid_bodies=len(f.rigid_bodies), skeletons=len(f.skeletons),
                          labeled_markers=len(f.labeled_markers), marker_sets=len(f.marker_sets))]
        for sk in f.skeletons[:4]:
            lines.append(tr("client.skeleton_line", id=sk.id, name=sk.name or "?",
                            bones=", ".join(b.name or str(b.id & 0xFFFF) for b in sk.bones)))
        return "\n".join(lines)


def main():
    load_saved_language()
    root = tk.Tk()
    if sys.platform.startswith("linux"):
        ttk.Style(root).theme_use("clam")
    ClientApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
