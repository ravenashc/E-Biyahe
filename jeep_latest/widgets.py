"""Small reusable screen parts: the card, the status badge, the message bar, the scroll frame, the header bar and the PIN window."""

import tkinter as tk
from tkinter import font as tkfont, ttk

from config import APP_NAME, MESSAGE_S
from helpers import rrect
from jeepney import draw_jeepney
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


class Pill(tk.Canvas):
    """One rounded tab name. Selected: blue with white text. Under the mouse: a darker fill and a blue outline.
    With the keyboard focus: a dotted inner outline. It is a canvas (not a ttk widget) because ttk cannot round corners."""

    def __init__(self, parent, text, command):
        super().__init__(parent, highlightthickness=0, borderwidth=0, bg=PALETTE["bg"], takefocus=1, cursor="hand2")
        self.bg_role = "bg"                                   # the palette color this canvas follows when the mode changes
        self.text, self.command = text, command
        self.selected = self.hover = self.focused = False
        for sequence, hover, focused in (("<Enter>", True, None), ("<Leave>", False, None),
                                         ("<FocusIn>", None, True), ("<FocusOut>", None, False)):
            self.bind(sequence, lambda e, h=hover, f=focused: self.set_state(hover=h, focused=f))
        self.bind("<Button-1>", lambda e: self.command())
        for key in ("<Return>", "<KP_Enter>", "<space>"):
            self.bind(key, lambda e: self.command())
        self.draw()

    def set_state(self, hover=None, focused=None):
        """Change the mouse or keyboard state (None leaves it as it is) and redraw."""
        if hover is not None:
            self.hover = hover
        if focused is not None:
            self.focused = focused
        self.draw()

    def set_selected(self, selected):
        self.selected = selected
        self.draw()

    def set_text(self, text):
        self.text = text
        self.draw()

    def draw(self):
        """Redraw at the size the text needs. Always measured in the bold font, so choosing a pill never changes its width."""
        font = tkfont.nametofont(F_HEADING)
        w = font.measure(self.text) + 2 * PAD_L + 4
        h = font.metrics("linespace") + PAD + 4
        if self.selected:
            fill, ink, edge = PALETTE["accent"], PALETTE["on_color"], PALETTE["accent"]
        elif self.hover:
            fill, ink, edge = PALETTE["hover"], PALETTE["text"], PALETTE["accent"]
        else:
            fill, ink, edge = PALETTE["header"], PALETTE["muted"], PALETTE["border"]
        self.configure(width=w, height=h)
        self.delete("all")
        self.create_polygon(rrect(1, 1, w - 1, h - 1, (h - 2) / 2), smooth=True, fill=fill, outline=edge, width=1)
        self.create_text(w / 2, h / 2, text=self.text, font=F_HEADING, fill=ink)
        if self.focused:
            self.create_polygon(rrect(5, 5, w - 5, h - 5, (h - 10) / 2), smooth=True, fill="", outline=ink, dash=(2, 2))


class PillTabs(ttk.Frame):
    """The tab names for a ttk.Notebook, drawn as a row of rounded pills above it. The notebook still holds the pages
    and does the switching (its own tab strip is hidden, see theme.py), so nb.select(), Ctrl+Tab and the Ctrl+1 ... Ctrl+4
    shortcuts keep working. Call refresh() after changing a tab's text or hiding / showing a tab, and relayout() after the
    text size changes. Left and Right arrows move between pills when one has the keyboard focus."""

    def __init__(self, parent, notebook):
        super().__init__(parent)
        self.nb = notebook
        self.pills = []
        for i in range(len(notebook.tabs())):
            pill = Pill(self, notebook.tab(i, "text"), lambda i=i: self.nb.select(i))
            pill.bind("<Left>", lambda e, i=i: self.step(i, -1))
            pill.bind("<Right>", lambda e, i=i: self.step(i, 1))
            self.pills.append(pill)
        notebook.bind("<<NotebookTabChanged>>", lambda e: self.sync(), add="+")
        self.refresh()

    def visible(self, i):
        return self.nb.tab(i, "state") != "hidden"

    def refresh(self):
        """Match the pills to the notebook: their texts, which tabs are shown (in order) and which one is selected."""
        for i, pill in enumerate(self.pills):
            pill.set_text(self.nb.tab(i, "text"))
            pill.pack_forget()
        for i, pill in enumerate(self.pills):
            if self.visible(i):
                pill.pack(side="left", padx=(0, PAD_S))
        self.sync()

    def sync(self):
        """Mark the pill of the selected tab."""
        try:
            current = self.nb.index("current")
        except tk.TclError:                                   # no tab is selected yet
            current = -1
        for i, pill in enumerate(self.pills):
            pill.set_selected(i == current)

    def relayout(self):
        """Redraw every pill (the fonts changed size)."""
        for pill in self.pills:
            pill.draw()

    def step(self, i, step):
        """Arrow key: select and focus the next (or previous) pill that is shown."""
        n = len(self.pills)
        for k in range(1, n):
            j = (i + step * k) % n
            if self.visible(j):
                self.nb.select(j)
                self.pills[j].focus_set()
                break
        return "break"


class StatusBadge(ttk.Frame):
    """A colored dot followed by a short status word, for example a green dot and 'Driving'.
    Color plus text means the state never depends on color alone."""

    def __init__(self, parent):
        super().__init__(parent, style="CardInner.TFrame")
        # ----- the dot -----
        self.dot = tk.Canvas(self, width=16, height=16, bg=PALETTE["card"], highlightthickness=0)
        self.dot.bg_role = "card"
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
        self.dot.bg_role = "card"
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
        self.enabled = True                                   # False: this frame never scrolls and shows no scroll bar (see set_scrolling)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # ----- the viewport (a canvas) and its scroll bar -----
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, bg=PALETTE["bg"], yscrollincrement=16)
        self.canvas.bg_role = "bg"
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
        if need_h <= view_h or not self.enabled:              # everything fits (or scrolling is off): no scroll bar to show
            self.scrollbar.grid_remove()
        else:
            self.scrollbar.grid()
        self.canvas.itemconfigure(self.window, width=width, height=height)
        self.canvas.configure(scrollregion=(0, 0, width, height))
        if (need_w, need_h) != self.requested:                # the window sizes itself from this request
            self.requested = (need_w, need_h)
            self.canvas.configure(width=need_w, height=need_h)

    def set_scrolling(self, on):
        """Turn scrolling on or off. Off: no scroll bar, the mouse wheel and the keyboard focus do not scroll, and the view
        goes back to the top. (Passengers get a screen that simply fits.)"""
        self.enabled = on
        if not on:
            self.canvas.yview_moveto(0)
        self.refresh()

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
        if not self.enabled or under is None or not self.contains(under) or under.winfo_class() in self.WHEEL_CLASSES:
            return
        if self.body.winfo_reqheight() <= self.canvas.winfo_height():
            return                                            # everything fits: nothing to scroll
        step = -1 if (event.num == 4 or getattr(event, "delta", 0) > 0) else 1
        self.canvas.yview_scroll(step * 3, "units")

    def on_focus(self, event):
        """When keyboard focus lands on a control that is partly out of view, scroll just far enough to show it."""
        w = event.widget
        if not self.enabled or not hasattr(w, "winfo_rooty") or w is self.canvas or not self.contains(w):
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
    and the sign-in / sign-out button. (The emergency stop is not here: it sits under the right-hand
    column, away from the routine buttons, so it cannot be hit by mistake.)"""

    def __init__(self, parent, on_sign_in, on_sign_out):
        super().__init__(parent, style="Header.TFrame", padding=(PAD_L, PAD))
        self.on_sign_in, self.on_sign_out = on_sign_in, on_sign_out
        self.role = PASSENGER

        # ----- title: stacked bold app name and italicized tagline (centered when there is room, see layout_title) -----
        self.spacer = ttk.Frame(self, style="Header.TFrame", width=1)       # gives the bar the title's height (a placed widget adds none)
        self.spacer.pack(side="left")
        self.title_box = ttk.Frame(self, style="Header.TFrame")
        self.title_box.place(relx=0.5, rely=0.5, anchor="center")
        self.name_row = ttk.Frame(self.title_box, style="Header.TFrame")       # the jeepney mark, then the name
        self.name_row.pack(side="top")
        self.mark = tk.Canvas(self.name_row, highlightthickness=0, bg=PALETTE["card"], width=1, height=1)
        self.mark.pack(side="left", padx=(0, PAD))
        self.app_name = ttk.Label(self.name_row, text=APP_NAME, style="Header.TLabel")
        self.app_name.pack(side="left")
        self.app_name.bind("<Configure>", self.draw_mark)                      # redraw at the right size when the text size changes
        self.tagline = ttk.Label(self.title_box, text="Ibiyahe mo with E-Biyahe!", style="HeaderTagline.TLabel")
        self.tagline.pack(side="top")

        # ----- right side (packed right to left): sign-in button, then the mode label -----
        self.button = ttk.Button(self, command=self.on_button)
        self.button.pack(side="right", pady=PAD_S)
        self.mode_label = ttk.Label(self, style="HeaderMuted.TLabel")
        self.mode_label.pack(side="right", padx=PAD_L)
        self.show_role(PASSENGER)
        self.bind("<Configure>", self.layout_title)
        self.title_box.bind("<Configure>", self.layout_title)       # the title changed size (text size step): re-center and re-measure

    def draw_mark(self, event=None):
        """Draw the small jeepney next to the app name, as tall as the name's text, in colors that suit the bar."""
        op = self.role == OPERATOR
        h = max(self.app_name.winfo_reqheight(), 24)
        bh = h * 0.30
        bw = bh * 1.85
        w = int(2 * bw + 4)
        bg = PALETTE["op_bar"] if op else PALETTE["card"]
        self.mark.configure(width=w, height=h, bg=bg)
        self.mark.delete("all")
        body, ink = (PALETTE["on_color"], PALETTE["on_color"]) if op else (PALETTE["accent"], PALETTE["text"])
        draw_jeepney(self.mark, w / 2, h / 2 + 0.08 * bh, bw, bh, body, bg, ink)     # centre the compact roof-to-wheel silhouette

    def layout_title(self, event=None):
        """Center the title in the bar when it fits clear of the buttons on the right; otherwise keep it at the left edge.
        (The mode label and the button can crowd a narrow bar.)"""
        self.update_idletasks()
        title_w, bar_w = self.title_box.winfo_reqwidth(), self.winfo_width()
        right = [w for w in (self.mode_label, self.button) if w.winfo_manager()]
        right_edge = min(w.winfo_x() for w in right)                       # where the right-hand group begins
        if (bar_w + title_w) / 2 + PAD_L <= right_edge:
            self.title_box.place_configure(relx=0.5, x=0, rely=0.5, anchor="center")
        else:
            self.title_box.place_configure(relx=0, x=PAD_L, rely=0.5, anchor="w")
        self.spacer.configure(height=self.title_box.winfo_reqheight())

    def on_button(self):
        """The right-hand button signs in (passengers) or out (operators)."""
        if self.role == OPERATOR:
            self.on_sign_out()
        else:
            self.on_sign_in()

    def show_role(self, role):
        """Change colors and texts to match the role."""
        self.role = role
        op = role == OPERATOR
        suffix = "Op" if op else ""
        self.configure(style=f"Header{suffix}.TFrame")
        self.title_box.configure(style=f"Header{suffix}.TFrame")
        self.name_row.configure(style=f"Header{suffix}.TFrame")
        self.spacer.configure(style=f"Header{suffix}.TFrame")
        self.app_name.configure(style=f"Header{suffix}.TLabel")
        self.tagline.configure(style=f"Header{suffix}Tagline.TLabel")
        self.mode_label.configure(text=ROLE_LABEL[role], style=f"Header{suffix}.TLabel" if op else "HeaderMuted.TLabel")
        self.button.configure(text="Sign out" if op else "Operator sign-in", style=f"Header{suffix}.TButton")
        self.draw_mark()
        self.after_idle(self.layout_title)


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