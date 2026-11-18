"""The update that runs four times a second: refreshes every screen from the Tracker's data.

This is one part of the App window: App (app.py) inherits RefreshMixin, so these methods are called as self.<name>()."""

import queue
import time
from datetime import datetime

from config import CLOSE_TIME, CURRENCY, DISCOUNTS, OPEN_TIME, STALE_S
from helpers import batt_pct, fare_for, fmt12, fmt_clock, fmt_dur, set_enabled, stop_label
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
        on_road = online and not tr.depot          # the jeep is out driving, not parked in the depot

        # ----- Plan trip: Request ride (the reason is shown under the button while it is disabled) -----
        a, b = self.trip_ends()
        why = self.reject_reason(a, b, now)
        set_enabled(self.btn_request, why is None)
        if why is None or a == b:                  # (same-station is already explained in the trip summary)
            hint = ""
        elif self.role == PASSENGER and not self.fresh(now):
            hint = "The service is unavailable right now. Please try again in a moment."
        elif not self.source:
            hint = "Connect to the jeep first (Connection box above)."
        else:
            hint = why
        self.v_reqhint.set(hint)
        if hint:
            self.lbl_reqhint.grid()
        else:
            self.lbl_reqhint.grid_remove()

        # ----- Status card: Para (only while the jeep is out on the road) -----
        set_enabled(self.btn_para, on_road)

        # ----- My rides: Cancel (needs a selected ride that is not picked up yet, and a live jeep) -----
        sel = self.rtree.selection()
        ride = self.book_by_id(int(sel[0])) if sel else None
        set_enabled(self.btn_cancel, bool(online and ride and ride.cancellable))

        # ----- Operator: Dispatch, Return and Reset (Emergency stop is left alone) -----
        set_enabled(self.btn_dispatch, online and tr.state == "PARKED" and not tr.paused)
        set_enabled(self.btn_return, on_road and not tr.paused)
        set_enabled(self.btn_reset, online and tr.state in ("EMERGENCY_STOP", "LINE_LOST"))

    def tick(self):
        now = time.time()
        self.check_idle(now)                          # Operator mode signs out after a long quiet time
        got_status = False
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "conn":
                    self.on_link(val)
                elif kind == "msg" and isinstance(val, dict):
                    if val.get("type") == "event":
                        self.on_event(val, now)
                    elif self.tr.update(val, now):
                        got_status = True
        except queue.Empty:
            pass
        if got_status:
            self.sync_bookings(now)
        self.tr.update_frac(now)
        self.refresh_status(now)
        self.refresh_trip(now)
        self.refresh_rides(now)
        self.refresh_schedule(now)
        self.refresh_operator(now)
        self.refresh_controls(now)
        self.draw_dynamic(now)
        self.after(250, self.tick)

    def fresh(self, now):
        return self.tr.connected and now - self.tr.last_msg <= STALE_S

    def state_text(self):
        tr = self.tr
        if tr.state == "LOADING_UNLOADING":
            return "At station: " + stop_label(tr.load, tr.unload)
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
            self.v_last.set("Last station: -")
            self.v_next.set("-")
            self.v_eta.set("-")
            self.v_etaclock.set("")
            self.set_battery(None)
            if self.role == PASSENGER:
                self.show_alert("The service is unavailable right now. Please try again in a moment.", "warn")
            else:
                self.show_alert("No connection to the jeep: requests and cancels are paused." if self.source else "", "warn")
            return

        # ----- state badge, next station and last station -----
        self.badge.set(self.state_text(), STATE_COLOR.get(tr.state, PALETTE["muted"]))
        self.v_next.set("-" if tr.state == "PARKED" else self.names[tr.next_stop])
        self.v_last.set("Last station: " + ("Depot" if tr.depot else self.names[tr.last_stop]))

        # ----- arrival time -----
        eta = tr.eta_to_next(now)
        if eta is None:
            self.v_eta.set("parked" if tr.state == "PARKED" else "paused")
            self.v_etaclock.set("")
        else:
            self.v_eta.set("arriving" if eta < 1 else fmt_dur(eta))
            self.v_etaclock.set("about " + fmt_clock(now + eta))

        # ----- battery bar -----
        self.set_battery(tr)

        # ----- alert line: red for danger, amber for caution -----
        if tr.state == "EMERGENCY_STOP":
            self.show_alert("EMERGENCY STOP. Press Reset (Operator tab) to continue.", "danger")
        elif tr.state == "LINE_LOST":
            self.show_alert("FAULT: line lost. Put the jeep back on the line, then press Reset.", "danger")
        elif tr.state == "OBSTACLE_HOLD":
            self.show_alert("Obstacle ahead: waiting for it to clear.", "warn")
        elif tr.paused:
            self.show_alert(("LOW BATTERY" if tr.lowbatt else "RETURNING TO DEPOT") + ": new requests are paused.", "warn")
        else:
            self.show_alert("")

    def set_battery(self, tr):
        """Fill the battery bar and its percentage. Pass None (or a Tracker with no reading) for an empty bar."""
        if tr is None or tr.batt is None:
            self.batt_bar.config(value=0, style="Ok.Horizontal.TProgressbar")
            self.v_batt.set("Battery: -")
            return
        pct = batt_pct(tr.batt)
        if tr.crit:
            level, tag = "Danger", " (critical)"
        elif tr.lowbatt:
            level, tag = "Warn", " (low)"
        else:
            level, tag = "Ok", ""
        self.batt_bar.config(value=pct, style=f"{level}.Horizontal.TProgressbar")
        self.v_batt.set(f"Battery: ~{pct:.0f}%{tag}")   # "~" because the percentage is an estimate from volts

    def show_alert(self, text, level="danger"):
        """Show the alert line in the status card in the palette color named by `level`;
        an empty text hides the line so the card has no gap."""
        self.v_alert.set(text)
        self.lbl_alert.config(foreground=PALETTE[level])
        if text:
            self.lbl_alert.grid()
        else:
            self.lbl_alert.grid_remove()

    def trip_ends(self):
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
        stops = [self.names[(a + k) % N] for k in range(legs + 1)]
        off = DISCOUNTS.get(cat, 0.0)
        self.v_route.set(" > ".join(stops) + f"   ({legs} leg{'s' if legs > 1 else ''})" + (f"   {int(off * 100)}% off" if off else ""))
        self.v_fare.set(f"{CURRENCY}{fare_for(legs, cat):.2f}")
        ride = sum(self.tr.leg_est[(a + k) % N] for k in range(legs)) + (self.tr.dwell * (legs - 1) if self.tr.patrol else 0.0)
        self.v_ride.set(fmt_dur(ride))
        wait = self.tr.eta_to_stop(a, now, dispatch=not self.tr.paused) if self.fresh(now) else None
        if wait is None:
            self.v_wait.set("unknown (jeep offline or stopped)")
            self.v_total.set("-")
            self.v_arrive.set("-")
        else:
            self.v_wait.set("at the station now" if wait == 0 else fmt_dur(wait))
            self.v_total.set(fmt_dur(wait + ride))
            self.v_arrive.set(fmt_clock(now + wait + ride))

    def status_text(self, b, now):
        if b.status == "WAITING":
            return "On the way" if self.fresh(now) and self.tr.state != "PARKED" else "Requested"
        if b.status == "BOARDED":
            return "On board"
        if b.status == "CANCELLED" and b.note:
            return f"Cancelled ({b.note})"
        return b.status.capitalize()

    def ride_eta(self, b, now):
        if not self.fresh(now):
            return "-"
        if b.status == "WAITING":
            t = self.tr.eta_to_stop(b.pickup, now, dispatch=not self.tr.paused, lap_if_here=True)
        elif b.status == "BOARDED":
            t = self.tr.eta_to_stop(b.drop, now)
        else:
            return "-"
        return "-" if t is None else ("arriving" if t < 1 else fmt_dur(t))

    def refresh_rides(self, now):
        shown = self.bookings[-30:]
        keep = {str(b.id) for b in shown}
        for iid in self.rtree.get_children():
            if iid not in keep:
                self.rtree.delete(iid)
        for b in shown:
            trip = f"{self.names[b.pickup].split()[0]} > {self.names[b.drop].split()[0]}"
            vals = (f"#{b.id}", trip, self.status_text(b, now), self.ride_eta(b, now))
            if self.rtree.exists(str(b.id)):
                self.rtree.item(str(b.id), values=vals)
            else:
                self.rtree.insert("", "end", iid=str(b.id), values=vals)
        # ----- empty-table hint -----
        self.lbl_rempty.config(text="" if self.bookings else self.rides_hint)

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
        self.v_svc.set("Patrol: the jeep stops at every station." if tr.patrol else
                       "On-demand: the jeep stops only where a ride is booked or Para is pressed, and parks when idle.")
        lap = tr.lap_time()
        for i, n in enumerate(self.names):
            if tr.state == "PARKED" and self.fresh(now):
                first = second = "on request"
            else:
                eta = tr.eta_to_stop(i, now) if self.fresh(now) else None
                first = "-" if eta is None else ("now" if eta == 0 else fmt_clock(now + eta))
                second = "-" if eta is None else fmt_clock(now + eta + lap)
            self.tree.item(str(i), values=(n, first, second))
        self.v_lap.set(f"One full loop takes about {fmt_dur(lap)} (learned from real arrivals).")

    def refresh_operator(self, now):
        tr, ov = self.tr, self.ov
        booked = sum(1 for b in self.bookings if b.status == "WAITING")
        riding = sum(1 for b in self.bookings if b.status == "BOARDED")
        if not self.fresh(now):
            for v in ov.values():
                v.set("-")
            ov["rides"].set(f"{booked} booked, {riding} on board")
            return
        ov["rides"].set(f"{booked} booked, {riding} on board")
        ov["state"].set(self.state_text())
        ov["mode"].set("Patrol" if tr.patrol else "On-demand")
        if tr.batt is None:
            ov["batt"].set("-")
        else:
            flag = "  CRITICAL" if tr.crit else ("  LOW" if tr.lowbatt else "")
            ov["batt"].set(f"{tr.batt:.2f} V (about {batt_pct(tr.batt):.0f}%, estimate){flag}")
        ov["sensors"].set((f"{tr.dist} cm ahead" if tr.dist else "nothing ahead") + (f", IR {tr.ir}" if tr.ir else "")
                          + f", headlights {'on' if tr.lights else 'off'}")
        short = [n.split()[0] for n in self.names]
        ov["pick"].set("  ".join(f"{s}:{c}" for s, c in zip(short, tr.pick)))
        ov["drop"].set("  ".join(f"{s}:{c}" for s, c in zip(short, tr.drop)))
