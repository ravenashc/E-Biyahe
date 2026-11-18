"""The connection to the jeep and the messages that come back (events and bookings sync).

This is one part of the App window: App (app.py) inherits LinkMixin, so these methods are called as self.<name>()."""

from config import DWELL_S, REQUEST_GRACE_S
from helpers import int_list, save_setting, stop_label, to_float
from map_data import N
from sources import DemoSource, TcpSource


# ======================= THE LINK TO THE JEEP =======================
class LinkMixin:
    """The connection to the jeep and the messages that come back (events and bookings sync)."""

    # ---------- events from the jeep ----------
    def on_event(self, m, now):
        ev = m.get("ev")

        def nm(i):
            return self.names[i] if isinstance(i, int) and 0 <= i < N else "?"

        if ev == "ARRIVED":
            self.log_add(f"Arrived at {nm(m.get('stop'))}: {stop_label(bool(m.get('load')), bool(m.get('unload')))}")
        elif ev == "DEPARTED":
            self.log_add(f"Left {nm(m.get('stop'))}")
        elif ev == "TAG_PASS":
            self.log_add(f"Passed {nm(m.get('stop'))} (nobody to pick up or drop off)")
        elif ev == "PARA":
            if m.get("ok", True):
                self.log_add("Para pressed: the jeep will stop at the next station", "ok")
                self.show_message("Para accepted: the jeep will stop at the next station.", "ok")
            else:
                self.log_add("Para ignored: the jeep is parked", "warn")
                self.show_message("Para ignored: the jeep is parked.", "warn")
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
        elif ev == "MODE":
            self.log_add("Service mode: " + ("Patrol" if m.get("patrol") else "On-demand"))
        elif ev in ("LOW_BATT", "RETURNING"):
            why = "low battery" if ev == "LOW_BATT" else "return to depot ordered"
            ids = int_list(m.get("cancelled"))
            for bid in ids:
                b = self.book_by_id(bid)
                if b and b.active:
                    b.status, b.note = "CANCELLED", why
            extra = f"{len(ids)} pending pickup(s) cancelled, " if ids else ""
            volts = f" ({m.get('batt')} V)" if ev == "LOW_BATT" else ""
            self.log_add(f"{why.capitalize()}{volts}: {extra}returning to the depot", "warn")
            if ids:
                self.show_message(f"Ride(s) {', '.join('#' + str(i) for i in ids)} cancelled: the jeep is returning to the depot.", "warn")
        elif ev == "REJECTED":
            b = self.book_by_id(m.get("id"))
            if b and b.active:
                b.status, b.note = "REJECTED", str(m.get("reason", ""))
            self.show_message("Rejected by the jeep: " + str(m.get("reason", "")), "error")
            self.log_add(f"Ride #{m.get('id')} rejected by the jeep: {m.get('reason', '')}", "warn")
        elif ev == "CANCELLED":
            b = self.book_by_id(m.get("id"))
            if b is None:
                return
            if m.get("ok"):
                if b.active:
                    b.status, b.note = "CANCELLED", "by you"
                self.show_message(f"Ride #{b.id} cancelled.", "ok")
                self.log_add(f"Ride #{b.id} cancelled by the passenger")
            else:
                self.show_message(f"Too late: ride #{b.id} is already on board.", "warn")

    def sync_bookings(self, now):
        """Bring the bookings in line with the jeep's wait/ride lists (the jeep is the truth)."""
        wait, ride = set(self.tr.wait_ids), set(self.tr.ride_ids)
        for b in self.bookings:
            if not b.active:
                continue
            if b.id in ride:
                if b.status != "BOARDED":
                    b.status = "BOARDED"
                    self.log_add(f"Ride #{b.id} boarded at {self.names[b.pickup]}")
            elif b.id in wait:
                continue
            elif b.status == "BOARDED":
                b.status = "COMPLETED"
                self.log_add(f"Ride #{b.id} completed at {self.names[b.drop]}", "ok")
            elif now - b.sent > REQUEST_GRACE_S:                      # the jeep no longer has it
                b.status, b.note = "CANCELLED", "dropped by the jeep"
                self.log_add(f"Ride #{b.id} is no longer on the jeep's list: cancelled", "warn")

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
            host = self.host_var.get().strip()
            if not host:
                self.show_message("Enter the jeep's host address.", "error")
                return
            try:
                port = int(self.port_var.get())
            except ValueError:
                self.show_message("Port must be a number.", "error")
                return
            if not 1 <= port <= 65535:
                self.show_message("Port must be between 1 and 65535.", "error")
                return
            self.source = TcpSource(host, port, self.q)
        self.tr.clear()
        self.tr.connected = False
        self.source.start()
        save_setting("connection", {"mode": self.mode_var.get(), "host": self.host_var.get().strip(),
                                    "port": self.port_var.get().strip()})      # the next start connects the same way
        self.btn_conn.config(text="Disconnect")
        self.log_add("Connecting (" + ("demo" if self.mode_var.get() == "demo" else self.host_var.get().strip()) + ")")

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
            self.send({"cmd": "sync", "ids": [b.id for b in self.bookings if b.active]})
            self.send({"cmd": "mode", "value": self.svc_var.get()})
            self.send({"cmd": "dwell", "value": to_float(self.dwell_var.get(), DWELL_S)})
        elif self.source:
            self.log_add("Connection lost", "warn")
            self.show_message("Connection to the jeep lost. Trying again...", "warn")

    def on_close(self):
        self.disconnect()
        self.destroy()
