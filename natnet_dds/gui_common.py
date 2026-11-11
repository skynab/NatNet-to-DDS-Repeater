"""Small Tkinter helpers shared by NatNetToDDSGui.py and DDSTestClientGui.py.

Tkinter ships with Python, so the GUIs need no extra packages.
"""
import queue
import socket
import sys
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

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
        self.after(100, self._drain)

    def write(self, msg):
        self._queue.put(msg)

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

    def _drain(self):
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
        self.after(100, self._drain)


class RigidBodyTable(ttk.Frame):
    """Treeview listing rigid body poses, one row per id."""

    COLUMNS = (("id", "ID", 40), ("name", "Name", 110), ("x", "X", 70), ("y", "Y", 70), ("z", "Z", 70),
               ("qx", "qx", 64), ("qy", "qy", 64), ("qz", "qz", 64), ("qw", "qw", 64),
               ("err", "Error (mm)", 76), ("state", "Tracking", 76))

    def __init__(self, master, height=6):
        super().__init__(master)
        self.tree = ttk.Treeview(self, columns=[c[0] for c in self.COLUMNS], show="headings", height=height)
        for key, title, width in self.COLUMNS:
            self.tree.heading(key, text=title)
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
                      "stale" if stale else ("tracked" if rb.tracking_valid else "LOST"))
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
