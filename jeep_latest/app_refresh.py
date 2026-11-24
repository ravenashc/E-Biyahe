"""The update that runs four times a second: refreshes every screen from the Tracker's data.

This is one part of the App window: App (app.py) inherits RefreshMixin, so these methods are called as self.<name>()."""

import queue
import time
from datetime import datetime

from config import CLOSE_TIME, CURRENCY, OPEN_TIME, STALE_S
from helpers import batt_pct, fare_for, fmt12, fmt_clock, fmt_dur, set_enabled
from map_data import N, STATE_COLOR, STATE_TEXT
from roles import PASSENGER
from sources import DemoSource
from theme import PALETTE


# ======================= PERIODIC UPDATE =======================
class RefreshMixin:
    """The update that runs four times a second: refreshes every screen from the Tracker's data."""

    # ---------- periodic update ----------
    def refresh_controls(self, now):
        """Enable each button only while its action can work, so people are not told 'no' after clicking.
        The emergency stop is never disabled."""
        tr = self.tr
        online = self.fresh(now)
        on_road = online and not tr.depot          # the jeep is out driving, not parked at the terminal
        stopped = online and tr.state == "EMERGENCY_STOP"      # locked: nothing can move the jeep again until Reset is pressed

        off = self.offline_reason()
        locked = "Emergency stop active: press Reset first."

        # ----- Operator: Dispatch, Return and Reset (Emergency stop is left alone) -----
        # While the jeep is in EMERGENCY_STOP, only Reset is enabled. The keyboard shortcuts press these same buttons,
        # so they are locked out too.
        can_dispatch = online and tr.state == "PARKED" and not tr.paused
        set_enabled(self.btn_dispatch, can_dispatch)
        self.set_hint(self.lbl_dispatch_hint, "" if can_dispatch else off if not online else locked if stopped else
                      "The jeep is already out on the road." if tr.state != "PARKED" else "Paused: low battery.")
        can_return = on_road and not tr.paused and not stopped
        set_enabled(self.btn_return, can_return)
        self.set_hint(self.lbl_return_hint, "" if can_return else off if not online else locked if stopped else
                      "The jeep is already at the terminal." if tr.depot else "Already returning to the terminal.")
        can_reset = online and tr.state in ("EMERGENCY_STOP", "LINE_LOST")
        set_enabled(self.btn_reset, can_reset)
        self.set_hint(self.lbl_reset_hint, "" if can_reset else off if not online else "No fault or emergency stop to reset.")

    def offline_reason(self):
        """Why a button is off when the jeep cannot be reached, worded for who is looking at it."""
        return "The service is unavailable right now." if self.role == PASSENGER else "No connection to the jeep."

    @staticmethod
    def set_hint(label, text):
        """Show `text` in a hint label directly under a button (blank when there is nothing to say)."""
        label.config(text=text)                   # the label stays in place (its row keeps its height), so nothing below it moves

    def tick(self):
        now = time.time()
        self.check_idle(now)                          # Operator mode signs out after a long quiet time
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "conn":
                    self.on_link(val)
                elif kind == "msg" and isinstance(val, dict):
                    if val.get("type") == "event":
                        self.on_event(val, now)
                    else:
                        self.tr.update(val, now)
        except queue.Empty:
            pass
        self.tr.update_frac(now)
        self.refresh_status(now)
        self.refresh_trip(now)
        self.refresh_schedule(now)
        self.refresh_operator(now)
        self.refresh_controls(now)
        self.draw_dynamic(now)
        self.after(250, self.tick)

    def fresh(self, now):
        return self.tr.connected and now - self.tr.last_msg <= STALE_S

    def do_estop(self):
        """EMERGENCY STOP, from the red button, the Operator menu or the keyboard.
        When the jeep already reports an emergency stop, the press is ignored: there is nothing left to stop, so nothing
        is sent and nothing is logged again. Without current data from the jeep the press goes to op(), which says
        so and points to the toggle switch on the jeep."""
        if self.fresh(time.time()) and self.tr.state == "EMERGENCY_STOP":
            self.show_message("The jeep is already in emergency stop. Press Reset to continue.", "info")
            return
        self.op("estop")

    def state_text(self):
        tr = self.tr
        if tr.state == "LOADING_UNLOADING":
            return "At station"
        return STATE_TEXT.get(tr.state, tr.state)

    def refresh_status(self, now):
        """Update the connection line and the status card from the Tracker's latest data."""
        tr = self.tr

        # ----- connection line (Connection box) -----
        if not self.source:
            self.v_conn.set("Not connected")
        elif not tr.connected:
            self.v_conn.set("Connecting...")
        elif not self.fresh(now):
            self.v_conn.set("Connected, but no data from the jeep")
        else:
            demo = isinstance(self.source, DemoSource)
            self.v_conn.set("Connected" + (" (demo jeep)" if demo else "") + f" - last update {now - tr.last_msg:.0f} s ago")

        # ----- offline: show placeholders and stop here -----
        if not self.fresh(now):
            self.badge.set("Offline", PALETTE["muted"])
            self.v_next.set("-")
            self.v_eta.set("-")
            if self.role == PASSENGER:
                self.show_alert("The service is unavailable right now. Please try again in a moment.", "warn")
            else:
                self.show_alert("No connection to the jeep." if self.source else "", "warn")
            return

        # ----- state badge and next station -----
        self.badge.set(self.state_text(), STATE_COLOR.get(tr.state, PALETTE["muted"]))
        self.v_next.set("-" if tr.state == "PARKED" else self.short_names[tr.next_stop])

        # ----- arrival time -----
        eta = tr.eta_to_next(now)
        if eta is None:
            self.v_eta.set("-" if tr.state == "PARKED" else "paused")
        else:
            self.v_eta.set("arriving" if eta < 1 else fmt_dur(eta))

        # ----- alert line: red for danger, amber for caution -----
        if tr.state == "EMERGENCY_STOP":
            self.show_alert("EMERGENCY STOP. Press Reset (Operator tab) to continue.", "danger")
        elif tr.state == "LINE_LOST":
            self.show_alert("FAULT: line lost. Put the jeep back on the line, then press Reset.", "danger")
        elif tr.state == "OBSTACLE_HOLD":
            self.show_alert("Obstacle ahead: waiting for it to clear.", "warn")
        elif tr.paused:
            self.show_alert("LOW BATTERY: returning to the terminal." if tr.lowbatt else "The jeep is returning to the terminal.", "warn")
        else:
            self.show_alert("")

    def show_alert(self, text, level="danger"):
        """Show the alert line in the status card in the palette color named by `level`;
        an empty text leaves the line blank (its room is kept, so nothing moves)."""
        self.v_alert.set(text)
        self.lbl_alert.config(foreground=PALETTE[level])

    def trip_ends(self):
        # Trip planning is passenger-only. Operators see the automatic patrol, not a selectable route highlight.
        if self.role != PASSENGER:
            return 0, 0
        return self.names.index(self.from_var.get()), self.names.index(self.to_var.get())

    def refresh_trip(self, now):
        a, b = self.trip_ends()
        if a == b:
            for v in (self.v_fare, self.v_wait, self.v_ride, self.v_total, self.v_arrive):
                v.set("-")
            self.v_route.set("Choose two different stations.")
            return
        cat = self.cat_var.get()
        legs = (b - a) % N
        stops = [self.short_names[(a + k) % N] for k in range(legs + 1)]       # compact station names so the route fits
        self.v_route.set(" > ".join(stops) + f"  ({legs} leg{'s' if legs > 1 else ''})" + "")
        self.v_fare.set(f"{CURRENCY}{fare_for(legs, cat):.2f}")
        ride = sum(self.tr.leg_est[(a + k) % N] for k in range(legs)) + self.tr.dwell * (legs - 1)     # the jeep stops at every station on the way
        self.v_ride.set(fmt_dur(ride))
        wait = self.tr.eta_to_stop(a, now, dispatch=not self.tr.paused) if self.fresh(now) else None
        if wait is None:
            self.v_wait.set("unknown")
            self.v_total.set("-")
            self.v_arrive.set("-")
        else:
            self.v_wait.set("at the station now" if wait == 0 else fmt_dur(wait))
            self.v_total.set(fmt_dur(wait + ride))
            self.v_arrive.set(fmt_clock(now + wait + ride))

    def refresh_schedule(self, now):
        t = datetime.now().time()
        o = datetime.strptime(OPEN_TIME, "%H:%M").time()
        c = datetime.strptime(CLOSE_TIME, "%H:%M").time()
        if o <= t <= c:
            self.v_service.set(f"IN SERVICE until {fmt12(CLOSE_TIME)}")
            self.lbl_service.config(foreground=PALETTE["ok"])
        else:
            self.v_service.set(f"OUT OF SERVICE, opens at {fmt12(OPEN_TIME)}")
            self.lbl_service.config(foreground=PALETTE["danger"])
        tr = self.tr
        self.v_svc.set("The jeep patrols the loop and stops at every station.")
        lap = tr.lap_time()
        for i, n in enumerate(self.names):
            if tr.state == "PARKED" and self.fresh(now):
                first = second = "parked"
            else:
                eta = tr.eta_to_stop(i, now) if self.fresh(now) else None
                first = "-" if eta is None else ("now" if eta == 0 else fmt_clock(now + eta))
                second = "-" if eta is None else fmt_clock(now + eta + lap)
            self.tree.item(str(i), values=(n, first, second))

    def refresh_operator(self, now):
        tr, ov = self.tr, self.ov
        if not self.fresh(now):
            for v in ov.values():
                v.set("-")
            return
        ov["state"].set(self.state_text())
        if tr.batt is None:
            ov["batt"].set("-")
        else:
            flag = "  CRITICAL" if tr.crit else ("  LOW" if tr.lowbatt else "")
            ov["batt"].set(f"{tr.batt:.2f} V (about {batt_pct(tr.batt):.0f}%, estimate){flag}")
        ov["sensors"].set((f"{tr.dist} cm ahead" if tr.dist else "nothing ahead") + (f", IR {tr.ir}" if tr.ir else "")
                          + f", headlights {'on' if tr.lights else 'off'}")
