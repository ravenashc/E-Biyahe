"""Builds the screens: menu bar, connection box, status card and the four tabs.

This is one part of the App window: App (app.py) inherits BuildMixin, so these methods are called as self.<name>()."""

import tkinter as tk
from tkinter import ttk

from config import CLOSE_TIME, DISCOUNTS, DWELL_S, OPEN_TIME, SERVICE_DAYS, TAB_NAMES
from helpers import fmt12
from roles import OPERATOR, allowed
from theme import F_BODY, F_DISPLAY, F_HEADING, F_SMALL, F_TITLE, LOG_LEVELS, PAD, PAD_L, PAD_S, PALETTE, RIGHT_W, WRAP
from widgets import Card, MessageBar, PillTabs, ScrollFrame, StatusBadge


# ======================= BUILDING THE SCREENS =======================
class BuildMixin:
    """Builds the screens: menu bar, connection box, status card and the four tabs."""

    # ---------- layout ----------
    def build_ui(self):
        """Assemble the window: menu bar, map on the left, status and tabs on the right."""
        # ----- menu bar -----
        self.build_menu()
        # ----- message bar at the bottom: all feedback appears here -----
        self.bar = MessageBar(self)
        self.bar.pack(side="bottom", fill="x")
        # ----- header bar at the top: mode and sign-in / sign-out -----
        self.build_header()
        # ----- main frame -----
        root = ttk.Frame(self, padding=PAD)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        # ----- left side: the map -----
        left = Card(root, "Map", padding=PAD)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, PAD))
        self.cv = tk.Canvas(left.body, bg=PALETTE["map_bg"], highlightthickness=1, highlightbackground=PALETTE["border"])
        self.cv.bg_role, self.cv.edge_role = "map_bg", "border"      # followed when the mode changes (see apply_mode_colors)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Configure>", lambda e: self.draw_static())
        self.hover_item = None                           # what the mouse is over on the map: ("stop", i), ("jeep", 0) or None
        self.cv.bind("<Motion>", self.on_map_motion)
        self.cv.bind("<Leave>", self.on_map_leave)
        # ----- right side: connection, status card and tabs (inside a frame that scrolls when the window is short) -----
        self.scroll = ScrollFrame(root)
        self.scroll.grid(row=0, column=1, sticky="ns")
        # ----- emergency stop: fixed under the right-hand column (outside the scrolling part), so it is always in view,
        #       next to the jeep's status and away from the routine buttons in the header. Shown to operators only. -----
        self.estop = ttk.Button(root, text="EMERGENCY STOP", style="Danger.TButton", command=self.do_estop)
        self.estop.grid(row=1, column=1, sticky="ew", pady=(PAD, 0))
        self.estop.grid_remove()
        right = self.scroll.body
        self.right_min = ttk.Frame(right, width=RIGHT_W, height=1)     # holds the column at a steady width (see RIGHT_W)
        self.right_min.pack()
        self.build_status(right)
        self.nb = ttk.Notebook(right, style="Pill.TNotebook", takefocus=0)     # holds the pages; the tab names are the pills
        self.nb.pack(fill="both", expand=True, pady=(PAD, 0))
        builders = (self.build_trip, self.build_schedule, self.build_operator, self.build_log)
        for name, build in zip(TAB_NAMES, builders):
            self.nb.add(build(self.nb), text=name)
        self.nb.enable_traversal()     # Ctrl+Tab and Ctrl+Shift+Tab switch tabs
        self.pills = PillTabs(right, self.nb)
        self.pills.pack(fill="x", pady=(PAD, 0), before=self.nb)
        self.nb.pack_configure(pady=(PAD_S, 0))
        # where the keyboard focus lands when a tab is chosen with Ctrl+1 ... Ctrl+4 (never a control that acts at once)
        self.tab_focus = [self.cb_from, self.pills.pills[1], self.dwell_spin, self.logtree]
        # table column widths at normal text size, so a larger text size can scale them
        self.col_base = [(t, {c: int(t.column(c, "width")) for c in t["columns"]})
                         for t in (self.tree, self.logtree)]

    def build_menu(self):
        """Menu bar: File, Ride, Operator, View, Demo and Help. Every item that has a shortcut shows it.
        Items and menus reserved for operators exist only in Operator mode (see roles.py)."""
        bar = tk.Menu(self)
        role = self.role
        table = {row[0]: row for row in self.shortcuts}

        def item(menu, ident, label=None):
            if not allowed(role, "shortcuts", ident):
                return
            _id, keys, _patterns, what, action = table[ident]
            menu.add_command(label=label or what, accelerator=keys, command=action)

        m_file = tk.Menu(bar, tearoff=0)
        item(m_file, "signin", "Sign out of Operator mode" if role == OPERATOR else "Operator sign-in...")
        item(m_file, "connect")
        item(m_file, "export")
        m_file.add_separator()
        item(m_file, "quit")
        bar.add_cascade(label="File", menu=m_file, underline=0)
        if allowed(role, "menus", "Operator"):
            m_op = tk.Menu(bar, tearoff=0)
            for ident in ("dispatch", "reset"):
                item(m_op, ident)
            m_op.add_separator()
            item(m_op, "estop")
            bar.add_cascade(label="Operator", menu=m_op, underline=0)
        m_view = tk.Menu(bar, tearoff=0)
        for i in range(1, len(TAB_NAMES) + 1):
            item(m_view, f"tab{i}")
        m_view.add_separator()
        for ident in ("bigger", "smaller", "normal"):
            item(m_view, ident)
        bar.add_cascade(label="View", menu=m_view, underline=0)
        if allowed(role, "menus", "Demo"):
            m_demo = tk.Menu(bar, tearoff=0)
            for text, what in (("Simulate obstacle", "obstacle"), ("Simulate line lost", "lineloss"),
                               ("Simulate low battery", "lowbatt"), ("Simulate Wi-Fi drop (8 s)", "wifi")):
                m_demo.add_command(label=text, command=lambda w=what, t=text: self.sim(w, t))
            bar.add_cascade(label="Demo", menu=m_demo, underline=0)
        m_help = tk.Menu(bar, tearoff=0)
        m_help.add_command(label="How it works", command=self.show_help)
        item(m_help, "help")
        bar.add_cascade(label="Help", menu=m_help, underline=0)
        self.config(menu=bar)

    def build_connection(self, parent):
        """Connection box: choose Demo or Wi-Fi and press Connect (the jeep's address is DEFAULT_HOST in config.py). It sits in the Operator tab."""
        card = Card(parent, "Connection")
        card.pack(fill="x", pady=(PAD, 0))
        self.conn_box = card                     # shown to operators only (see apply_role)
        f = card.body
        ttk.Radiobutton(f, text="Demo (no jeep)", variable=self.mode_var, value="demo", style="Card.TRadiobutton").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(f, text="Wi-Fi jeep", variable=self.mode_var, value="wifi", style="Card.TRadiobutton").grid(row=0, column=1, sticky="w")
        self.btn_conn = ttk.Button(f, text="Connect", command=self.toggle_connection)
        self.btn_conn.grid(row=0, column=2, sticky="e", padx=(PAD, 0))
        self.v_conn = tk.StringVar(value="Not connected")
        ttk.Label(f, textvariable=self.v_conn, style="CardMuted.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(PAD, 0))

    def build_status(self, parent):
        """Status card. The current state, next stop, arrival estimate and important alerts stay visible at a glance."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=(PAD_L, PAD))
        card.pack(fill="x")
        self.status_card = card
        card.columnconfigure(0, weight=1)
        card.columnconfigure(1, weight=1)

        # ----- values shown in this card (changing one updates the screen) -----
        self.v_next = tk.StringVar()
        self.v_alert = tk.StringVar()

        # ----- top line: the live state (colored dot and word), then a thin rule -----
        self.badge = StatusBadge(card)
        self.badge.grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Separator(card).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(PAD_S, PAD_S))

        # ----- next-stop information (live ETA intentionally omitted) -----
        ttk.Label(card, style="CardMuted.TLabel", text="Next stop").grid(row=2, column=0, sticky="w")
        ttk.Label(card, textvariable=self.v_next, style="CardDisplay.TLabel").grid(row=3, column=0, sticky="w")
        self.reserve_width(card, 0, F_DISPLAY, self.short_names)

        # ----- alert line: its two lines of room are always kept, so an alert appearing never pushes the tabs down -----
        self.lbl_alert = ttk.Label(card, textvariable=self.v_alert, style="Alert.TLabel", wraplength=WRAP)
        self.lbl_alert.grid(row=4, column=0, columnspan=2, sticky="nw", pady=(PAD_S, 0))
        self.reserve(card, 4, F_HEADING, 2)

    def build_trip(self, nb):
        """Passenger trip planner: choose boarding and alighting stops to look up fare and estimated times."""
        f = ttk.Frame(nb, padding=PAD)
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)

        # Full station names use the full card width and are stacked to remain readable.
        ttk.Label(f, text="Ride on at").grid(row=0, column=0, columnspan=2, sticky="w")
        self.from_var = tk.StringVar(value=self.names[0])
        self.cb_from = ttk.Combobox(f, values=self.names, textvariable=self.from_var, state="readonly", width=22)
        self.cb_from.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(PAD_S, 0))

        ttk.Label(f, text="Get off at").grid(row=2, column=0, columnspan=2, sticky="w", pady=(PAD, 0))
        self.to_var = tk.StringVar(value=self.names[2])
        self.cb_to = ttk.Combobox(f, values=self.names, textvariable=self.to_var, state="readonly", width=22)
        self.cb_to.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(PAD_S, 0))

        ttk.Label(f, text="Passenger").grid(row=4, column=0, sticky="w", pady=(PAD, 0))
        ttk.Label(f, text="Fare").grid(row=4, column=1, sticky="w", padx=(PAD, 0), pady=(PAD, 0))
        self.cat_var = tk.StringVar(value="Regular")
        ttk.Combobox(f, values=list(DISCOUNTS), textvariable=self.cat_var, state="readonly", width=11).grid(
            row=5, column=0, sticky="w", pady=(PAD_S, 0))
        self.v_route, self.v_fare, self.v_wait = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.v_ride, self.v_total, self.v_arrive = tk.StringVar(), tk.StringVar(), tk.StringVar()
        ttk.Label(f, textvariable=self.v_fare, font=F_TITLE, width=9).grid(
            row=5, column=1, sticky="w", padx=(PAD, 0), pady=(PAD_S, 0))

        ttk.Label(f, textvariable=self.v_route, wraplength=WRAP, style="Muted.TLabel").grid(
            row=6, column=0, columnspan=2, sticky="nw", pady=(PAD, 0))
        self.reserve(f, 6, F_BODY, 1)
        sm = ttk.Frame(f)
        sm.grid(row=7, column=0, columnspan=2, sticky="w", pady=(PAD_S, 0))
        rows = (("Jeep reaches you in", self.v_wait), ("Ride time", self.v_ride),
                ("Total", self.v_total), ("You arrive at", self.v_arrive))
        for r, (label, value) in enumerate(rows):
            ttk.Label(sm, text=label).grid(row=r, column=0, sticky="w")
            ttk.Label(sm, textvariable=value, font=F_HEADING, width=11).grid(
                row=r, column=1, sticky="w", padx=(PAD, 0))
        return f

    def build_schedule(self, nb):
        """Schedule tab: operating hours, service status and when the jeep passes each station."""
        f = ttk.Frame(nb, padding=(PAD, PAD_S))
        ttk.Label(f, font=F_HEADING, text=f"Operating hours: {fmt12(OPEN_TIME)} to {fmt12(CLOSE_TIME)}").pack(anchor="w")
        ttk.Label(f, text=SERVICE_DAYS).pack(anchor="w")
        self.v_service = tk.StringVar()
        self.lbl_service = ttk.Label(f, textvariable=self.v_service, font=F_HEADING)
        self.lbl_service.pack(anchor="w", pady=(2, 2))
        self.v_svc = tk.StringVar()
        ttk.Label(f, textvariable=self.v_svc, wraplength=WRAP).pack(anchor="w", pady=(0, PAD_S))
        self.tree = ttk.Treeview(f, columns=("stn", "next", "after"), show="headings", height=4,
                                 style="Compact.Treeview", takefocus=0)            # read-only: nothing to do in it, so Tab skips it
        for c, t, w in (("stn", "Station", 140), ("next", "Jeep passes", 68), ("after", "Following", 68)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        for i, n in enumerate(self.names):
            self.tree.insert("", "end", iid=str(i), values=(n, "-", "-"))
        self.tree.pack(fill="x")
        return f

    def build_operator(self, nb):
        """Operator tab: vehicle controls, service settings and a live readout from the jeep."""
        f = ttk.Frame(nb, padding=PAD)

        # ----- dispatch buttons -----
        bar = ttk.Frame(f)
        bar.pack(fill="x")
        # each button sits in its own column with the reason it is off right under it (shown only then)
        specs = (("btn_dispatch", "lbl_dispatch_hint", "Dispatch", "Primary.TButton", self.do_dispatch),
                 ("btn_reset", "lbl_reset_hint", "Reset", "TButton", lambda: self.op("reset")))
        for col, (btn_name, hint_name, text, style, command) in enumerate(specs):
            pad = (0 if col == 0 else PAD, 0)
            button = ttk.Button(bar, text=text, style=style, command=command)
            button.grid(row=0, column=col, sticky="we", padx=pad)
            hint = ttk.Label(bar, wraplength=100, style="Hint.TLabel", justify="left")
            hint.grid(row=1, column=col, sticky="nw", padx=pad, pady=(PAD_S, 0))
            setattr(self, btn_name, button)
            setattr(self, hint_name, hint)
        self.reserve(bar, 1, F_SMALL, 2)                   # room for the reasons under the buttons is always kept (see set_hint)

        # ----- emergency stop: it lives under the right-hand column (visible from every tab and never disabled), so only a reminder here -----
        ttk.Label(f, text="EMERGENCY STOP is the red button at the bottom of this column.", style="Muted.TLabel",
                  wraplength=WRAP).pack(anchor="w", pady=(PAD, PAD_S))

        # ----- service setting: how long the jeep waits at each station (it patrols and stops at every one) -----
        mc = Card(f, "Station stop")
        mc.pack(fill="x")
        mf = mc.body
        df = ttk.Frame(mf, style="CardInner.TFrame")
        df.pack(fill="x")
        ttk.Label(df, text="Dwell time (s)", style="Card.TLabel").pack(side="left")
        self.dwell_var = tk.StringVar(value=str(int(DWELL_S)))
        self.dwell_spin = spin = ttk.Spinbox(df, from_=1, to=30, width=5, textvariable=self.dwell_var)
        spin.pack(side="left", padx=PAD)
        spin.bind("<Return>", lambda e: self.set_dwell())      # Enter in the box = press Set
        ttk.Button(df, text="Set", command=self.set_dwell).pack(side="left")
        # ----- connection (setup, so it sits with the other operator settings instead of above the status card) -----
        self.build_connection(f)
        # ----- live readout -----
        rc = Card(f, "Live readout (from the jeep)")
        rc.pack(fill="x", pady=(PAD, 0))
        self.live_card = rc                      # the connection card is packed just above this one (see apply_role)
        rf = rc.body
        self.ov = {k: tk.StringVar(value="-") for k in ("state", "batt", "sensors")}
        for r, (k, t) in enumerate((("state", "State"), ("sensors", "Sensors"))):
            ttk.Label(rf, text=t, style="CardMuted.TLabel").grid(row=r, column=0, sticky="nw", pady=2)
            ttk.Label(rf, textvariable=self.ov[k], style="Card.TLabel", wraplength=WRAP - 110).grid(
                row=r, column=1, sticky="w", padx=PAD, pady=2)
        self.reserve(rf, 1, F_BODY, 2)                     # the battery and sensor lines may wrap: keep room for two lines each
        self.reserve(rf, 2, F_BODY, 2)
        return f

    def apply_log_tags(self):
        """One tag per severity and stripe, in the colors of the current mode (called again when the mode changes)."""
        for level, (_label, color, even, odd) in LOG_LEVELS.items():
            self.logtree.tag_configure(f"{level}_even", foreground=color, background=even)
            self.logtree.tag_configure(f"{level}_odd", foreground=color, background=odd)

    def build_log(self, nb):
        """Log tab: a striped table of everything that happened, colored by severity (also saved to a file)."""
        f = ttk.Frame(nb, padding=PAD)
        self.logtree = ttk.Treeview(f, columns=("time", "level", "event"), show="headings", height=8)
        self.logtree.heading("time", text="Time")
        self.logtree.heading("level", text="Level")
        self.logtree.heading("event", text="Event")
        self.logtree.column("time", width=78, anchor="w", stretch=False)
        self.logtree.column("level", width=62, anchor="w", stretch=False)
        self.logtree.column("event", width=160, anchor="w")
        self.apply_log_tags()
        sb = ttk.Scrollbar(f, orient="vertical", command=self.logtree.yview)
        self.logtree.configure(yscrollcommand=sb.set)
        self.logtree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        f.rowconfigure(0, weight=1)
        f.columnconfigure(0, weight=1)
        buttons = ttk.Frame(f)
        buttons.grid(row=1, column=0, columnspan=2, sticky="w", pady=(PAD, 0))
        ttk.Button(buttons, text="Clear list", command=self.clear_log).pack(side="left")
        ttk.Button(buttons, text="Export...", command=self.export_log).pack(side="left", padx=(PAD, 0))
        ttk.Label(f, text="Every event is also saved to data/log.csv", style="Muted.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w")
        return f
