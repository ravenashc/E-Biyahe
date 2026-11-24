"""Passenger and Operator modes: the header bar, signing in and out, and showing or hiding what each role may use.

This is one part of the App window: App (app.py) inherits RolesMixin, so these methods are called as self.<name>().
The permissions themselves are in roles.py; this file only applies them to the screen."""

import time
from tkinter import ttk

from config import OPERATOR_IDLE_MIN, OPERATOR_PIN, TAB_NAMES
from roles import OPERATOR, PASSENGER, allowed
from theme import PAD, PALETTE, set_mode
from widgets import HeaderBar, PinDialog


# ======================= ROLES (passenger and operator) =======================
class RolesMixin:
    """The header bar, operator sign-in and sign-out, idle sign-out, and applying a role to the screen."""

    def fit_tabs(self):
        """A hidden tab still counts toward the notebook's natural height, so without this a passenger would get room
        for the operator's tabs and have to scroll. The pages of hidden tabs are made tiny; the others keep their own size."""
        for i, t in enumerate(self.nb.tabs()):
            page, show = self.nb.nametowidget(t), allowed(self.role, "tabs", TAB_NAMES[i])
            page.pack_propagate(show)                          # False: the page stops growing to fit its contents
            page.grid_propagate(show)
            if not show:
                page.configure(width=1, height=1)

    # ---------- header bar ----------
    def build_header(self):
        """The bar at the top of the window: app name, current mode, sign-in / sign-out button
        and (operators) the sign-out button."""
        self.header = HeaderBar(self, on_sign_in=self.sign_in, on_sign_out=self.sign_out)
        self.header.pack(side="top", fill="x")
        ttk.Separator(self).pack(side="top", fill="x")

    # ---------- colors ----------
    def apply_mode_colors(self, role):
        """Give the whole window the look of the role: warm cream for passengers, cool sky blue for operators.
        theme.set_mode() restyles the ttk widgets; the Tk canvases, the log rows and the map are recolored here."""
        set_mode(self, role == OPERATOR)
        for w in self.all_widgets(self):
            if hasattr(w, "bg_role"):                          # canvases remember which palette color they follow
                w.configure(bg=PALETTE[w.bg_role])
            if hasattr(w, "edge_role"):
                w.configure(highlightbackground=PALETTE[w.edge_role])
        self.pills.relayout()
        self.apply_log_tags()
        self.draw_static()                                     # the map redraws in the new colors

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

        # ----- colors first: the whole window changes look with the mode, not only the header -----
        self.apply_mode_colors(role)

        # ----- header bar: mode label, button text and colors -----
        self.header.show_role(role)

        # ----- message bar: operators only (passengers get no strip at the bottom, so the map is taller) -----
        if role == OPERATOR:
            self.bar.pack(side="bottom", fill="x", before=self.header)     # `before` keeps it first in the packing order, so it keeps its room
        else:
            self.bar.pack_forget()

        # ----- tabs -----
        for i, name in enumerate(TAB_NAMES):
            self.nb.tab(i, state="normal" if allowed(role, "tabs", name) else "hidden")
        # Always open the useful home tab for the new role. In Operator mode the
        # passenger My Trip tab is hidden, so the dispatch controls should open
        # directly rather than leaving the operator on Schedule.
        preferred_name = "Operator" if role == OPERATOR else "My Trip"
        preferred_tab = next((tab for tab in self.nb.tabs()
                              if self.nb.tab(tab, "text") == preferred_name), None)
        if preferred_tab is not None:
            self.nb.select(preferred_tab)
        self.pills.refresh()                                   # the pills follow: show only the tabs this role may use

        # ----- emergency stop: under the right-hand column, only for operators (see build_ui) -----
        if allowed(role, "panels", "estop"):
            self.estop.grid()
        else:
            self.estop.grid_remove()

        # ----- panels: the connection box sits in the Operator tab above the live readout -----
        if allowed(role, "panels", "connection"):
            self.conn_box.pack(fill="x", pady=(PAD, 0), before=self.live_card)
        else:
            self.conn_box.pack_forget()
        # ----- menu bar (rebuilt: operator menus and items exist only in Operator mode) -----
        self.build_menu()
        self.fit_tabs()
        self.scroll.set_scrolling(role == OPERATOR)            # passengers get a screen that fits: no scrolling, no scroll bar
