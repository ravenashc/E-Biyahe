"""The two messengers that bring jeep messages to the app: DemoSource (pretend jeep) and
TcpSource (the real jeep over Wi-Fi). Each runs on its own thread and drops messages in a queue."""

import json
import queue
import socket
import threading
import time

from sim import JeepSim


# ======================= DATA SOURCES =======================
class DemoSource(threading.Thread):
    """Runs a JeepSim and sends the same messages as the real jeep."""

    def __init__(self, q):
        super().__init__(daemon=True)
        self.q = q
        self.halt = threading.Event()
        self.cmds = queue.Queue()
        self.sim = JeepSim()
        self.down_until = 0.0                    # simulated Wi-Fi drop

    def send(self, obj):
        self.cmds.put(obj)

    def stop(self):
        self.halt.set()

    def run(self):
        self.q.put(("conn", True))
        up, last, last_status = True, time.time(), 0.0
        while not self.halt.is_set():
            now = time.time()
            dt, last = min(now - last, 0.5), now
            link = now >= self.down_until
            while True:
                try:
                    c = self.cmds.get_nowait()
                except queue.Empty:
                    break
                if c.get("cmd") == "sim" and c.get("what") == "wifi":
                    self.down_until, link = now + 8.0, False
                elif link:
                    self.sim.command(c)              # commands sent while the link is down are lost
            if link != up:
                up = link
                self.q.put(("conn", up))
            self.sim.step(dt)
            out, self.sim.out = self.sim.out, []
            if link:                                 # the jeep keeps running while the link is down
                for m in out:
                    self.q.put(("msg", m))
                if self.sim.dirty or now - last_status >= 1.0:
                    self.q.put(("msg", self.sim.status()))
                    self.sim.dirty, last_status = False, now
            self.halt.wait(0.1)
        self.q.put(("conn", False))


class TcpSource(threading.Thread):
    """Reads JSON lines from the jeep over Wi-Fi (TCP). Reconnects by itself."""

    def __init__(self, host, port, q):
        super().__init__(daemon=True)
        self.host, self.port, self.q = host, port, q
        self.halt = threading.Event()
        self.sock = None
        self.lock = threading.Lock()

    def send(self, obj):
        with self.lock:
            if self.sock:
                try:
                    self.sock.sendall((json.dumps(obj) + "\n").encode())
                except OSError:
                    pass

    def stop(self):
        self.halt.set()
        with self.lock:
            if self.sock:
                try:
                    self.sock.close()
                except OSError:
                    pass

    def run(self):
        while not self.halt.is_set():
            try:
                s = socket.create_connection((self.host, self.port), timeout=4)
                s.settimeout(1.0)
                with self.lock:
                    self.sock = s
                self.q.put(("conn", True))
                buf = b""
                while not self.halt.is_set():
                    try:
                        data = s.recv(1024)
                    except socket.timeout:
                        continue
                    if not data:
                        break
                    buf += data
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        try:
                            msg = json.loads(line.decode("utf-8", "ignore"))
                        except ValueError:
                            continue
                        if isinstance(msg, dict):
                            self.q.put(("msg", msg))
            except OSError:
                pass
            finally:
                with self.lock:
                    if self.sock:
                        try:
                            self.sock.close()
                        except OSError:
                            pass
                    self.sock = None
                self.q.put(("conn", False))
            self.halt.wait(2.0)
