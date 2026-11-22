"""Keyboard shortcuts, text size, window size and the help window.

This is one part of the App window: App (app.py) inherits KeyboardMixin, so these methods are called as self.<name>()."""

import tkinter as tk
from tkinter import font as tkfont, messagebox

from config import MOD, MOD_NAME, TAB_NAMES, TEXT_SIZES
from helpers import chord, save_text_size
from roles import allowed
from theme import apply_text_size, MAP_MIN_PT, RIGHT_W


# ======================= KEYBOARD, TEXT SIZE AND WINDOW SIZE =======================
class KeyboardMixin:
    """Keyboard shortcuts, text size, window size and the help window."""

    # ---------- keyboard and text size ----------
    def shortcut_table(self):
        """Every keyboard shortcut as (id, keys shown to the user, Tk key patterns, what it does, function).
        This one list drives the key bindings, the menus and the Keyboard shortcuts window."""
        M = MOD_NAME
        rows = [(f"tab{i}", f"{M}+{i}", chord(str(i)), f"Go to {name}", lambda i=i: self.show_tab(i - 1))
                for i, name in enumerate(TAB_NAMES, start=1)]
        rows += [
            ("dispatch", f"{M}+Shift+D", chord("d", True), "Dispatch",
             lambda: self.press(self.btn_dispatch, "Dispatch", "the jeep must be parked and online")),
            ("return", f"{M}+Shift+H", chord("h", True), "Return to depot",
             lambda: self.press(self.btn_return, "Return to depot", "the jeep must be out on the road and not in an emergency stop")),
            ("reset", f"{M}+Shift+F", chord("f", True), "Reset fault",
             lambda: self.press(self.btn_reset, "Reset fault", "there is no fault or emergency stop to reset")),
            ("estop", f"{M}+Shift+E", chord("e", True), "EMERGENCY STOP", self.do_estop),
            ("signin", f"{M}+L", chord("l"), "Operator sign-in / sign-out", self.toggle_operator),
            ("connect", f"{M}+Shift+C", chord("c", True), "Connect or disconnect", self.toggle_connection),
            ("export", f"{M}+S", chord("s"), "Export the log...", self.export_log),
            ("bigger", f"{M}++", [f"<{MOD}-Key-plus>", f"<{MOD}-Key-equal>", f"<{MOD}-Key-KP_Add>"],
             "Larger text", lambda: self.step_text_size(1)),
            ("smaller", f"{M}+-", [f"<{MOD}-Key-minus>", f"<{MOD}-Key-KP_Subtract>"],
             "Smaller text", lambda: self.step_text_size(-1)),
            ("normal", f"{M}+0", [f"<{MOD}-Key-0>", f"<{MOD}-Key-KP_0>"],
             "Normal text size", lambda: self.step_text_size(0)),
            ("help", "F1", ["<F1>"], "Keyboard shortcuts", self.show_shortcuts),
            ("quit", f"{M}+Q", chord("q"), "Exit", self.on_close),
        ]
        return rows

    def bind_keys(self):
        """Turn the shortcut table into key bindings and make a few standard keys work as people expect."""
        for _id, _keys, patterns, _what, action in self.shortcuts:
            for pattern in patterns:
                self.bind_all(pattern, lambda e, ident=_id, action=action: self.run_shortcut(ident, action))
        for key in ("<Return>", "<KP_Enter>"):         # Enter presses the focused button (Tk only does this for Space)
            self.bind_class("TButton", key, self.press_focused)
        self.bind_class("TButton", "<Enter>", lambda e: e.widget.configure(cursor="arrow" if e.widget.instate(["disabled"]) else "hand2"))
        self.bind_class("TButton", "<Leave>", lambda e: e.widget.configure(cursor=""))     # hover: a hand over buttons that work
        for key, step in (("Left", -1), ("Up", -1), ("Right", 1), ("Down", 1)):   # arrow keys move inside a radio group
            self.bind_class("TRadiobutton", f"<{key}>", lambda e, step=step: self.move_radio(e, step))

    def run_shortcut(self, ident, action):
        """Run a shortcut, unless it is reserved for operators and nobody has signed in."""
        if allowed(self.role, "shortcuts", ident):
            action()
        else:
            self.show_message(f"That shortcut is for operators. Sign in with the button at the top right ({MOD_NAME}+L).", "warn")
        return "break"                                  # the key has been used; nothing else should react to it

    def press_focused(self, event):
        event.widget.invoke()                           # does nothing while the button is disabled
        return "break"

    def move_radio(self, event, step):
        """Arrow keys inside a group of radio buttons: go to the next or previous one and choose it."""
        w = event.widget
        group = [str(c) for c in w.master.winfo_children()
                 if c.winfo_class() == "TRadiobutton" and str(c.cget("variable")) == str(w.cget("variable"))]
        if len(group) > 1:
            target = self.nametowidget(group[(group.index(str(w)) + step) % len(group)])
            target.focus_set()
            target.invoke()
        return "break"

    def press(self, button, what, reason=""):
        """Press a button from the keyboard, but only while the button itself is enabled (as with the mouse)."""
        if button.instate(["disabled"]):
            text = f"{what} is not available right now" + (f": {reason}" if reason else "")
            self.show_message(text.rstrip(".") + ".", "warn")
        else:
            button.invoke()

    def show_tab(self, i):
        """Switch to tab number i and put the keyboard focus on its first safe control."""
        if not allowed(self.role, "tabs", TAB_NAMES[i]):
            self.show_message(f"The {TAB_NAMES[i]} tab is for operators. Sign in with the button at the top right ({MOD_NAME}+L).", "warn")
            return
        self.nb.select(i)
        self.update_idletasks()
        self.tab_focus[i].focus_set()

    def show_shortcuts(self):
        lines = [f"{keys}    {what}" for ident, keys, _patterns, what, _action in self.shortcuts
                 if allowed(self.role, "shortcuts", ident)]
        lines += ["", "Tab / Shift+Tab    move between controls",
                  "Space or Enter    press the selected button",
                  "Arrow keys    choose a radio button, move in a table, or switch tabs (while the tab names are selected)",
                  "Ctrl+Tab / Ctrl+Shift+Tab    next / previous tab"]
        messagebox.showinfo("Keyboard shortcuts", "\n".join(lines))

    def step_text_size(self, step):
        """Larger text (step 1), smaller text (step -1) or back to normal (step 0)."""
        i = 0 if step == 0 else min(max(TEXT_SIZES.index(self.text_pct) + step, 0), len(TEXT_SIZES) - 1)
        if TEXT_SIZES[i] == self.text_pct:
            self.show_message(f"Text is already at the {'largest' if step > 0 else 'normal'} size ({self.text_pct}%).", "info")
        else:
            self.set_text_size(TEXT_SIZES[i])

    def set_text_size(self, pct, startup=False):
        """Apply a text size (percent of normal) to the whole window; it is remembered for next time.
        A size that would make the window wider than this screen is not used: the largest size that fits is used
        instead (never smaller than normal). Height is never a problem, because the right-hand column scrolls."""
        wanted = pct
        self.apply_size(pct)

        # ----- too big for this screen? step down to the largest size that fits -----
        while not self.fits_screen() and TEXT_SIZES.index(pct) > 0:
            pct = TEXT_SIZES[TEXT_SIZES.index(pct) - 1]
            self.apply_size(pct)
        self.fit_window()

        # ----- redraw, remember the size actually used, and tell the user what happened -----
        if not startup:
            self.draw_static()
            save_text_size(pct)
        if pct != wanted:
            self.show_message(f"Text size {wanted}% does not fit this screen, so the app uses {pct}%.", "warn")
        elif not startup:
            self.show_message(f"Text size {pct}%.", "info")

    def apply_size(self, pct):
        """Switch every font, table column and wrap width to `pct` percent of normal (no checks, no saving)."""
        self.text_pct = pct
        self.text_factor = pct / 100.0
        apply_text_size(self, pct)
        self.rescale_widgets()

    def fits_screen(self):
        """True when the window is not wider than this screen at the current text size.
        (Height is not checked: when the window is too short, the right-hand column scrolls.)"""
        self.update_idletasks()
        self.scroll.refresh()
        return self.winfo_reqwidth() + 20 <= self.winfo_screenwidth() - 20

    def all_widgets(self, parent):
        """Every widget below `parent`, at any depth."""
        for child in parent.winfo_children():
            yield child
            yield from self.all_widgets(child)

    def rescale_widgets(self):
        """Things fonts cannot do for themselves: table column widths and the wrap width of long labels."""
        f = self.text_factor
        self.right_min.configure(width=round(RIGHT_W * f))
        self.pills.relayout()                  # the tab pills are canvases: they measure their own text again
        self.apply_reserved()
        for tree, widths in self.col_base:
            for col, width in widths.items():
                tree.column(col, width=round(width * f))
        for w in self.all_widgets(self):
            if w.winfo_class() == "TLabel" and w is not self.bar.label:      # the message bar wraps itself
                base = self.wrap_base.setdefault(str(w), int(str(w.cget("wraplength")) or 0))
                if base:
                    w.configure(wraplength=round(base * f))

    def fit_window(self):
        """Make the window big enough for its content, never smaller than it is now and never bigger than the screen.
        If the screen is too short, the right-hand column simply scrolls."""
        if self.is_maximized():                # a maximized window already has the biggest size it can have
            return
        self.update_idletasks()
        self.scroll.refresh()                  # hand the content's size to the scroll frame before measuring
        self.update_idletasks()
        width = min(max(1200, self.winfo_width(), self.winfo_reqwidth() + 20), self.winfo_screenwidth() - 20)
        height = min(max(780, self.winfo_height(), self.winfo_reqheight() + 30), self.winfo_screenheight() - 80)  # +30: menu bar room on Linux
        self.geometry(f"{width}x{height}")

    def start_maximized(self):
        """Open the window maximized (Windows and macOS: state zoomed, Linux: the -zoomed attribute)."""
        try:
            self.state("zoomed")
        except tk.TclError:
            try:
                self.attributes("-zoomed", True)
            except tk.TclError:
                pass                           # this window manager cannot maximize: the normal size is used

    def is_maximized(self):
        try:
            return self.state() == "zoomed" or bool(self.attributes("-zoomed"))
        except tk.TclError:
            return False

    def reserve(self, frame, row, font, lines):
        """Keep row `row` of `frame` at least `lines` lines of `font` tall, even when its label is empty or short,
        so that text appearing and disappearing never moves the controls below it."""
        self.reserved.append((frame, row, font, lines))
        self.apply_reserved()

    def reserve_width(self, frame, column, font, texts, extra=0):
        """Keep column `column` of `frame` at least as wide as the widest of `texts` in `font` (plus `extra` pixels),
        so that a value changing from short to long never shifts the columns beside it."""
        self.reserved_cols.append((frame, column, font, texts, extra))
        self.apply_reserved()

    def apply_reserved(self):
        for frame, row, font, lines in self.reserved:
            frame.rowconfigure(row, minsize=lines * tkfont.nametofont(font).metrics("linespace"))
        for frame, column, font, texts, extra in self.reserved_cols:
            f = tkfont.nametofont(font)
            frame.columnconfigure(column, minsize=max(f.measure(t) for t in texts) + extra)

    def map_pt(self, size):
        """Point size for a map label: it follows the map zoom but never drops below the readable minimum."""
        return max(round(MAP_MIN_PT * self.text_factor), int(size))

    def show_help(self):
        messagebox.showinfo("How it works",
                            "The jeep patrols a loop (Bottom Right > Top Right > Top Left > Bottom Left) and stops at every station. "
                            "You do not need to book or request anything: check the map and the Schedule, and wait at your station.\n\n"
                            "Plan trip shows the fare and the estimated waiting and riding times between two stations.\n\n"
                            "When the jeep is not needed (low battery, or an operator sends it back) it parks in the depot.\n\n"
                            "Between stations the jeep's position on the map is an estimate; "
                            "it is exact only at stations.\n\n"
                            "Fares and times are estimates.")
