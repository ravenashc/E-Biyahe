"""Builds the screens: menu bar, connection box, status card and the five tabs.

This is one part of the App window: App (app.py) inherits BuildMixin, so these methods are called as self.<name>()."""

import time
import tkinter as tk
from tkinter import ttk

from config import CLOSE_TIME, DISCOUNTS, DWELL_S, OPEN_TIME, SERVICE_DAYS, TAB_NAMES
from helpers import fmt12
from roles import OPERATOR, allowed
from theme import F_HEADING, F_TITLE, LOG_LEVELS, PAD, PAD_L, PAD_S, PALETTE, RIGHT_W, WRAP
from widgets import Card, MessageBar, PillTabs, ScrollFrame, StatusBadge


# ======================= BUILDING THE SCREENS =======================
class BuildMixin:
    """Builds the screens: menu bar, connection box, status card and the five tabs."""

    # ---------- layout ----------
    def build_ui(self):
        """Assemble the window: menu bar, map on the left, status and tabs on the right."""
        # ----- menu bar -----
        self.build_menu()
        # ----- message bar at the bottom: all feedback appears here -----
        self.bar = MessageBar(self)
        self.bar.pack(side="bottom", fill="x")
        # ----- header bar at the top: mode, sign-in / sign-out and (operators) the emergency stop -----
        self.build_header()
        # ----- main frame -----
        root = ttk.Frame(self, padding=PAD)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        # ----- left side: the map -----
        left = Card(root, "Map", padding=PAD)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, PAD))
        self.lab(left.heading, "map")
        self.cv = tk.Canvas(left.body, bg=PALETTE["map_bg"], highlightthickness=1, highlightbackground=PALETTE["border"])
        self.cv.bg_role, self.cv.edge_role = "map_bg", "border"      # followed when the mode changes (see apply_mode_colors)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Configure>", lambda e: self.draw_static())
        self.hover_item = None                           # what the mouse is over on the map: ("stop", i), ("jeep", 0) or None
        self.cv.bind("<Motion>", self.on_map_motion)
        self.cv.bind("<Leave>", self.on_map_leave)
        self.labels.on_change(self.draw_static)          # the map key and labels change language
        # ----- right side: connection, status card and tabs (inside a frame that scrolls when the window is short) -----
        self.scroll = ScrollFrame(root)
        self.scroll.grid(row=0, column=1, sticky="ns")
        right = self.scroll.body
        self.right_min = ttk.Frame(right, width=RIGHT_W, height=1)     # holds the column at a steady width (see RIGHT_W)
        self.right_min.pack()
        self.build_status(right)
        self.nb = ttk.Notebook(right, style="Pill.TNotebook", takefocus=0)     # holds the pages; the tab names are the pills
        self.nb.pack(fill="both", expand=True, pady=(PAD, 0))
        builders = (self.build_trip, self.build_rides, self.build_schedule, self.build_operator, self.build_log)
        for name, build in zip(TAB_NAMES, builders):
            self.nb.add(build(self.nb), text=name)
        self.nb.enable_traversal()     # Ctrl+Tab and Ctrl+Shift+Tab switch tabs
        self.pills = PillTabs(right, self.nb)
        self.pills.pack(fill="x", pady=(PAD, 0), before=self.nb)
        self.nb.pack_configure(pady=(PAD_S, 0))
        for i, key in enumerate(("tab_plan", "tab_rides", "tab_schedule")):    # Operator and Log stay in English (staff screens)
            self.labels.bind(key, lambda text, i=i: self.nb.tab(i, text=text))
        self.labels.on_change(self.pills.refresh)        # new tab names: the pills resize
        # where the keyboard focus lands when a tab is chosen with Ctrl+1 ... Ctrl+5 (never a control that acts at once)
        self.tab_focus = [self.cb_from, self.rtree, self.pills.pills[2], self.rad_ondemand, self.logtree]
        # table column widths at normal text size, so a larger text size can scale them
        self.col_base = [(t, {c: int(t.column(c, "width")) for c in t["columns"]})
                         for t in (self.rtree, self.tree, self.logtree)]

    def lab(self, widget, key, option="text", **values):
        """Give a widget's text from the label table (labels.py): it is set now and again whenever the language changes."""
        self.labels.bind(key, lambda text: widget.configure(**{option: text}), **values)
        return widget

    def lab_column(self, tree, column, key):
        """The same for a table column heading."""
        self.labels.bind(key, lambda text: tree.heading(column, text=text))

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
        m_ride = tk.Menu(bar, tearoff=0)
        for ident in ("request", "para", "cancel"):
            item(m_ride, ident)
        bar.add_cascade(label="Ride", menu=m_ride, underline=0)
        if allowed(role, "menus", "Operator"):
            m_op = tk.Menu(bar, tearoff=0)
            for ident in ("dispatch", "return", "reset"):
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
        m_view.add_separator()
        item(m_view, "language")
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
        """Connection box: choose Demo or Wi-Fi, set the jeep address and press Connect. It sits in the Operator tab."""
        card = Card(parent, "Connection")
        card.pack(fill="x", pady=(PAD, 0))
        self.conn_box = card                     # shown to operators only (see apply_role)
        f = card.body
        ttk.Radiobutton(f, text="Demo (no jeep)", variable=self.mode_var, value="demo", style="Card.TRadiobutton").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(f, text="Wi-Fi jeep", variable=self.mode_var, value="wifi", style="Card.TRadiobutton").grid(row=0, column=1, sticky="w")
        ttk.Label(f, text="Host", style="Card.TLabel").grid(row=1, column=0, sticky="e", pady=(PAD, 0))
        host = ttk.Entry(f, textvariable=self.host_var, width=16)
        host.grid(row=1, column=1, sticky="w", pady=(PAD, 0))
        ttk.Label(f, text="Port", style="Card.TLabel").grid(row=1, column=2, sticky="e", padx=(PAD, 0), pady=(PAD, 0))
        port = ttk.Entry(f, textvariable=self.port_var, width=6)
        port.grid(row=1, column=3, sticky="w", padx=(PAD_S, 0), pady=(PAD, 0))
        for entry in (host, port):               # Enter connects (it never disconnects by accident)
            entry.bind("<Return>", lambda e: None if self.source else self.connect())
        self.btn_conn = ttk.Button(f, text="Connect", command=self.toggle_connection)
        self.btn_conn.grid(row=0, column=3, sticky="e", padx=(PAD, 0))
        self.v_conn = tk.StringVar(value="Not connected")
        ttk.Label(f, textvariable=self.v_conn, style="CardMuted.TLabel").grid(row=2, column=0, columnspan=4, sticky="w", pady=(PAD, 0))

    def build_status(self, parent):
        """Status card. The most important facts (state, next stop, ETA) are large and sit at the top;
        battery and the Para button follow. Kept compact so the tabs below stay fully visible."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=(PAD_L, PAD))
        card.pack(fill="x")
        self.status_card = card
        card.columnconfigure(0, weight=1)

        # ----- values shown in this card (changing one updates the screen) -----
        self.v_next, self.v_eta, self.v_etaclock = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.v_last, self.v_batt = tk.StringVar(), tk.StringVar(value="Battery: -")
        self.v_alert = tk.StringVar()

        # ----- header: live state badge (left) and last station (right) -----
        self.badge = StatusBadge(card)
        self.badge.grid(row=0, column=0, sticky="w")
        ttk.Label(card, textvariable=self.v_last, style="CardMuted.TLabel").grid(
            row=0, column=1, sticky="e", padx=(PAD_L, 0))

        # ----- primary information: next stop (left) and arrival time (right) -----
        self.lab(ttk.Label(card, style="CardMuted.TLabel"), "next_stop").grid(row=1, column=0, sticky="w", pady=(PAD_S, 0))
        ttk.Label(card, textvariable=self.v_next, style="CardDisplay.TLabel").grid(row=2, column=0, sticky="w")
        self.lab(ttk.Label(card, style="CardMuted.TLabel"), "arrives_in").grid(
            row=1, column=1, sticky="w", padx=(PAD_L, 0), pady=(PAD_S, 0))
        eta_row = ttk.Frame(card, style="CardInner.TFrame")      # "17 s  about 9:41 AM" on one line (saves a row)
        eta_row.grid(row=2, column=1, sticky="w", padx=(PAD_L, 0))
        ttk.Label(eta_row, textvariable=self.v_eta, style="CardTitle.TLabel").pack(side="left")
        ttk.Label(eta_row, textvariable=self.v_etaclock, style="CardMuted.TLabel").pack(side="left", padx=(PAD, 0), anchor="s", pady=(0, 3))

        # ----- battery: percentage text above a colored bar -----
        self.batt_label = ttk.Label(card, textvariable=self.v_batt, style="CardMuted.TLabel")
        self.batt_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=(PAD, 0))
        self.batt_bar = ttk.Progressbar(card, maximum=100, style="Ok.Horizontal.TProgressbar")
        self.batt_bar.grid(row=4, column=0, columnspan=2, sticky="we", pady=(PAD_S, 0))
        self.batt_widgets = (self.batt_label, self.batt_bar)     # shown to operators only (see apply_role)

        # ----- alert line (hidden whenever there is nothing to report) -----
        self.lbl_alert = ttk.Label(card, textvariable=self.v_alert, style="Alert.TLabel", wraplength=WRAP)
        self.lbl_alert.grid(row=5, column=0, columnspan=2, sticky="w", pady=(PAD, 0))
        self.lbl_alert.grid_remove()

        # ----- Para button (the jeep's reply appears in the message bar) -----
        self.btn_para = self.lab(ttk.Button(card, style="Primary.TButton", command=self.do_para), "para")
        self.btn_para.grid(row=6, column=0, columnspan=2, sticky="we", pady=(PAD, 0))
        self.lbl_para_hint = ttk.Label(card, wraplength=WRAP, style="CardMuted.TLabel")      # why Para is off (shown only then)
        self.lbl_para_hint.grid(row=7, column=0, columnspan=2, sticky="w", pady=(PAD_S, 0))
        self.lbl_para_hint.grid_remove()

    def build_trip(self, nb):
        """Plan trip tab: choose stations and passenger type, see fare and times, request a ride."""
        f = ttk.Frame(nb, padding=PAD)
        # ----- trip choices -----
        self.from_var = tk.StringVar(value=self.names[0])
        self.to_var = tk.StringVar(value=self.names[2])
        self.cat_var = tk.StringVar(value="Regular")
        self.lab(ttk.Label(f), "ride_on").grid(row=0, column=0, sticky="w")
        self.cb_from = ttk.Combobox(f, values=self.names, textvariable=self.from_var, state="readonly", width=16)
        self.cb_from.grid(row=0, column=1, sticky="w", pady=PAD_S)
        self.lab(ttk.Label(f), "get_off").grid(row=1, column=0, sticky="w")
        self.cb_to = ttk.Combobox(f, values=self.names, textvariable=self.to_var, state="readonly", width=16)
        self.cb_to.grid(row=1, column=1, sticky="w", pady=PAD_S)
        # Swap is created after both boxes, so Tab visits: Ride on at, Get off at, Swap, Passenger.
        # It has its own column, level with the two boxes it swaps.
        self.lab(ttk.Button(f, width=10, command=self.swap_stations), "swap").grid(row=0, column=2, rowspan=2, sticky="w", padx=(PAD_L, 0))
        self.lab(ttk.Label(f), "passenger").grid(row=2, column=0, sticky="w")
        ttk.Combobox(f, values=list(DISCOUNTS), textvariable=self.cat_var, state="readonly", width=16).grid(row=2, column=1, sticky="w", pady=PAD_S)
        # ----- fare and trip summary -----
        self.v_route, self.v_fare, self.v_wait = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.v_ride, self.v_total, self.v_arrive = tk.StringVar(), tk.StringVar(), tk.StringVar()
        ttk.Label(f, textvariable=self.v_route, wraplength=WRAP).grid(row=3, column=0, columnspan=3, sticky="w", pady=(PAD, 0))
        sm = ttk.Frame(f)                                  # fare on top, then the four times in two columns (keeps the tab short)
        sm.grid(row=4, column=0, columnspan=3, sticky="we", pady=(PAD_S, 0))
        self.lab(ttk.Label(sm), "fare").grid(row=0, column=0, sticky="w")
        ttk.Label(sm, textvariable=self.v_fare, font=F_TITLE).grid(row=0, column=1, sticky="w", padx=(PAD, 0))
        pairs = (("jeep_reaches", self.v_wait), ("ride_time", self.v_ride),
                 ("total", self.v_total), ("arrive_at", self.v_arrive))
        for k, (t, v) in enumerate(pairs):
            r, c = 1 + k // 2, (k % 2) * 2
            self.lab(ttk.Label(sm), t).grid(row=r, column=c, sticky="w", padx=(0 if c == 0 else PAD_L, 0))
            ttk.Label(sm, textvariable=v, font=F_HEADING).grid(row=r, column=c + 1, sticky="w", padx=(PAD, 0))
        # ----- request button (its result appears in the message bar) -----
        self.btn_request = self.lab(ttk.Button(f, style="Primary.TButton", command=self.do_request), "request")
        self.btn_request.grid(row=5, column=0, columnspan=3, sticky="we", pady=(PAD, 0))
        # ----- reason the button is disabled (hidden while the button works) -----
        self.v_reqhint = tk.StringVar()
        self.lbl_reqhint = ttk.Label(f, textvariable=self.v_reqhint, wraplength=WRAP, style="Muted.TLabel")
        self.lbl_reqhint.grid(row=6, column=0, columnspan=3, sticky="w", pady=(PAD_S, 0))
        self.lbl_reqhint.grid_remove()
        return f

    def build_rides(self, nb):
        """My rides tab: a table of your requests and a Cancel button."""
        f = ttk.Frame(nb, padding=PAD)
        self.rtree = ttk.Treeview(f, columns=("id", "trip", "status", "eta"), show="headings", height=3, selectmode="browse")
        for c, t, w in (("id", "ID", 44), ("trip", "col_trip", 110), ("status", "col_status", 170), ("eta", "col_eta", 80)):
            if c == "id":
                self.rtree.heading(c, text=t)                  # "ID" is the same in both languages
            else:
                self.lab_column(self.rtree, c, t)
            self.rtree.column(c, width=w, anchor="w")
        self.rtree.pack(fill="both", expand=True)       # three rows at least; it grows when the window is taller
        self.rtree.bind("<<TreeviewSelect>>", lambda e: self.refresh_controls(time.time()))   # update Cancel at once
        cancel_box = ttk.Frame(f)                        # the Cancel button with the reason it is off right under it
        cancel_box.pack(anchor="w", pady=(PAD, PAD_S))
        self.btn_cancel = self.lab(ttk.Button(cancel_box, command=self.do_cancel), "cancel_ride")
        self.btn_cancel.grid(row=0, column=0, sticky="w")
        self.lbl_cancel_hint = ttk.Label(cancel_box, wraplength=WRAP, style="Hint.TLabel")
        self.lbl_cancel_hint.grid(row=1, column=0, sticky="w", pady=(PAD_S, 0))
        self.lbl_cancel_hint.grid_remove()
        for key in ("<Delete>", "<BackSpace>"):          # Delete (Backspace on a Mac keyboard) cancels the selected ride
            self.rtree.bind(key, lambda e: self.cancel_from_keyboard())
        self.rides_hint = "No rides yet. Use Plan trip > Request ride."
        self.lbl_rempty = ttk.Label(f, text=self.rides_hint, wraplength=WRAP, style="Muted.TLabel")
        self.lbl_rempty.pack(anchor="w")                  # empty-table hint: blank once there are rides
        ttk.Label(f, text="Select a ride and press Cancel. A ride can be cancelled until the jeep has picked you up. "
                          "ETA is the pickup, then the drop-off.",
                  wraplength=WRAP, style="Muted.TLabel").pack(anchor="w", pady=(PAD, 0))
        return f

    def build_schedule(self, nb):
        """Schedule tab: operating hours, service status and when the jeep passes each station."""
        f = ttk.Frame(nb, padding=(PAD, PAD_S))
        self.lab(ttk.Label(f, font=F_HEADING), "hours", open=fmt12(OPEN_TIME), close=fmt12(CLOSE_TIME)).pack(anchor="w")
        ttk.Label(f, text=SERVICE_DAYS).pack(anchor="w")
        self.v_service = tk.StringVar()
        self.lbl_service = ttk.Label(f, textvariable=self.v_service, font=F_HEADING)
        self.lbl_service.pack(anchor="w", pady=(2, 2))
        self.v_svc = tk.StringVar()
        ttk.Label(f, textvariable=self.v_svc, wraplength=WRAP).pack(anchor="w", pady=(0, PAD_S))
        self.tree = ttk.Treeview(f, columns=("stn", "next", "after"), show="headings", height=4,
                                 style="Compact.Treeview", takefocus=0)            # read-only: nothing to do in it, so Tab skips it
        for c, t, w in (("stn", "col_station", 130), ("next", "col_passes", 120), ("after", "col_following", 120)):
            self.lab_column(self.tree, c, t)
            self.tree.column(c, width=w, anchor="w")
        for i, n in enumerate(self.names):
            self.tree.insert("", "end", iid=str(i), values=(n, "-", "-"))
        self.tree.pack(fill="x")
        self.v_lap = tk.StringVar()
        ttk.Label(f, textvariable=self.v_lap, style="Muted.TLabel", wraplength=WRAP).pack(anchor="w", pady=(PAD_S, 0))
        return f

    def build_operator(self, nb):
        """Operator tab: vehicle controls, service settings and a live readout from the jeep."""
        f = ttk.Frame(nb, padding=PAD)

        # ----- dispatch buttons -----
        bar = ttk.Frame(f)
        bar.pack(fill="x")
        # each button sits in its own column with the reason it is off right under it (shown only then)
        specs = (("btn_dispatch", "lbl_dispatch_hint", "Dispatch", "Primary.TButton", self.do_dispatch),
                 ("btn_return", "lbl_return_hint", "Return to depot", "TButton", lambda: self.op("return")),
                 ("btn_reset", "lbl_reset_hint", "Reset fault", "TButton", lambda: self.op("reset")))
        for col, (btn_name, hint_name, text, style, command) in enumerate(specs):
            pad = (0 if col == 0 else PAD, 0)
            button = ttk.Button(bar, text=text, style=style, command=command)
            button.grid(row=0, column=col, sticky="we", padx=pad)
            hint = ttk.Label(bar, wraplength=130, style="Hint.TLabel", justify="left")
            hint.grid(row=1, column=col, sticky="nw", padx=pad, pady=(PAD_S, 0))
            hint.grid_remove()
            setattr(self, btn_name, button)
            setattr(self, hint_name, hint)

        # ----- emergency stop: it lives in the header bar (visible from every tab and never disabled), so only a reminder here -----
        ttk.Label(f, text="EMERGENCY STOP is in the bar at the top of the window.", style="Muted.TLabel",
                  wraplength=WRAP).pack(anchor="w", pady=(PAD, PAD_S))

        # ----- service mode -----
        mc = Card(f, "Service mode")
        mc.pack(fill="x")
        mf = mc.body
        self.svc_var = tk.StringVar(value="ondemand")
        modes = ttk.Frame(mf, style="CardInner.TFrame")
        modes.pack(fill="x")
        self.rad_ondemand = ttk.Radiobutton(modes, text="On-demand", variable=self.svc_var, value="ondemand",
                                            command=self.set_mode, style="Card.TRadiobutton")
        self.rad_ondemand.pack(side="left")
        ttk.Radiobutton(modes, text="Patrol (every stop)", variable=self.svc_var, value="patrol",
                        command=self.set_mode, style="Card.TRadiobutton").pack(side="left", padx=PAD_L)
        # ----- dwell time (a service setting, so it sits in the same card) -----
        df = ttk.Frame(mf, style="CardInner.TFrame")
        df.pack(fill="x", pady=(PAD, 0))
        ttk.Label(df, text="Dwell time (s)", style="Card.TLabel").pack(side="left")
        self.dwell_var = tk.StringVar(value=str(int(DWELL_S)))
        spin = ttk.Spinbox(df, from_=1, to=30, width=5, textvariable=self.dwell_var)
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
        self.ov = {k: tk.StringVar(value="-") for k in ("state", "mode", "batt", "sensors", "rides", "pick", "drop")}
        for r, (k, t) in enumerate((("state", "State"), ("mode", "Service mode"), ("batt", "Battery"), ("sensors", "Sensors"),
                                    ("rides", "Active rides (app)"), ("pick", "Waiting at"), ("drop", "Getting off at"))):
            ttk.Label(rf, text=t, style="CardMuted.TLabel").grid(row=r, column=0, sticky="nw", pady=2)
            ttk.Label(rf, textvariable=self.ov[k], style="Card.TLabel", wraplength=WRAP - 180).grid(
                row=r, column=1, sticky="w", padx=PAD, pady=2)
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
        self.logtree.column("time", width=88, anchor="w", stretch=False)
        self.logtree.column("level", width=76, anchor="w", stretch=False)
        self.logtree.column("event", width=240, anchor="w")
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
