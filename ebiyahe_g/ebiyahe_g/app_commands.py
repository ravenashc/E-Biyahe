"""What the buttons do: request, cancel, para, dispatch, mode, dwell and the Demo menu.

This is one part of the App window: App (app.py) inherits CommandMixin, so these methods are called as self.<name>()."""

import time

from config import CURRENCY, MAX_ACTIVE
from helpers import fare_for, save_language
from labels import LANG_NAME
from map_data import N
from models import Booking
from sources import DemoSource


# ======================= COMMANDS (button actions) =======================
class CommandMixin:
    """What the buttons do: request, cancel, para, dispatch, mode, dwell and the Demo menu."""

    # ---------- language ----------
    def set_language(self, lang, startup=False):
        """Show the fixed labels in English ('en') or Filipino ('fil'). The choice is remembered for next time.
        Live messages stay in English (see labels.py)."""
        self.labels.set_language(lang)
        self.header.set_language_name(LANG_NAME["en" if lang == "fil" else "fil"])    # the button names the other language
        if startup:
            return
        save_language(lang)
        self.fit_window()                                       # labels have different lengths: make sure everything still fits
        self.show_message("Filipino labels are on. Messages stay in English." if lang == "fil" else "English labels are on.", "info")

    def toggle_language(self):
        self.set_language("fil" if self.labels.lang == "en" else "en")

    # ---------- commands ----------
    def send(self, obj):
        if self.source:
            self.source.send(obj)

    def active_count(self):
        return sum(1 for b in self.bookings if b.active)

    def book_by_id(self, bid):
        return next((b for b in self.bookings if b.id == bid), None)

    def reject_reason(self, a, b, now):
        if a == b:
            return "Choose two different stations."
        if not self.fresh(now):
            return "The jeep is offline."
        if self.tr.paused:
            return "Service is paused (low battery or the jeep is returning to the depot)."
        if self.tr.state in ("EMERGENCY_STOP", "LINE_LOST"):
            return "The jeep is stopped (emergency stop or fault)."
        if self.active_count() >= MAX_ACTIVE:
            return f"Too many active rides (limit {MAX_ACTIVE})."
        return None

    def swap_stations(self):
        """Swap 'Ride on at' and 'Get off at' (handy for the trip back)."""
        a, b = self.from_var.get(), self.to_var.get()
        self.from_var.set(b)
        self.to_var.set(a)

    def do_request(self):
        now = time.time()
        a, b = self.trip_ends()
        why = self.reject_reason(a, b, now)
        if why:
            self.show_message("Request rejected: " + why, "error")
            self.log_add("Request rejected: " + why, "warn")
            return
        legs = (b - a) % N
        cat = self.cat_var.get()
        bk = Booking(self.next_id, a, b, cat, fare_for(legs, cat), now)
        self.next_id += 1
        self.bookings.append(bk)
        self.send({"cmd": "request", "id": bk.id, "from": a, "to": b})
        self.show_message(f"Ride #{bk.id} requested: {self.names[a]} > {self.names[b]}, fare {CURRENCY}{bk.fare:.2f} ({cat}). "
                          "Track it in My rides.", "ok")
        self.log_add(f"Ride #{bk.id} requested: {self.names[a]} > {self.names[b]} ({cat}, {CURRENCY}{bk.fare:.2f})", "ok")

    def do_cancel(self):
        sel = self.rtree.selection()
        if not sel:
            self.show_message("Select a ride in the list first.", "warn")
            return
        bk = self.book_by_id(int(sel[0]))
        if bk is None:
            return
        if not bk.cancellable:
            self.show_message(f"Ride #{bk.id} cannot be cancelled (status: {bk.status.lower()}).", "warn")
        elif not self.fresh(time.time()):
            self.show_message("Cannot cancel while the jeep is offline. Try again when it reconnects.", "warn")
        else:
            self.send({"cmd": "cancel", "id": bk.id})
            self.show_message(f"Cancel sent for ride #{bk.id}...", "info")

    def do_para(self):
        if not self.fresh(time.time()):
            self.show_message("Para not sent: the jeep is offline.", "warn")
            return
        self.send({"cmd": "para"})

    def op(self, cmd, **kw):
        if not (self.source and self.fresh(time.time())):
            self.show_message("Not connected to the jeep." + (" For a real emergency use the toggle switch on the jeep!" if cmd == "estop" else ""),
                              "error" if cmd == "estop" else "warn")
            return
        self.send({"cmd": cmd, **kw})

    def do_dispatch(self):
        if self.tr.paused:
            self.show_message("Cannot dispatch: the battery is low. Wait for it to recharge.", "warn")
        else:
            self.op("dispatch")

    def set_mode(self):
        self.op("mode", value=self.svc_var.get())

    def set_dwell(self):
        try:
            v = float(self.dwell_var.get())
        except ValueError:
            self.show_message("Dwell time must be a number.", "error")
            return
        if not 1 <= v <= 30:
            self.show_message("Dwell time must be between 1 and 30 seconds.", "error")
            return
        self.op("dwell", value=v)

    def sim(self, what, text):
        if not isinstance(self.source, DemoSource):
            self.show_message("Connect in Demo mode first, then use the Demo menu.", "warn")
            return
        self.log_add("Demo: " + text.lower())
        self.send({"cmd": "sim", "what": what})
