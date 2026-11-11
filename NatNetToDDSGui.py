#!/usr/bin/env python3
"""GUI for the NatNet -> DDS bridge (NatNetToDDS.py).

Fill in the Motive connection and DDS settings, press Start, and the status
lights show each hop of the pipeline:

    NatNet connection -> incoming frames -> DDS publisher -> DDS subscribers

The rigid body table shows the poses being republished. "Start mock Motive"
launches MockNatNetServer.py so you can try everything without cameras.

    python NatNetToDDSGui.py
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import NatNetToDDS as nn
from natnet_dds import FRAME_TOPIC, RIGID_BODY_TOPIC, create_backend
from natnet_dds.gui_common import (BAD, IDLE, OK, WARN, LanguagePicker, Lamp, LogPane, RigidBodyTable,
                                   command_line, labeled, local_ipv4_addresses)
from natnet_dds.i18n import load_saved_language, tr

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".natnet_dds_bridge_gui.json")

DEFAULTS = {
    "server": "127.0.0.1", "client": "127.0.0.1", "multicast": True,
    "multicast_address": "239.255.42.99", "command_port": 1510, "data_port": 1511,
    "dds": "auto", "domain": 0, "reliable": False,
    "publish_frames": True, "publish_rigid_bodies": True, "mock_fps": 120,
}


class BridgeSession:
    """One running bridge: DDS backend + NatNet client, started off the UI thread."""

    CONNECT_RETRY_S = 2.0

    def __init__(self, cfg):
        self.cfg = cfg
        self.state = "starting"     # starting -> connecting -> connected | error | stopped
        self.error = None
        self.backend = None
        self.bridge = None
        self.client = None
        self._request_descriptions = None
        self.started_at = time.monotonic()
        self.connected_at = None
        self._last_connect = 0.0
        self._thread = threading.Thread(target=self._start, daemon=True)
        self._thread.start()

    def _start(self):
        c = self.cfg
        try:
            self.backend = create_backend(c["dds"], c["domain"])
            print("[dds] using %s, domain %d" % (self.backend.name, c["domain"]))
            self.bridge = nn.NatNetToDDSBridge(self.backend, c["publish_frames"],
                                               c["publish_rigid_bodies"], c["reliable"])
            client, self._request_descriptions = nn.create_natnet_client(
                self.bridge, c["server"], c["client"], c["multicast"], c["multicast_address"],
                c["command_port"], c["data_port"])
            print("[natnet] connecting to %s from %s (%s)" % (
                c["server"], c["client"],
                "multicast " + c["multicast_address"] if c["multicast"] else "unicast"))
            if not client.run():
                raise RuntimeError(tr("bridge.err_sockets"))
            self.client = client
            self._last_connect = time.monotonic()
            if self.state == "starting":
                self.state = "connecting"
        except Exception as e:  # noqa: BLE001 - show anything that goes wrong
            self.error = str(e) or repr(e)
            self.state = "error"
            print("ERROR: %s" % self.error)

    def tick(self):
        """Called periodically from the UI: retries the connect handshake and
        requests model names once connected."""
        if self.state != "connecting" or not self.client:
            return
        if self.client.connected():
            self.state = "connected"
            self.connected_at = time.monotonic()
            ver = self.client.get_server_version()
            nn_ver = self.client.get_nat_net_version_server()
            print("[natnet] connected to %s %d.%d.%d.%d (NatNet %d.%d)" % (
                self.client.get_application_name(), *ver, nn_ver[0], nn_ver[1]))
            self._request_descriptions()
        elif time.monotonic() - self._last_connect > self.CONNECT_RETRY_S:
            self._last_connect = time.monotonic()
            try:
                self.client.send_connect()
            except OSError as e:
                print("[natnet] connect request failed: %s" % e)

    def stop(self, done=None):
        """Shut down in a background thread (the SDK client can take ~2 s)."""
        self.state = "stopped"

        def _stop():
            self._thread.join()     # let a slow start (e.g. RTI participant) finish first
            try:
                if self.client:
                    self.client.shutdown()
                if self.backend:
                    self.backend.close()
            except Exception as e:  # noqa: BLE001
                print("[bridge] shutdown error: %r" % e)
            print("[bridge] stopped")
            if done:
                done()
        threading.Thread(target=_stop, daemon=True).start()


class MockServer:
    """MockNatNetServer.py as a child process with its output sent to print()."""

    def __init__(self, cfg, fps):
        args = [sys.executable, "-u", os.path.join(HERE, "MockNatNetServer.py"),
                "--fps", str(fps), "--bind", cfg["server"],
                "--command-port", str(cfg["command_port"]), "--data-port", str(cfg["data_port"]),
                "--multicast-group", cfg["multicast_address"], "--multicast-interface", cfg["client"]]
        if not cfg["multicast"]:
            args.append("--unicast")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, bufsize=1, creationflags=flags)
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for line in self.proc.stdout:
            print(line if line.startswith("[mock]") else "[mock] " + line, end="")
        print("[mock] exited with code %s" % self.proc.wait())

    def running(self):
        return self.proc.poll() is None

    def stop(self):
        if self.running():
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()


class BridgeApp:
    def __init__(self, root):
        self.root = root
        self.session = None
        self.mock = None
        self.last_count = 0
        self.last_rate_t = time.monotonic()
        self.fps = 0.0
        self.last_error_shown = None
        self.top = None
        root.minsize(760, 640)

        cfg = dict(DEFAULTS)
        try:
            with open(SETTINGS_FILE) as f:
                cfg.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass

        self.v = {
            "server": tk.StringVar(value=cfg["server"]),
            "client": tk.StringVar(value=cfg["client"]),
            "multicast": tk.BooleanVar(value=cfg["multicast"]),
            "multicast_address": tk.StringVar(value=cfg["multicast_address"]),
            "command_port": tk.StringVar(value=str(cfg["command_port"])),
            "data_port": tk.StringVar(value=str(cfg["data_port"])),
            "dds": tk.StringVar(value=cfg["dds"]),
            "domain": tk.StringVar(value=str(cfg["domain"])),
            "reliable": tk.BooleanVar(value=cfg["reliable"]),
            "publish_frames": tk.BooleanVar(value=cfg["publish_frames"]),
            "publish_rigid_bodies": tk.BooleanVar(value=cfg["publish_rigid_bodies"]),
            "mock_fps": tk.StringVar(value=str(cfg["mock_fps"])),
        }
        self.cmdline = tk.StringVar()
        self._build()
        for var in self.v.values():
            var.trace_add("write", lambda *_: self._update_cmdline())
        self._update_cmdline()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(250, self._tick)

    # -- layout ---------------------------------------------------------------

    def _build(self):
        """Create every widget in the current language. Called again on a
        language change; settings live in self.v, so they survive."""
        self.root.title(tr("bridge.title"))
        pad = {"padx": 8, "pady": 4}
        top = self.top = ttk.Frame(self.root, padding=8)
        top.pack(fill="both", expand=True)
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)

        # NatNet settings
        nf = ttk.LabelFrame(top, text=tr("bridge.natnet_group"), padding=8)
        nf.grid(row=0, column=0, sticky="nsew", **pad)
        nf.columnconfigure(1, weight=1)
        self.settings_widgets = []
        w = labeled(nf, 0, tr("bridge.server_ip"), ttk.Entry(nf, textvariable=self.v["server"], width=18))
        self.settings_widgets.append(w)
        w = labeled(nf, 1, tr("bridge.local_ip"), ttk.Combobox(nf, textvariable=self.v["client"],
                                                                values=local_ipv4_addresses(), width=16))
        self.settings_widgets.append(w)
        tf = ttk.Frame(nf)
        labeled(nf, 2, tr("bridge.transmission"), tf)
        for i, (key, val) in enumerate((("bridge.multicast_option", True), ("bridge.unicast_option", False))):
            rb = ttk.Radiobutton(tf, text=tr(key), value=val, variable=self.v["multicast"],
                                 command=self._on_transport)
            rb.grid(row=0, column=i, sticky="w", padx=(0, 10))
            self.settings_widgets.append(rb)
        self.mcast_entry = labeled(nf, 3, tr("bridge.multicast_group"),
                                   ttk.Entry(nf, textvariable=self.v["multicast_address"], width=18))
        self.settings_widgets.append(self.mcast_entry)
        pf = ttk.Frame(nf)
        labeled(nf, 4, tr("bridge.ports"), pf)
        for i, key in enumerate(("command_port", "data_port")):
            e = ttk.Entry(pf, textvariable=self.v[key], width=7)
            e.grid(row=0, column=i, padx=(0, 6))
            self.settings_widgets.append(e)
        ttk.Label(nf, text=tr("bridge.natnet_hint"),
                  foreground="#666666").grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # DDS settings
        df = ttk.LabelFrame(top, text=tr("bridge.dds_group"), padding=8)
        df.grid(row=0, column=1, sticky="nsew", **pad)
        df.columnconfigure(1, weight=1)
        self.dds_combo = labeled(df, 0, tr("common.implementation"), ttk.Combobox(
            df, textvariable=self.v["dds"], state="readonly", values=("auto", "rti", "cyclone"), width=10))
        self.settings_widgets.append(self.dds_combo)
        w = labeled(df, 1, tr("common.domain_id"),
                    ttk.Spinbox(df, from_=0, to=232, textvariable=self.v["domain"], width=6))
        self.settings_widgets.append(w)
        for i, (key, text) in enumerate((("publish_frames", tr("bridge.publish_topic", topic=FRAME_TOPIC)),
                                         ("publish_rigid_bodies",
                                          tr("bridge.publish_topic", topic=RIGID_BODY_TOPIC)),
                                         ("reliable", tr("bridge.reliable")))):
            cb = ttk.Checkbutton(df, text=text, variable=self.v[key])
            cb.grid(row=2 + i, column=0, columnspan=2, sticky="w", pady=1)
            self.settings_widgets.append(cb)

        # Buttons + language
        bf = ttk.Frame(top)
        bf.grid(row=1, column=0, columnspan=2, sticky="we", **pad)
        self.start_btn = ttk.Button(bf, command=self._toggle_bridge)
        self.start_btn.pack(side="left")
        ttk.Separator(bf, orient="vertical").pack(side="left", fill="y", padx=12)
        self.mock_btn = ttk.Button(bf, command=self._toggle_mock)
        self.mock_btn.pack(side="left")
        ttk.Label(bf, text=tr("bridge.mock_at")).pack(side="left", padx=4)
        ttk.Spinbox(bf, from_=1, to=1000, textvariable=self.v["mock_fps"], width=5).pack(side="left")
        ttk.Label(bf, text=tr("bridge.mock_hint"), foreground="#666666").pack(side="left", padx=4)
        LanguagePicker(bf, self._on_language).pack(side="right")

        # Status
        sf = ttk.LabelFrame(top, text=tr("common.status"), padding=8)
        sf.grid(row=2, column=0, columnspan=2, sticky="we", **pad)
        for i in range(4):
            sf.columnconfigure(i, weight=1, uniform="lamp")
        self.lamp_natnet = Lamp(sf, tr("bridge.lamp_natnet"))
        self.lamp_frames = Lamp(sf, tr("bridge.lamp_frames"))
        self.lamp_dds = Lamp(sf, tr("bridge.lamp_dds"))
        self.lamp_subs = Lamp(sf, tr("bridge.lamp_subs"))
        for i, lamp in enumerate((self.lamp_natnet, self.lamp_frames, self.lamp_dds, self.lamp_subs)):
            lamp.grid(row=0, column=i, sticky="nw", padx=4)
            lamp.set(IDLE, tr("common.stopped"))

        # Rigid bodies
        rf = ttk.LabelFrame(top, text=tr("bridge.rigid_bodies_group"), padding=4)
        rf.grid(row=3, column=0, columnspan=2, sticky="nsew", **pad)
        top.rowconfigure(3, weight=1)
        self.table = RigidBodyTable(rf, height=6)
        self.table.pack(fill="both", expand=True)

        # Log + command line
        lf = ttk.LabelFrame(top, text=tr("common.log"), padding=4)
        lf.grid(row=4, column=0, columnspan=2, sticky="nsew", **pad)
        top.rowconfigure(4, weight=1)
        self.log = LogPane(lf, height=8)
        self.log.pack(fill="both", expand=True)
        self.log.install()

        cf = ttk.Frame(top)
        cf.grid(row=5, column=0, columnspan=2, sticky="we", **pad)
        ttk.Label(cf, text=tr("common.command_line")).pack(side="left")
        ttk.Entry(cf, textvariable=self.cmdline, state="readonly").pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(cf, text=tr("common.copy"), command=self._copy_cmdline).pack(side="left")

        self._sync_buttons()

    def _sync_buttons(self):
        """Set button labels and enabled widgets from the current state."""
        if self._stopping:
            self.start_btn.configure(state="disabled", text=tr("common.stopping"))
        elif self.session:
            self.start_btn.configure(state="normal", text=tr("bridge.stop"))
        else:
            self.start_btn.configure(state="normal", text=tr("bridge.start"))
        mock_on = bool(self.mock and self.mock.running())
        self.mock_btn.configure(text=tr("bridge.mock_stop" if mock_on else "bridge.mock_start"))
        self._set_settings_enabled(not self.session and not self._stopping)

    _stopping = False   # True between pressing Stop and the shutdown finishing

    def _on_language(self, _code):
        log_text = self.log.get_text()
        self.top.destroy()
        self._build()
        self.log.set_text(log_text)
        self._refresh()

    # -- settings ---------------------------------------------------------------

    def _on_transport(self):
        self.mcast_entry.configure(state="normal" if self.v["multicast"].get() and not self.session
                                   else "disabled")

    def _read_config(self):
        """Validate the form. Returns a config dict or raises ValueError."""
        cfg = {}
        for key in ("server", "client", "multicast_address"):
            val = self.v[key].get().strip()
            try:
                socket.inet_aton(val)
                if val.count(".") != 3:
                    raise OSError
            except OSError:
                raise ValueError(tr("bridge.err_ip", value=val))
            cfg[key] = val
        for key, lo, hi, msg in (("command_port", 1, 65535, "bridge.err_command_port"),
                                 ("data_port", 1, 65535, "bridge.err_data_port"),
                                 ("domain", 0, 232, "common.err_domain")):
            try:
                cfg[key] = int(self.v[key].get())
                if not lo <= cfg[key] <= hi:
                    raise ValueError
            except ValueError:
                raise ValueError(tr(msg))
        for key in ("multicast", "reliable", "publish_frames", "publish_rigid_bodies"):
            cfg[key] = bool(self.v[key].get())
        cfg["dds"] = self.v["dds"].get()
        if not (cfg["publish_frames"] or cfg["publish_rigid_bodies"]):
            raise ValueError(tr("bridge.err_no_topic"))
        try:
            cfg["mock_fps"] = max(1, int(float(self.v["mock_fps"].get())))
        except ValueError:
            cfg["mock_fps"] = DEFAULTS["mock_fps"]
        return cfg

    def _save_settings(self, cfg):
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(cfg, f, indent=2)
        except OSError:
            pass

    def _update_cmdline(self):
        g = self.v
        args = ["--server", g["server"].get(), "--client", g["client"].get()]
        if not g["multicast"].get():
            args.append("--unicast")
        elif g["multicast_address"].get() != DEFAULTS["multicast_address"]:
            args += ["--multicast-address", g["multicast_address"].get()]
        if g["command_port"].get() != str(DEFAULTS["command_port"]):
            args += ["--command-port", g["command_port"].get()]
        if g["data_port"].get() != str(DEFAULTS["data_port"]):
            args += ["--data-port", g["data_port"].get()]
        args += ["--dds", g["dds"].get(), "--domain", g["domain"].get()]
        if g["reliable"].get():
            args.append("--reliable")
        if not g["publish_frames"].get():
            args.append("--no-frames")
        if not g["publish_rigid_bodies"].get():
            args.append("--no-rigid-bodies")
        self.cmdline.set(command_line("NatNetToDDS.py", args))

    def _copy_cmdline(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.cmdline.get())

    def _set_settings_enabled(self, enabled):
        for w in self.settings_widgets:
            if w is self.dds_combo:
                w.configure(state="readonly" if enabled else "disabled")
            else:
                w.configure(state="normal" if enabled else "disabled")
        self._on_transport()

    # -- actions ----------------------------------------------------------------

    def _toggle_bridge(self):
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
        self._save_settings(cfg)
        self.table.clear()
        self.last_count, self.last_rate_t, self.fps = 0, time.monotonic(), 0.0
        self.last_error_shown = None
        self.session = BridgeSession(cfg)
        self._sync_buttons()

    def _stopped(self):
        self._stopping = False
        self._sync_buttons()

    def _toggle_mock(self):
        if self.mock and self.mock.running():
            self.mock.stop()
            self.mock = None
            self._sync_buttons()
            return
        try:
            cfg = self._read_config()
        except ValueError as e:
            messagebox.showerror(tr("common.invalid_setting"), str(e), parent=self.root)
            return
        if cfg["server"] not in local_ipv4_addresses():
            if not messagebox.askyesno(tr("bridge.mock_title"),
                                       tr("bridge.mock_remote_question", server=cfg["server"]),
                                       parent=self.root):
                return
        print("[mock] starting MockNatNetServer.py at %d fps (%s)" % (
            cfg["mock_fps"], "multicast" if cfg["multicast"] else "unicast"))
        self.mock = MockServer(cfg, cfg["mock_fps"])
        self._sync_buttons()

    def _on_close(self):
        if self.mock:
            self.mock.stop()
        if self.session:
            self.session.stop(done=lambda: self.root.after(0, self.root.destroy))
            self.session = None
            self.root.after(4000, self.root.destroy)   # don't hang if shutdown stalls
        else:
            self.root.destroy()

    # -- status -----------------------------------------------------------------

    def _tick(self):
        try:
            self._refresh()
        finally:
            self.root.after(250, self._tick)

    def _refresh(self):
        if self.mock and not self.mock.running():
            self.mock = None
            self._sync_buttons()

        s = self.session
        if not s:
            for lamp in (self.lamp_natnet, self.lamp_frames, self.lamp_dds, self.lamp_subs):
                lamp.set(IDLE, tr("common.stopped"))
            return
        s.tick()
        now = time.monotonic()
        c = s.cfg
        b = s.bridge
        transport = tr("common.multicast" if c["multicast"] else "common.unicast")

        # 3. DDS publisher (created first)
        if s.backend and b:
            topics = [t for t, on in ((FRAME_TOPIC, c["publish_frames"]),
                                      (RIGID_BODY_TOPIC, c["publish_rigid_bodies"])) if on]
            self.lamp_dds.set(OK, tr("bridge.dds_ok", backend=s.backend.name, domain=c["domain"],
                                     topics="\n".join(topics)))
        elif s.state == "error" and not s.backend:
            self.lamp_dds.set(BAD, s.error)
        else:
            self.lamp_dds.set(WARN, tr("common.creating_participant"))

        # 1. NatNet connection
        if s.state == "error":
            self.lamp_natnet.set(BAD if s.backend else IDLE, s.error if s.backend else tr("bridge.not_started"))
        elif s.state == "connected":
            ver = s.client.get_server_version()
            nn_ver = s.client.get_nat_net_version_server()
            self.lamp_natnet.set(OK, tr("bridge.natnet_ok", app=s.client.get_application_name(),
                                        version="%d.%d.%d" % tuple(ver[:3]), server=c["server"],
                                        natnet="%d.%d" % tuple(nn_ver[:2]), transport=transport))
        elif s.state == "connecting":
            waited = now - s.started_at
            text = tr("bridge.connecting", seconds=waited)
            if waited > 4:
                text += "\n" + tr("bridge.no_reply", server=c["server"], port=c["command_port"])
            self.lamp_natnet.set(WARN, text)
        else:
            self.lamp_natnet.set(WARN, tr("common.starting"))

        # 2. Incoming frames
        if b:
            dt = now - self.last_rate_t
            if dt >= 1.0:
                self.fps = (b.frames_published - self.last_count) / dt
                self.last_count, self.last_rate_t = b.frames_published, now
            age = (now - b.last_frame_time) if b.last_frame_time else None
            if age is not None and age < 1.0:
                self.lamp_frames.set(OK, tr("bridge.frames_ok", fps=self.fps, frame=b.last_frame_number,
                                            published=b.frames_published))
            elif age is not None:
                self.lamp_frames.set(BAD, tr("bridge.frames_stopped", seconds=age, frame=b.last_frame_number))
            elif s.state == "connected" and now - s.connected_at > 2:
                self.lamp_frames.set(WARN, tr("bridge.frames_none"))
            else:
                self.lamp_frames.set(IDLE, tr("common.waiting"))
            if b.last_error and b.last_error != self.last_error_shown:
                self.last_error_shown = b.last_error
                print("[bridge] error converting frame: %s" % b.last_error)
        else:
            self.lamp_frames.set(IDLE, "")

        # 4. DDS subscribers
        if b:
            counts = []
            if b.frame_writer:
                counts.append(("bridge.subs_frame", b.frame_writer.matched_count()))
            if b.rigid_body_writer:
                counts.append(("bridge.subs_rigid_body", b.rigid_body_writer.matched_count()))
            detail = tr("common.list_separator").join(tr(k, count=n) for k, n in counts)
            if any(n for _, n in counts):
                self.lamp_subs.set(OK, detail)
            else:
                self.lamp_subs.set(WARN, detail + "\n" + tr("bridge.subs_none", domain=c["domain"]))
            self.table.update_rows(b.latest_rigid_bodies)
        else:
            self.lamp_subs.set(IDLE, "")


def main():
    load_saved_language()
    root = tk.Tk()
    if sys.platform.startswith("linux"):
        ttk.Style(root).theme_use("clam")
    BridgeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
