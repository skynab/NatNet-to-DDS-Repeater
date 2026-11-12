"""Small Tkinter helpers shared by NatNetToDDSGui.py and DDSTestClientGui.py.

Tkinter ships with Python, so the GUIs need no extra packages.
"""
import json
import queue
import socket
import sys
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from .i18n import available_languages, current_language, save_language, tr

# Status lamp colors
OK, WARN, BAD, IDLE = "#2ecc40", "#ffb000", "#e5383b", "#9a9a9a"


def local_ipv4_addresses():
    """Best-effort list of this machine's IPv4 addresses, loopback first."""
    found = ["127.0.0.1"]
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.append(info[4][0])
    except OSError:
        pass
    # The interface the OS would use for multicast. connect() on a UDP socket
    # only picks a route; no packet is sent.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("239.255.42.99", 1511))
            found.append(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    result = []
    for ip in found:
        if ip not in result and ip != "0.0.0.0":
            result.append(ip)
    return result


class Lamp(ttk.Frame):
    """A colored dot with a title and a detail line."""

    def __init__(self, master, title):
        super().__init__(master)
        self._dot = tk.Canvas(self, width=16, height=16, highlightthickness=0, bd=0)
        self._oval = self._dot.create_oval(2, 2, 14, 14, fill=IDLE, outline="")
        self._dot.grid(row=0, column=0, rowspan=2, padx=(0, 6), sticky="n", pady=2)
        ttk.Label(self, text=title, font=("TkDefaultFont", 0, "bold")).grid(row=0, column=1, sticky="w")
        self._detail = ttk.Label(self, text="", foreground="#555555", wraplength=260, justify="left")
        self._detail.grid(row=1, column=1, sticky="w")

    def set(self, color, detail=""):
        self._dot.itemconfigure(self._oval, fill=color)
        self._detail.configure(text=detail)


class LogPane(ttk.Frame):
    """Read-only scrolling log that also captures print() output.

    install() redirects sys.stdout/sys.stderr so messages printed by the
    bridge, the SDK client or the DDS backend (from any thread) show up here
    as well as in the console.
    """

    MAX_LINES = 2000

    def __init__(self, master, height=8):
        super().__init__(master)
        self.text = ScrolledText(self, height=height, wrap="none", state="disabled",
                                 font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True)
        self._queue = queue.Queue()
        self._after_id = self.after(100, self._drain)

    def write(self, msg):
        self._queue.put(msg)

    def get_text(self):
        """Everything logged so far, including messages not yet shown."""
        self._drain(reschedule=False)
        return self.text.get("1.0", "end-1c")

    def set_text(self, text):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", text)
        self.text.see("end")
        self.text.configure(state="disabled")

    def destroy(self):
        self.after_cancel(self._after_id)
        super().destroy()

    def install(self):
        pane = self

        class _Tee:
            def __init__(self, stream):
                self._stream = stream

            def write(self, msg):
                pane.write(msg)
                if self._stream:
                    try:
                        self._stream.write(msg)
                    except Exception:  # noqa: BLE001 - e.g. no console (pythonw)
                        pass

            def flush(self):
                if self._stream:
                    try:
                        self._stream.flush()
                    except Exception:  # noqa: BLE001
                        pass

        sys.stdout = _Tee(sys.__stdout__)
        sys.stderr = _Tee(sys.__stderr__)

    def _drain(self, reschedule=True):
        chunks = []
        try:
            while True:
                chunks.append(self._queue.get_nowait())
        except queue.Empty:
            pass
        if chunks:
            self.text.configure(state="normal")
            self.text.insert("end", "".join(chunks))
            lines = int(self.text.index("end-1c").split(".")[0])
            if lines > self.MAX_LINES:
                self.text.delete("1.0", "%d.0" % (lines - self.MAX_LINES))
            self.text.see("end")
            self.text.configure(state="disabled")
        if reschedule:
            self._after_id = self.after(100, self._drain)


class RigidBodyTable(ttk.Frame):
    """Treeview listing rigid body poses, one row per id."""

    # (column, title or translation id, width)
    COLUMNS = (("id", "table.id", 40), ("name", "table.name", 110), ("x", "X", 70), ("y", "Y", 70),
               ("z", "Z", 70), ("qx", "qx", 64), ("qy", "qy", 64), ("qz", "qz", 64), ("qw", "qw", 64),
               ("err", "table.error", 76), ("state", "table.tracking", 76))

    def __init__(self, master, height=6):
        super().__init__(master)
        self.tree = ttk.Treeview(self, columns=[c[0] for c in self.COLUMNS], show="headings", height=height)
        for key, title, width in self.COLUMNS:
            self.tree.heading(key, text=tr(title) if title.startswith("table.") else title)
            self.tree.column(key, width=width, anchor="w" if key == "name" else "e", stretch=key == "name")
        self.tree.tag_configure("lost", foreground=BAD)
        self.tree.tag_configure("stale", foreground=IDLE)
        self.tree.pack(fill="both", expand=True)

    def update_rows(self, bodies, stale_ids=()):
        """bodies: iterable of objects with id, name, position, orientation,
        mean_error and tracking_valid (RigidBodyPose or RigidBody)."""
        seen = set()
        for rb in sorted(bodies, key=lambda r: r.id):
            iid = str(rb.id)
            seen.add(iid)
            p, q = rb.position, rb.orientation
            stale = rb.id in stale_ids
            values = (rb.id, rb.name or "?", "%.4f" % p.x, "%.4f" % p.y, "%.4f" % p.z,
                      "%.4f" % q.x, "%.4f" % q.y, "%.4f" % q.z, "%.4f" % q.w,
                      "%.2f" % (rb.mean_error * 1000.0),
                      tr("table.stale") if stale else tr("table.tracked" if rb.tracking_valid else "table.lost"))
            tags = ("stale",) if stale else (() if rb.tracking_valid else ("lost",))
            if self.tree.exists(iid):
                self.tree.item(iid, values=values, tags=tags)
            else:
                self.tree.insert("", "end", iid=iid, values=values, tags=tags)
        for iid in self.tree.get_children():
            if iid not in seen:
                self.tree.delete(iid)

    def clear(self):
        self.tree.delete(*self.tree.get_children())


class Section(ttk.LabelFrame):
    """A LabelFrame whose title collapses and expands its contents.

    Put child widgets in `section.body`, not in the section itself. Click the
    title (or focus it with Tab and press Space/Return) to toggle. When
    collapsed, the section gives up its grid row's stretch so the other
    sections can use the space. on_toggle(key, expanded) is called after a
    toggle, e.g. to remember the state.
    """

    def __init__(self, master, title, key=None, expanded=True, on_toggle=None, padding=8):
        self._title = title
        self._header = ttk.Label(master, cursor="hand2", takefocus=1)
        super().__init__(master, labelwidget=self._header)
        self.key = key
        self._padding = padding
        self._on_toggle = on_toggle
        self._expanded = True
        self._grid_saved = None     # (row weight, sticky) while collapsed
        self.body = ttk.Frame(self, padding=padding)
        self.body.pack(fill="both", expand=True)
        # Packed in place of the body while collapsed, so the frame shrinks
        # to its title (Tk keeps a frame's old size when it has no children).
        self._stub = ttk.Frame(self, height=0)
        for seq in ("<Button-1>", "<space>", "<Return>"):
            self._header.bind(seq, lambda _e: self.toggle())
        self._update_header()
        if not expanded:
            # Collapse once gridded, so the row can be released.
            self.after_idle(lambda: self.set_expanded(False, notify=False))

    @property
    def expanded(self):
        return self._expanded

    def toggle(self):
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded, notify=True):
        if expanded == self._expanded:
            return
        self._expanded = expanded
        info = self.grid_info()
        if expanded:
            self._stub.pack_forget()
            self.body.pack(fill="both", expand=True)
            if info and self._grid_saved:
                weight, sticky = self._grid_saved
                self.master.rowconfigure(info["row"], weight=weight)
                self.grid_configure(sticky=sticky)
            self._grid_saved = None
        else:
            self.body.pack_forget()
            self._stub.pack(fill="x")
            if info:
                self._grid_saved = (self.master.rowconfigure(info["row"])["weight"], info["sticky"])
                if not any(isinstance(w, Section) and w is not self and w.expanded
                           and w.grid_info().get("row") == info["row"]
                           for w in self.master.grid_slaves()):
                    self.master.rowconfigure(info["row"], weight=0)
                self.grid_configure(sticky=info["sticky"].replace("s", ""))
        self._update_header()
        if notify and self._on_toggle:
            self._on_toggle(self.key, expanded)

    def _update_header(self):
        self._header.configure(text=("▾ " if self._expanded else "▸ ") + self._title)


class MetricsPanel(ttk.Frame):
    """Grid of metric rows: a title column plus one value column per stream.

    rows: [(row key, title)], columns: optional column headings."""

    def __init__(self, master, rows, columns=None):
        super().__init__(master)
        self._values = {}
        n_cols = len(columns) if columns else 1
        first = 0
        if columns:
            for c, heading in enumerate(columns):
                ttk.Label(self, text=heading, font=("TkDefaultFont", 0, "bold")).grid(
                    row=0, column=1 + c, sticky="w", padx=(0, 16))
            first = 1
        for r, (key, title) in enumerate(rows):
            ttk.Label(self, text=title, foreground="#555555").grid(
                row=first + r, column=0, sticky="nw", padx=(0, 12), pady=1)
            for c in range(n_cols):
                lbl = ttk.Label(self, text="—", justify="left")
                lbl.grid(row=first + r, column=1 + c, sticky="nw", padx=(0, 16), pady=1)
                self._values[(key, c)] = lbl
        for c in range(n_cols):
            self.columnconfigure(1 + c, weight=1, uniform="metric")

    def set(self, key, text, column=0):
        self._values[(key, column)].configure(text=text)

    def clear(self):
        for lbl in self._values.values():
            lbl.configure(text="—")


class LanguagePicker(ttk.Frame):
    """Language menu. Each language is listed by its own name, so it can be
    found whatever language the window is in. Calls on_change(code)."""

    def __init__(self, master, on_change):
        super().__init__(master)
        self._langs = available_languages()
        names = [name for _, name in self._langs]
        current = dict(self._langs).get(current_language(), names[0] if names else "")
        self._var = tk.StringVar(value=current)
        ttk.Label(self, text=tr("common.language")).pack(side="left", padx=(0, 4))
        box = ttk.Combobox(self, textvariable=self._var, values=names, state="readonly",
                           width=max([8] + [len(n) + 2 for n in names]))
        box.pack(side="left")
        box.bind("<<ComboboxSelected>>", lambda _e: self._picked(on_change))

    def _picked(self, on_change):
        code = {name: c for c, name in self._langs}.get(self._var.get())
        if code and code != current_language():
            save_language(code)
            on_change(code)


def labeled(parent, row, text, widget, column=0, **grid):
    """Grid a label + widget pair and return the widget."""
    ttk.Label(parent, text=text).grid(row=row, column=column, sticky="w", padx=(0, 6), pady=2)
    widget.grid(row=row, column=column + 1, sticky="we", pady=2, **grid)
    return widget


def command_line(script, args):
    """Format an equivalent CLI command for display/copying."""
    parts = ["python", script]
    for a in args:
        parts.append('"%s"' % a if " " in a else a)
    return " ".join(parts)


def stats_texts(st):
    """Translated value strings for a natnet_dds.metrics.Snapshot."""
    from .metrics import fmt
    return {
        "rate": tr("metrics.rate_value", rate=fmt(st.rate_hz), source=fmt(st.source_rate_hz)),
        "interval": tr("metrics.interval_value", mean=fmt(st.interval_mean_ms, "%.2f"),
                       std=fmt(st.interval_std_ms, "%.2f"), max=fmt(st.interval_max_ms, "%.2f")),
        "loss": tr("metrics.loss_value", missed=st.missed_window, window=st.window_s,
                   percent=st.loss_percent_window, total=st.missed_total,
                   out_of_order=st.out_of_order_total),
        "latency": tr("metrics.latency_value", mean=fmt(st.latency_mean_ms, "%.2f"),
                      max=fmt(st.latency_max_ms, "%.2f")),
    }


def parse_window(text):
    """Validate the metrics window setting (seconds). Raises ValueError."""
    try:
        value = float(text)
        if not 1 <= value <= 3600:
            raise ValueError
    except ValueError:
        raise ValueError(tr("metrics.err_window"))
    return value


def merge_settings(path, updates):
    """Update keys in a JSON settings file, keeping the keys already there."""
    data = {}
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        pass
    data.update(updates)
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass
