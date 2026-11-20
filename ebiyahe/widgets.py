"""Small reusable screen parts: the card, the status badge, the message bar, the scroll frame, the header bar and the PIN window."""

import tkinter as tk
from tkinter import ttk

from config import APP_NAME, MESSAGE_S
from roles import OPERATOR, PASSENGER, ROLE_LABEL
from theme import F_HEADING, PAD, PAD_L, PAD_S, PALETTE, WRAP


# ======================= WIDGETS (small reusable screen parts) =======================
class Card(ttk.Frame):
    """A white raised panel with an optional bold heading: the one look for every titled group on screen
    (Connection, Map, Service mode, Live readout). Put the widgets inside `.body`, not inside the card itself.
    Widgets inside need the Card* styles (Card.TLabel, Card.TRadiobutton ...) so their background is white too."""

    def __init__(self, parent, title=None, padding=PAD_L):
        super().__init__(parent, style="Card.TFrame", padding=padding)
        if title:
            self.heading = ttk.Label(self, text=title, style="CardHeading.TLabel")
            self.heading.pack(anchor="w", pady=(0, PAD))
        self.body = ttk.Frame(self, style="CardInner.TFrame")
        self.body.pack(fill="both", expand=True)


class StatusBadge(ttk.Frame):
    """A colored dot followed by a short status word, for example a green dot and 'Driving'.
    Color plus text means the state never depends on color alone."""

    def __init__(self, parent):
        super().__init__(parent, style="CardInner.TFrame")
        # ----- the dot -----
        self.dot = tk.Canvas(self, width=16, height=16, bg=PALETTE["card"], highlightthickness=0)
        self.dot_id = self.dot.create_oval(2, 2, 14, 14, fill=PALETTE["disabled"], outline="")
        self.dot.pack(side="left")
        # ----- the word -----
        self.label = ttk.Label(self, text="Offline", style="CardHeading.TLabel")
        self.label.pack(side="left", padx=(PAD_S, 0))

    def set(self, text, color):
        """Show `text` next to a dot of `color`."""
        self.dot.itemconfig(self.dot_id, fill=color)
        self.label.config(text=text, foreground=color)


class MessageBar(ttk.Frame):
    """One-line message area at the bottom of the window.
    Every confirmation, warning and error from any tab appears here, in the same place and with the
    same colored dot, then the bar returns to 'Ready.' after a few seconds (see MESSAGE_S)."""

    LEVEL_COLOR = {"info": "muted", "ok": "ok", "warn": "warn", "error": "danger"}
    READY_TEXT = "Ready."

    def __init__(self, parent):
        super().__init__(parent, style="CardInner.TFrame")
        self.timer = None                         # the pending "return to Ready" timer, if any
        # ----- divider line above the bar -----
        ttk.Separator(self).pack(side="top", fill="x")
        # ----- colored dot and message text -----
        row = ttk.Frame(self, style="CardInner.TFrame", padding=(PAD, PAD_S))
        row.pack(fill="x")
        self.dot = tk.Canvas(row, width=16, height=16, bg=PALETTE["card"], highlightthickness=0)
        self.dot_id = self.dot.create_oval(2, 2, 14, 14, fill=PALETTE["disabled"], outline="")
        self.dot.pack(side="left")
        self.label = ttk.Label(row, text=self.READY_TEXT, style="Card.TLabel")
        self.label.pack(side="left", padx=(PAD_S, 0))
        row.bind("<Configure>", lambda e: self.label.config(wraplength=max(200, e.width - 48)))   # wrap long text

    def show(self, text, level="info"):
        """Show `text` with a dot in the color for `level` ('info', 'ok', 'warn' or 'error'),
        then go back to 'Ready.' after MESSAGE_S[level] seconds. A newer message replaces an older one."""
        if self.timer:
            self.after_cancel(self.timer)
        self.dot.itemconfig(self.dot_id, fill=PALETTE[self.LEVEL_COLOR[level]])
        self.label.config(text=text)
        self.timer = self.after(int(MESSAGE_S[level] * 1000), self.clear)

    def clear(self):
        """Return to the quiet 'Ready.' state."""
        self.timer = None
        self.dot.itemconfig(self.dot_id, fill=PALETTE["disabled"])
        self.label.config(text=self.READY_TEXT)


class ScrollFrame(ttk.Frame):
    """A frame whose content scrolls up and down when it is taller than the space it is given.
    Put the widgets inside `.body`. It scrolls with the scroll bar, with the mouse wheel, and by itself
    when the keyboard focus moves to a control that is out of view (so Tab never lands on something you cannot see)."""

    WHEEL_CLASSES = ("Treeview", "TCombobox", "TSpinbox", "Text", "Listbox")   # these use the wheel themselves

    def __init__(self, parent):
        super().__init__(parent)
        self.requested = (0, 0)                               # the size the content asked for last time
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # ----- the viewport (a canvas) and its scroll bar -----
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, bg=PALETTE["bg"], yscrollincrement=16)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        # ----- the content frame that sits inside the viewport -----
        self.body = ttk.Frame(self.canvas)
        self.window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", self.refresh)
        self.canvas.bind("<Configure>", self.refresh)

        # ----- mouse wheel and keyboard focus (each handler first checks that the event concerns this frame) -----
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(sequence, self.on_wheel, add="+")
        self.bind_all("<FocusIn>", self.on_focus, add="+")

    def refresh(self, event=None):
        """Make the content as wide as the viewport and at least as tall (so tabs can still stretch),
        pass the content's size on to the canvas as its requested size, and set how far it can scroll."""
        view_w, view_h = self.canvas.winfo_width(), self.canvas.winfo_height()
        need_w, need_h = self.body.winfo_reqwidth(), self.body.winfo_reqheight()
        width, height = max(view_w, need_w), max(view_h, need_h)
        self.canvas.itemconfigure(self.window, width=width, height=height)
        self.canvas.configure(scrollregion=(0, 0, width, height))
        if (need_w, need_h) != self.requested:                # the window sizes itself from this request
            self.requested = (need_w, need_h)
            self.canvas.configure(width=need_w, height=need_h)

    def contains(self, widget):
        """True if `widget` is this frame or sits anywhere inside it."""
        while widget is not None:
            if widget is self:
                return True
            widget = getattr(widget, "master", None)
        return False

    def on_wheel(self, event):
        """Mouse wheel over the content scrolls it (tables, drop-down boxes and number boxes keep their own wheel use)."""
        try:
            under = self.winfo_containing(event.x_root, event.y_root)
        except (KeyError, tk.TclError):                       # the pointer is over a drop-down list
            return
        if under is None or not self.contains(under) or under.winfo_class() in self.WHEEL_CLASSES:
            return
        if self.body.winfo_reqheight() <= self.canvas.winfo_height():
            return                                            # everything fits: nothing to scroll
        step = -1 if (event.num == 4 or getattr(event, "delta", 0) > 0) else 1
        self.canvas.yview_scroll(step * 3, "units")

    def on_focus(self, event):
        """When keyboard focus lands on a control that is partly out of view, scroll just far enough to show it."""
        w = event.widget
        if not hasattr(w, "winfo_rooty") or w is self.canvas or not self.contains(w):
            return
        top = w.winfo_rooty() - self.body.winfo_rooty()       # the control's position inside the content
        bottom = top + w.winfo_height()
        view_top, view_h = self.canvas.canvasy(0), self.canvas.winfo_height()
        total = max(self.body.winfo_height(), 1)
        if top < view_top:
            self.canvas.yview_moveto(max(top - PAD, 0) / total)
        elif bottom > view_top + view_h:
            self.canvas.yview_moveto((bottom - view_h + PAD) / total)


class HeaderBar(ttk.Frame):
    """The bar at the top of the window: the app name and italicized tagline centered; on the right the current mode,
    the emergency stop (operators only) and the sign-in / sign-out button. The bar turns blue in Operator mode so the mode
    is never in doubt."""

    def __init__(self, parent, on_sign_in, on_sign_out, on_estop):
        super().__init__(parent, style="Header.TFrame", padding=(PAD_L, PAD))
        self.on_sign_in, self.on_sign_out = on_sign_in, on_sign_out
        self.role = PASSENGER

        # ----- center: stacked bold app name and italicized tagline -----
        self.title_box = ttk.Frame(self, style="Header.TFrame")
        self.title_box.place(relx=0.5, rely=0.5, anchor="center")
        self.app_name = ttk.Label(self.title_box, text=APP_NAME, style="Header.TLabel")
        self.app_name.pack(side="top")
        self.tagline = ttk.Label(self.title_box, text="Ibiyahe mo with E-Biyahe!", style="HeaderTagline.TLabel")
        self.tagline.pack(side="top")

        # ----- right side (packed right to left): button, mode label, then the emergency stop -----
        self.button = ttk.Button(self, command=self.on_button)
        self.button.pack(side="right", pady=PAD_S)
        self.mode_label = ttk.Label(self, style="HeaderMuted.TLabel")
        self.mode_label.pack(side="right", padx=PAD_L)
        self.estop = ttk.Button(self, text="EMERGENCY STOP", style="Danger.TButton", command=on_estop)
        self.show_role(PASSENGER)

    def on_button(self):
        """The right-hand button signs in (passengers) or out (operators)."""
        if self.role == OPERATOR:
            self.on_sign_out()
        else:
            self.on_sign_in()

    def show_role(self, role):
        """Change colors, texts and the emergency stop to match the role."""
        self.role = role
        op = role == OPERATOR
        suffix = "Op" if op else ""
        self.configure(style=f"Header{suffix}.TFrame")
        self.title_box.configure(style=f"Header{suffix}.TFrame")
        self.app_name.configure(style=f"Header{suffix}.TLabel")
        self.tagline.configure(style=f"Header{suffix}Tagline.TLabel")
        self.mode_label.configure(text=ROLE_LABEL[role], style=f"Header{suffix}.TLabel" if op else "HeaderMuted.TLabel")
        self.button.configure(text="Sign out" if op else "Operator sign-in")
        if op:
            self.estop.pack(side="right", padx=(0, PAD))
        else:
            self.estop.pack_forget()


class PinDialog(tk.Toplevel):
    """A small window that asks for the operator PIN. check(pin) says whether it is right, on_ok() runs after a
    correct PIN and on_close() runs whenever the window closes. A wrong PIN is explained inside the window."""

    def __init__(self, parent, check, on_ok, on_close):
        super().__init__(parent)
        self.check, self.on_ok, self.on_close = check, on_ok, on_close
        self.closed = False
        self.title("Operator sign-in")
        self.configure(bg=PALETTE["bg"])
        self.transient(parent)
        self.resizable(False, False)

        # ----- heading, instruction, masked PIN box and error line -----
        body = ttk.Frame(self, padding=PAD_L)
        body.pack()
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        ttk.Label(body, text="Operator sign-in", font=F_HEADING).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(body, text="Enter the operator PIN to unlock the dispatch controls.", style="Muted.TLabel",
                  wraplength=WRAP - 60).grid(row=1, column=0, columnspan=2, sticky="w", pady=(PAD_S, 0))
        self.pin = tk.StringVar()
        self.entry = ttk.Entry(body, textvariable=self.pin, show="\u2022", width=16)
        self.entry.grid(row=2, column=0, columnspan=2, sticky="we", pady=(PAD, 0))
        self.error = tk.StringVar()
        ttk.Label(body, textvariable=self.error, foreground=PALETTE["danger"], wraplength=WRAP - 60).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(PAD_S, 0))

        # ----- buttons -----
        ttk.Button(body, text="Sign in", style="Primary.TButton", command=self.submit).grid(
            row=4, column=0, sticky="we", pady=(PAD, 0), padx=(0, PAD_S))
        ttk.Button(body, text="Cancel", command=self.close).grid(row=4, column=1, sticky="we", pady=(PAD, 0))

        # ----- keys: Enter signs in, Escape cancels -----
        for key in ("<Return>", "<KP_Enter>"):
            self.bind(key, lambda e: self.submit())
        self.bind("<Escape>", lambda e: self.close())
        self.protocol("WM_DELETE_WINDOW", self.close)

        # ----- put it over the middle of the main window, take the keyboard, and focus the PIN box -----
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:                                    # some systems refuse a grab; the window still works
            pass
        self.entry.focus_set()

    def submit(self):
        """Check the PIN: close and continue if it is right, otherwise explain and let the user try again."""
        if self.check(self.pin.get()):
            self.close()
            self.on_ok()
        else:
            self.error.set("Wrong PIN. Please try again.")
            self.pin.set("")
            self.entry.focus_set()

    def close(self):
        """Close the window (once) and tell the app."""
        if self.closed:
            return
        self.closed = True
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
        self.on_close()