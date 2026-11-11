"""Rolling stream statistics shared by the bridge and the test client.

StreamStats keeps the last `window_s` seconds of arrivals and reports:

  * rate         - samples per second as they arrived here (per stream)
  * source rate  - frame rate according to the source's own timestamps
                   (Motive's frame timestamp), independent of network jitter
  * interval     - mean / standard deviation / max time between arrivals
  * loss         - gaps in frame numbers within the window and since start
  * latency      - mean / max of a caller-supplied latency per sample

A "stream" is identified by an optional key. The frame topic is one stream;
the rigid body topic is one stream per rigid body id, so gaps are counted per
body. Thread-safe: record() is called from a network thread while
snapshot() is called from the UI or report thread.
"""
import math
import threading
import time
from collections import deque, namedtuple
from datetime import datetime, timezone

DEFAULT_WINDOW_S = 10.0

Snapshot = namedtuple("Snapshot", [
    "window_s",          # length of the window used (seconds)
    "rate_hz",           # arrivals per second per stream, None if < 2 samples
    "source_rate_hz",    # frames per second from source timestamps, None if unknown
    "interval_mean_ms", "interval_std_ms", "interval_max_ms",
    "missed_window",     # frames missing (frame number gaps) within the window
    "received_window",   # samples received within the window
    "loss_percent_window",
    "missed_total", "received_total", "out_of_order_total",
    "latency_mean_ms", "latency_max_ms",   # None if no latency samples in the window
])


class StreamStats:
    def __init__(self, window_s=DEFAULT_WINDOW_S, clock=time.monotonic):
        self.window_s = float(window_s)
        self._clock = clock
        self._lock = threading.Lock()
        self._arrivals = deque()    # (t, key, frame_number, source_time_s)
        self._gaps = deque()        # (t, frames missed)
        self._latency = deque()     # (t, latency seconds)
        self._last_frame = {}       # key -> last frame number
        self._last_arrival = {}     # key -> t of the previous sample
        self._intervals = deque()   # (t, seconds since the previous sample of the same key)
        self.received_total = 0
        self.missed_total = 0
        self.out_of_order_total = 0

    def record(self, frame_number, key=None, source_time_s=None, latency_s=None, now=None):
        """Record one sample. Returns the number of frames missed before it."""
        t = self._clock() if now is None else now
        missed = 0
        with self._lock:
            self.received_total += 1
            last = self._last_frame.get(key)
            if last is not None:
                if frame_number > last + 1:
                    missed = frame_number - last - 1
                    self.missed_total += missed
                    self._gaps.append((t, missed))
                elif frame_number <= last:
                    self.out_of_order_total += 1   # also when Motive playback loops
            self._last_frame[key] = frame_number
            prev = self._last_arrival.get(key)
            if prev is not None:
                self._intervals.append((t, t - prev))
            self._last_arrival[key] = t
            self._arrivals.append((t, key, frame_number, source_time_s))
            if latency_s is not None:
                self._latency.append((t, latency_s))
            self._trim(t)
        return missed

    def _trim(self, now):
        horizon = now - self.window_s
        for q in (self._arrivals, self._gaps, self._latency, self._intervals):
            while q and q[0][0] < horizon:
                q.popleft()

    def snapshot(self, now=None):
        t = self._clock() if now is None else now
        with self._lock:
            self._trim(t)
            arrivals = list(self._arrivals)
            gaps = sum(n for _, n in self._gaps)
            intervals = [d for _, d in self._intervals]
            latencies = [x for _, x in self._latency]
            totals = (self.missed_total, self.received_total, self.out_of_order_total)

        rate = None
        keys = {a[1] for a in arrivals}
        if len(arrivals) >= 2 and keys:
            span = arrivals[-1][0] - arrivals[0][0]
            if span > 0:
                rate = (len(arrivals) - len(keys)) / span / len(keys)

        # Source rate: median source time per frame between consecutive
        # samples of the most recent stream. The median ignores restarts,
        # playback loops and frames decoded before the NatNet version was known.
        source_rate = None
        if arrivals:
            key = arrivals[-1][1]
            same = [a for a in arrivals if a[1] == key and a[3] is not None]
            per_frame = sorted((b[3] - a[3]) / (b[2] - a[2]) for a, b in zip(same, same[1:])
                               if b[2] > a[2] and b[3] > a[3])
            if per_frame:
                source_rate = 1.0 / per_frame[len(per_frame) // 2]

        if intervals:
            mean = sum(intervals) / len(intervals)
            std = math.sqrt(sum((x - mean) ** 2 for x in intervals) / len(intervals))
            interval = (mean * 1e3, std * 1e3, max(intervals) * 1e3)
        else:
            interval = (None, None, None)

        received = len(arrivals)
        loss = 100.0 * gaps / (received + gaps) if received + gaps else 0.0
        lat = ((sum(latencies) / len(latencies) * 1e3, max(latencies) * 1e3)
               if latencies else (None, None))
        return Snapshot(self.window_s, rate, source_rate, *interval, gaps, received, loss,
                        *totals, *lat)


def format_utc_ns(ns):
    """Wall-clock nanoseconds since the UNIX epoch -> 'YYYY-MM-DD HH:MM:SS.ffffff UTC'."""
    if not ns:
        return "—"
    dt = datetime.fromtimestamp(ns // 1_000_000_000, tz=timezone.utc)
    return "%s.%06d UTC" % (dt.strftime("%Y-%m-%d %H:%M:%S"), (ns % 1_000_000_000) // 1000)


def fmt(value, spec="%.1f", none="—"):
    """Format an optional number."""
    return none if value is None else spec % value
