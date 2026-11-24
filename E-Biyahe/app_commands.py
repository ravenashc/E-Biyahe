"""What the buttons do: dispatch, return, reset, emergency stop, dwell time and the Demo menu.

This is one part of the App window: App (app.py) inherits CommandMixin, so these methods are called as self.<name>()."""

import time

from sources import DemoSource


# ======================= COMMANDS (button actions) =======================
class CommandMixin:
    """What the buttons do: dispatch, return, reset, emergency stop, dwell time and the Demo menu."""

    # ---------- commands ----------
    def send(self, obj):
        if self.source:
            self.source.send(obj)

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
