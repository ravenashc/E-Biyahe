"""Passenger and Operator modes: the header bar, signing in and out, and showing or hiding what each role may use.

This is one part of the App window: App (app.py) inherits RolesMixin, so these methods are called as self.<name>().
The permissions themselves are in roles.py; this file only applies them to the screen."""

import time
from tkinter import ttk

from config import OPERATOR_IDLE_MIN, OPERATOR_PIN, TAB_NAMES
from roles import OPERATOR, PASSENGER, allowed
from widgets import HeaderBar, PinDialog


# ======================= ROLES (passenger and operator) =======================
class RolesMixin:
    """The header bar, operator sign-in and sign-out, idle sign-out, and applying a role to the screen."""

    # ---------- header bar ----------
    def build_header(self):
        """The bar at the top of the window: app name, current mode, sign-in / sign-out button
        and (operators only) the emergency stop, which stays visible from every tab."""
        self.header = HeaderBar(self, on_sign_in=self.sign_in, on_sign_out=self.sign_out,
                                on_estop=lambda: self.op("estop"))
        self.header.pack(side="top", fill="x")
        ttk.Separator(self).pack(side="top", fill="x")

    # ---------- signing in and out ----------
    def toggle_operator(self):
        """Ctrl+L: sign in (opens the PIN window) or sign out."""
        if self.role == OPERATOR:
            self.sign_out()
        else:
            self.sign_in()

    def sign_in(self):
        """Open the PIN window. The role changes only when the right PIN is entered."""
        if self.role == OPERATOR:
            return
        if self.pin_dialog is not None:                        # already open: bring it to the front
            self.pin_dialog.lift()
            self.pin_dialog.entry.focus_set()
            return
        self.pin_dialog = PinDialog(self, check=lambda pin: pin == OPERATOR_PIN,
                                    on_ok=self.operator_signed_in, on_close=self.pin_closed)

    def pin_closed(self):
        """The PIN window closed (signed in or cancelled)."""
        self.pin_dialog = None

    def operator_signed_in(self):
        """The right PIN was entered: switch to Operator mode."""
        self.log_add("Operator signed in", "ok")
        self.set_role(OPERATOR)
        self.show_message("Operator mode: the dispatch controls are unlocked.", "ok")

    def sign_out(self, automatic=False):
        """Back to Passenger mode (automatic=True when it happens after a long time without activity)."""
        if self.role != OPERATOR:
            return
        self.log_add("Operator signed out" + (" (no activity)" if automatic else ""), "info")
        self.set_role(PASSENGER)
        self.ensure_connected()                                # passengers must always have a connection
        if automatic:
            self.show_message(f"Signed out after {OPERATOR_IDLE_MIN} minutes without activity. Passenger mode.", "info")
        else:
            self.show_message("Signed out. Passenger mode.", "info")

    def set_role(self, role):
        """Switch role and update the whole screen."""
        self.role = role
        self.last_activity = time.time()
        self.apply_role()
        self.fit_window()                                      # Operator mode shows more, so the window may need to grow

    # ---------- idle sign-out ----------
    def bind_activity(self):
        """Count every key press, click and wheel turn as activity (it restarts the idle timer)."""
        for sequence in ("<Key>", "<ButtonPress>", "<MouseWheel>"):
            self.bind_all(sequence, self.note_activity, add="+")

    def note_activity(self, event=None):
        self.last_activity = time.time()

    def check_idle(self, now):
        """Called by the periodic update: sign the operator out after OPERATOR_IDLE_MIN quiet minutes."""
        if self.role == OPERATOR and now - self.last_activity > OPERATOR_IDLE_MIN * 60:
            self.sign_out(automatic=True)

    # ---------- connection for passengers ----------
    def ensure_connected(self):
        """Passengers have no Connection box, so the app connects by itself (to the connection used last time)."""
        if self.source is None:
            self.connect()

    # ---------- applying a role to the screen ----------
    def apply_role(self):
        """Show or hide everything according to the current role (the permissions are in roles.py)."""
        role = self.role

        # ----- header bar: mode label, button text, colors and the emergency stop -----
        self.header.show_role(role)

        # ----- tabs -----
        for i, name in enumerate(TAB_NAMES):
            self.nb.tab(i, state="normal" if allowed(role, "tabs", name) else "hidden")
        if not allowed(role, "tabs", TAB_NAMES[self.nb.index("current")]):
            self.nb.select(0)                                  # the open tab was just hidden: go to the first one

        # ----- panels: connection box above the status card, battery bar inside it -----
        if allowed(role, "panels", "connection"):
            self.conn_box.pack(fill="x", before=self.status_card)
        else:
            self.conn_box.pack_forget()
        for widget in self.batt_widgets:
            if allowed(role, "panels", "battery"):
                widget.grid()
            else:
                widget.grid_remove()

        # ----- menu bar (rebuilt: operator menus and items exist only in Operator mode) -----
        self.build_menu()
        self.scroll.refresh()
