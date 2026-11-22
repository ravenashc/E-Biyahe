"""The connection to the jeep and the messages that come back (events).

This is one part of the App window: App (app.py) inherits LinkMixin, so these methods are called as self.<name>()."""

from config import DEFAULT_HOST, DEFAULT_PORT, DWELL_S
from helpers import save_setting, to_float
from map_data import N
from sources import DemoSource, TcpSource


# ======================= THE LINK TO THE JEEP =======================
class LinkMixin:
    """The connection to the jeep and the messages that come back (events)."""

    # ---------- events from the jeep ----------
    def on_event(self, m, now):
        ev = m.get("ev")

        def nm(i):
            return self.names[i] if isinstance(i, int) and 0 <= i < N else "?"

        if ev == "ARRIVED":
            self.log_add(f"Arrived at {nm(m.get('stop'))}")
        elif ev == "DEPARTED":
            self.log_add(f"Left {nm(m.get('stop'))}")
        elif ev == "TAG_PASS":
            self.log_add(f"Passed {nm(m.get('stop'))} without stopping")
        elif ev == "OBSTACLE":
            self.log_add(f"Obstacle detected ({m.get('dist', '?')} cm): jeep stopped", "danger")
        elif ev == "OBSTACLE_CLEAR":
            self.log_add("Obstacle cleared: jeep moving again", "ok")
        elif ev == "FAULT":
            self.log_add("FAULT: line lost. Put the jeep back on the line, then press Reset", "danger")
        elif ev == "ESTOP":
            self.log_add("EMERGENCY STOP", "danger")
        elif ev == "RESET":
            self.log_add("Reset")
        elif ev == "DISPATCHED":
            self.log_add("Jeep left the depot")
        elif ev == "PARKED":
            self.log_add("Jeep parked at the depot")
        elif ev == "BATT_OK":
            self.log_add("Battery recharged: service resumed", "ok")
        elif ev in ("LOW_BATT", "RETURNING"):
            why = "low battery" if ev == "LOW_BATT" else "return to depot ordered"
            volts = f" ({m.get('batt')} V)" if ev == "LOW_BATT" else ""
            self.log_add(f"{why.capitalize()}{volts}: returning to the depot", "warn")

    # ---------- connection ----------
    def toggle_connection(self):
        if self.source:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        if self.mode_var.get() == "demo":
            self.source = DemoSource(self.q)
        else:
            self.source = TcpSource(DEFAULT_HOST, DEFAULT_PORT, self.q)       # the jeep's own Wi-Fi: the address is in config.py
        self.tr.clear()
        self.tr.connected = False
        self.source.start()
        save_setting("connection", {"mode": self.mode_var.get()})      # the next start connects the same way
        self.btn_conn.config(text="Disconnect")
        self.log_add("Connecting (" + ("demo" if self.mode_var.get() == "demo" else f"{DEFAULT_HOST}:{DEFAULT_PORT}") + ")")

    def disconnect(self):
        if self.source:
            self.source.stop()
            self.source = None
            self.log_add("Disconnected")
        self.tr.connected = False
        self.btn_conn.config(text="Connect")

    def on_link(self, up):
        if up == self.tr.connected:
            return
        self.tr.connected = up
        if up:
            self.tr.clear()
            self.log_add("Connected to the jeep", "ok")
            self.show_message("Connected to the jeep.", "ok")
            self.send({"cmd": "mode", "value": "patrol"})          # the jeep only patrols: it stops at every station
            self.send({"cmd": "dwell", "value": to_float(self.dwell_var.get(), DWELL_S)})
        elif self.source:
            self.log_add("Connection lost", "warn")
            self.show_message("Connection to the jeep lost. Trying again...", "warn")

    def on_close(self):
        self.disconnect()
        self.destroy()
