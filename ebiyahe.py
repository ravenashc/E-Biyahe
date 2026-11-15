#continue 3,4,5
#make jeepney look better
#add scroll
#add pretty bg
#better fonts
#better spacings/layouts
#make prettier
#clean up code
#packs
#separate operator and passenger (hide operator)

#!/usr/bin/env python3
"""
E-BIYAHE - Tkinter dispatch and monitoring app for the automated guided e-jeepney diorama.

Run:   python ebiyahe_app.py        (Python 3.8+, Tkinter only, nothing to pip install)

HOW THE SERVICE WORKS (on-demand)
  The jeep drives a one-way loop, counterclockwise (BR > TR > TL > BL), and parks in the depot when idle.
  At every station tag it reads, the jeep stops ONLY if
      1. someone is waiting there (a booked pickup), or
      2. someone on board booked a drop-off there (armed only AFTER that rider boarded), or
      3. Para was pressed, or
      4. the service mode is Patrol (stop at every station) and the battery is fine.
  Otherwise it logs a pass and keeps going. The jeep makes these decisions itself, so it keeps
  working if Wi-Fi drops. The app only sends requests and shows what the jeep reports.

MODES
  Demo  - a built-in simulated jeep that follows the same rules (class JeepSim). The Demo menu
          triggers an obstacle, a lost line, low battery and a Wi-Fi drop.
  Wi-Fi - connects to the jeep over TCP (default 192.168.4.1:8080, the ESP32 access point).

MESSAGES (one JSON object per line)
  App -> jeep
    {"cmd":"request","id":7,"from":0,"to":2}   book a ride (station numbers are 0..3)
    {"cmd":"cancel","id":7}                    cancel a ride that has not boarded yet
    {"cmd":"para"}  {"cmd":"estop"}  {"cmd":"reset"}  {"cmd":"dispatch"}  {"cmd":"return"}
    {"cmd":"mode","value":"ondemand"|"patrol"}      {"cmd":"dwell","value":4}
    {"cmd":"sync","ids":[7,8]}                 sent on every (re)connect: the jeep drops other bookings
  Jeep -> app: STATUS every 1 s and on every change
    {"state":"RUNNING","next":1,"depot":false,"batt":7.9,"dist":42,"head":0,"patrol":false,
     "para":false,"lowbatt":false,"paused":false,"crit":false,"dwell":4,"load":false,"unload":false,
     "ir":"010","pick":[0,1,0,0],"drop":[0,0,0,1],"wait":[7],"ride":[]}
    state = PARKED | RUNNING | LOADING_UNLOADING | OBSTACLE_HOLD | LINE_LOST | EMERGENCY_STOP | LOW_BATTERY
    next  = index of the next station tag the jeep will read; the last station is (next - 1) mod 4.
            While parked, next is 0 (the jeep leaves the depot toward BR).
    pick/drop = people waiting / on board per station;  wait/ride = booking ids waiting / on board
    paused = new requests refused (low battery, or returning to the depot)
    LOW_BATTERY is also used for "returning to depot" ordered by the operator.
  Jeep -> app: EVENT (for the log and alerts)
    {"type":"event","ev":"ARRIVED","stop":2,"load":true,"unload":false,"boarded":[7],"done":[]}
    ev = ARRIVED DEPARTED TAG_PASS PARA OBSTACLE OBSTACLE_CLEAR FAULT ESTOP RESET DISPATCHED PARKED
         LOW_BATT RETURNING BATT_OK MODE REJECTED CANCELLED
  Booking states in the app come from the STATUS lists wait/ride, so a missed event or a short
  Wi-Fi drop cannot leave a ride stuck.

Firmware note: latch every tag read until the state machine has handled it. If an obstacle or
fault wins priority on the same loop pass as a tag read, the tag must not be lost.

Edit the CONFIG block to match your diorama, fares and hours.
"""

# ----------------------------------------------------------------------------------
# FILE MAP - the sections of this file, in the order they appear
#   IMPORTS                     tools borrowed from Python
#   CONFIG                      settings you can change (fares, hours, battery levels)
#   THEME                       colors, fonts and spacing shared by every screen
#   MAP LAYOUT AND JEEP STATES  station positions, roads and the jeep's seven states
#   HELPERS                     small functions (distance, time text, fare, battery percent)
#   BOOKINGS                    one ride request
#   JEEP STATE AND ETA MODEL    the app's notebook of what the jeep reports, plus ETA guesses
#   SIMULATED JEEP              the pretend jeep used by Demo mode
#   DATA SOURCES                the two messengers (Demo and Wi-Fi) that bring messages in
#   WIDGETS                     small reusable screen parts (the status badge)
#   APP                         the window: layout, buttons, events, refreshing, map drawing
# ----------------------------------------------------------------------------------

# ======================= IMPORTS =======================
import csv
import json
import math
import os
import queue
import random
import socket
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkfont      # named fonts used by the THEME section
from datetime import datetime

# ======================= CONFIG =======================
APP_NAME = "E-Biyahe"
VEHICLE = "E-Jeepney"
APP_TITLE = f"{APP_NAME}: Dispatch and Monitoring"
DEFAULT_HOST, DEFAULT_PORT = "192.168.4.1", 8080
CURRENCY = "\u20b1"            # peso sign
BASE_FARE = 10.0               # boarding fare
PER_STOP_FARE = 5.0            # added for every station-to-station leg ridden
DISCOUNTS = {"Regular": 0.0, "Student": 0.20, "Senior": 0.20, "PWD": 0.20}
MAX_ACTIVE = 8                 # request limit: the jeep keeps its bookings in a small fixed list
DWELL_S = 4.0                  # time the jeep waits at a station (the operator can change it)
SPEED_UNITS_PER_S = 30.0       # first guess of jeep speed on the map, replaced by learned times
LEARN_ALPHA = 0.5              # how fast learned leg times follow real arrivals (0..1)
STALE_S = 4.0                  # no data for this long = jeep shown as offline
REQUEST_GRACE_S = 3.0          # a new request may take this long to show up in the jeep's lists
DISPATCH_S = 1.0               # time a parked jeep needs to wake up
BATT_FULL, BATT_LOW, BATT_CRIT, BATT_RECHARGED = 8.4, 6.6, 6.0, 7.2     # 2S Li-ion volts
BATT_DRAIN_V_PER_S = 0.002     # demo bus only
CHARGE_V_PER_S = 0.05          # demo bus only (fast, so the demo does not take long)
OPEN_TIME, CLOSE_TIME = "06:00", "21:00"
SERVICE_DAYS = "Monday to Sunday"
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "log.csv")

# ======================= THEME (colors, fonts, spacing) =======================
# Every color, font and spacing value used on screen lives in this section. To restyle the app,
# change a value here; no other part of the file has a color or font size typed into it.
# Design rules: one brand color (teal), three colors that always mean the same thing
# (green = fine, amber = caution, red = danger), and neutral grays for everything else.

# ----- colors -----
PALETTE = {
    # surfaces
    "bg": "#f3f5f4",             # window background
    "card": "#ffffff",           # raised panels: status card, tables, input boxes
    "border": "#d5dbd8",         # thin outlines and dividers
    "header": "#e3e9e6",         # table headings, unselected tabs, secondary buttons
    # text
    "text": "#1f2937",           # main text
    "muted": "#4b5563",          # hints, labels and secondary text
    "disabled": "#9ca3af",       # unavailable controls and the offline dot
    "on_color": "#ffffff",       # text drawn on top of a colored fill
    # brand
    "accent": "#0d5c63",         # teal: primary buttons, selected tab, next stop
    "accent_dark": "#0a4a50",    # teal while the mouse is over a button
    # meaning (same meaning on every screen)
    "ok": "#15803d",             # driving, in service, battery fine
    "warn": "#b45309",           # at a station, obstacle, low battery, offline notice
    "danger": "#b91c1c",         # emergency stop, fault, out of service
    "danger_dark": "#991b1b",    # red while the mouse is over a button
    # map drawing
    "map_bg": "#eef1ee",
    "map_block": "#d3e6cc",
    "map_block_edge": "#a9c2a2",
    "map_road": "#222222",
    "map_depot_fill": "#e5e7eb",
    "map_depot_edge": "#9ca3af",
    "map_route": "#9ec5fe",      # highlight for the trip being planned
    "map_next": "#f59e0b",       # dashed ring on the next station
    "map_pickup": "#ea580c",     # ring: someone is waiting to board
    "map_drop": "#2563eb",       # ring: a rider is getting off
}

# ----- fonts (one family, five sizes) -----
FONT_CHOICES = ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", "DejaVu Sans")
FONT_FAMILY = "TkDefaultFont"    # replaced by the first installed choice in apply_theme()
FONT_OBJECTS = []                # keeps the font objects from apply_theme() alive
F_DISPLAY, F_TITLE, F_HEADING = "eb_display", "eb_title", "eb_heading"
F_BODY, F_SMALL, F_SMALL_BOLD = "eb_body", "eb_small", "eb_small_bold"
FONT_SCALE = (                   # (font name, size in points, weight)
    (F_DISPLAY, 20, "bold"),     # the single most important fact on screen (next stop)
    (F_TITLE, 14, "bold"),       # key numbers: ETA, fare, live state
    (F_HEADING, 11, "bold"),     # labels that need weight, button text, group titles
    (F_BODY, 10, "normal"),      # normal text
    (F_SMALL, 9, "normal"),      # hints and secondary detail
    (F_SMALL_BOLD, 9, "bold"),   # small labels on the map
)

# ----- spacing (one scale, so gaps look the same everywhere) -----
PAD_S, PAD, PAD_L = 4, 8, 12     # small, normal and large gaps in pixels
WRAP = 330                       # width in pixels at which long text wraps


def apply_theme(root):
    """Create the named fonts and style every ttk widget. Call once, right after the window exists."""
    global FONT_FAMILY
    P = PALETTE

    # ----- fonts: pick the first installed family, then create the named sizes -----
    installed = set(tkfont.families(root))
    system_family = tkfont.nametofont("TkDefaultFont").actual("family")
    FONT_FAMILY = next((f for f in FONT_CHOICES if f in installed), system_family)
    for name, size, weight in FONT_SCALE:
        # keep a reference: Tk deletes a named font as soon as its Python object is garbage collected
        FONT_OBJECTS.append(tkfont.Font(root=root, name=name, family=FONT_FAMILY, size=size, weight=weight))
    for default in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(default).configure(family=FONT_FAMILY, size=10)

    # ----- window and base style -----
    root.configure(bg=P["bg"])
    s = ttk.Style(root)
    s.theme_use("clam")          # draws the same on Windows, macOS and Linux
    s.configure(".", font=F_BODY, background=P["bg"], foreground=P["text"], bordercolor=P["border"])

    # ----- containers: titled boxes and the white status card -----
    s.configure("TLabelframe", background=P["bg"], bordercolor=P["border"])
    s.configure("TLabelframe.Label", background=P["bg"], foreground=P["text"], font=F_HEADING)
    s.configure("Card.TFrame", background=P["card"], relief="solid", borderwidth=1)
    s.configure("CardInner.TFrame", background=P["card"])

    # ----- labels: Muted.* on the window background, Card* on the white card -----
    s.configure("Muted.TLabel", foreground=P["muted"])
    for name, font, color in (("Card", F_BODY, "text"), ("CardMuted", F_SMALL, "muted"),
                              ("CardHeading", F_HEADING, "text"), ("CardTitle", F_TITLE, "text"),
                              ("CardDisplay", F_DISPLAY, "accent"), ("Alert", F_HEADING, "danger")):
        s.configure(f"{name}.TLabel", background=P["card"], foreground=P[color], font=font)

    # ----- buttons: plain (secondary), Primary (teal) and Danger (red) -----
    s.configure("TButton", padding=(PAD_L, PAD_S + 2), background=P["header"], foreground=P["text"],
                bordercolor=P["border"], focuscolor=P["accent"])
    s.map("TButton", background=[("active", P["border"]), ("disabled", P["bg"])],
          foreground=[("disabled", P["disabled"])])
    for name, base, hover in (("Primary", "accent", "accent_dark"), ("Danger", "danger", "danger_dark")):
        s.configure(f"{name}.TButton", background=P[base], foreground=P["on_color"],
                    bordercolor=P[base], font=F_HEADING)
        s.map(f"{name}.TButton", background=[("active", P[hover]), ("disabled", P["disabled"])],
              foreground=[("disabled", P["on_color"])])
    s.configure("Danger.TButton", padding=(PAD_L, PAD))     # the emergency button is taller

    # ----- tabs -----
    s.configure("TNotebook", background=P["bg"], bordercolor=P["border"])
    s.configure("TNotebook.Tab", padding=(PAD_L, PAD_S), background=P["header"], foreground=P["muted"])
    s.map("TNotebook.Tab", background=[("selected", P["bg"])], foreground=[("selected", P["accent"])])

    # ----- tables -----
    s.configure("Treeview", background=P["card"], fieldbackground=P["card"], foreground=P["text"],
                rowheight=21, bordercolor=P["border"])        # compact rows: tables stay short
    s.map("Treeview", background=[("selected", P["accent"])], foreground=[("selected", P["on_color"])])
    s.configure("Treeview.Heading", background=P["header"], foreground=P["text"], font=F_HEADING,
                relief="flat", padding=(PAD, 2))

    # ----- input boxes, radio buttons and dividers -----
    for widget in ("TEntry", "TCombobox", "TSpinbox"):
        s.configure(widget, fieldbackground=P["card"], foreground=P["text"], bordercolor=P["border"],
                    padding=2)               # tight, so forms stay short
    s.map("TCombobox", fieldbackground=[("readonly", P["card"])])
    s.configure("TRadiobutton", background=P["bg"])
    s.map("TRadiobutton", background=[("active", P["bg"])])
    s.configure("TSeparator", background=P["border"])

    # ----- battery bar in three colors (see App.set_battery) -----
    for name, color in (("Ok", "ok"), ("Warn", "warn"), ("Danger", "danger")):
        s.configure(f"{name}.Horizontal.TProgressbar", troughcolor=P["border"], background=P[color],
                    bordercolor=P["border"], lightcolor=P[color], darkcolor=P[color], thickness=10)


# ======================= MAP LAYOUT AND JEEP STATES =======================

# Stations in the order the jeep visits them, with their position on the 600 x 650 map.
STOPS = [
    ("BR Station", (550, 395)),
    ("TR Station", (425, 50)),
    ("TL Station", (175, 50)),
    ("BL Station", (50, 395)),
]
N = len(STOPS)
LEG_PATHS = [                  # leg i = from station i to station i+1 (map points)
    [(550, 395), (550, 50), (425, 50)],
    [(425, 50), (175, 50)],
    [(175, 50), (50, 50), (50, 395)],
    [(50, 395), (50, 510), (550, 510), (550, 395)],
]
BLOCKS = [(75, 75, 275, 255), (325, 75, 525, 255), (75, 305, 275, 485), (325, 305, 525, 485)]
LABEL_POS = [(-14, 0, "e"), (0, -16, "s"), (0, -16, "s"), (14, 0, "w")]   # label placement per station

# The depot hangs off leg 3 (BL > BR). Leaving it, the jeep joins the loop toward BR.
DEPOT_POS = (200, 615)
EXIT_PATH = [DEPOT_POS, (200, 510), (550, 510), (550, 395)]
EXIT_STOP = 0                  # the first station tag after leaving the depot (BR)
DEPOT_LEG = 3                  # the leg where the depot-entry tag sits

STATES = ("PARKED", "RUNNING", "LOADING_UNLOADING", "OBSTACLE_HOLD", "LINE_LOST", "EMERGENCY_STOP", "LOW_BATTERY")
MOVING = ("RUNNING", "LOW_BATTERY")
STATE_TEXT = {"PARKED": "Parked at depot", "RUNNING": "Driving", "LOADING_UNLOADING": "At station",
              "OBSTACLE_HOLD": "Stopped: obstacle ahead", "LINE_LOST": "FAULT: line lost",
              "EMERGENCY_STOP": "EMERGENCY STOP", "LOW_BATTERY": "Returning to depot"}
STATE_COLOR = {"RUNNING": PALETTE["ok"], "LOW_BATTERY": PALETTE["warn"],
               "LOADING_UNLOADING": PALETTE["warn"], "OBSTACLE_HOLD": PALETTE["danger"],
               "LINE_LOST": PALETTE["danger"], "EMERGENCY_STOP": PALETTE["danger"]}


# ======================= HELPERS =======================
def path_len(pts):
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def point_at(pts, frac):
    d = max(0.0, min(1.0, frac)) * path_len(pts)
    for i in range(len(pts) - 1):
        seg = math.dist(pts[i], pts[i + 1])
        if d <= seg or i == len(pts) - 2:
            t = d / seg if seg else 0.0
            return (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t)
        d -= seg
    return pts[-1]


def fmt_dur(s):
    if s is None:
        return "-"
    s = int(round(s))
    if s < 60:
        return f"{s} s"
    m, s = divmod(s, 60)
    return f"{m} min {s:02d} s"


def fmt_clock(ts):
    return datetime.fromtimestamp(ts).strftime("%I:%M:%S %p").lstrip("0")


def fmt12(hhmm):
    return datetime.strptime(hhmm, "%H:%M").strftime("%I:%M %p").lstrip("0")


def fare_for(legs, category="Regular"):
    return round((BASE_FARE + PER_STOP_FARE * legs) * (1.0 - DISCOUNTS.get(category, 0.0)), 2)


def stop_label(load, unload):
    """LOADING if only a pickup is flagged, UNLOADING if only a drop-off or Para, otherwise both."""
    show_load = load or not unload
    show_unload = unload or not load
    if show_load and show_unload:
        return "LOADING / UNLOADING"
    return "LOADING" if show_load else "UNLOADING"


def batt_pct(v):
    return max(0.0, min(100.0, (v - BATT_LOW) / (BATT_FULL - BATT_LOW) * 100.0))


def int_list(v):
    return [x for x in v if isinstance(x, int) and not isinstance(x, bool)] if isinstance(v, list) else []


def to_float(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def rrect(x1, y1, x2, y2, r):
    return [x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y1 + r, x2, y2 - r, x2, y2 - r,
            x2, y2, x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r,
            x1, y1 + r, x1, y1]


# fraction of leg 3 at which the depot-entry tag sits (where the spur leaves the road)
DEPOT_FRAC = path_len([(50, 395), (50, 510), (200, 510)]) / path_len(LEG_PATHS[DEPOT_LEG])
EXIT = -1                       # "leg number" of the depot -> BL exit path


# ======================= BOOKINGS =======================
class Booking:
    """One ride request. WAITING -> BOARDED -> COMPLETED, or CANCELLED / REJECTED."""

    def __init__(self, bid, pickup, drop, category, fare, now):
        self.id, self.pickup, self.drop = bid, pickup, drop
        self.category, self.fare = category, fare
        self.status = "WAITING"
        self.sent = now
        self.note = ""

    @property
    def active(self):
        return self.status in ("WAITING", "BOARDED")

    @property
    def cancellable(self):
        return self.status == "WAITING"


# ======================= JEEP STATE AND ETA MODEL =======================
class Tracker:
    """Follows the jeep from its STATUS messages and estimates times."""

    def __init__(self):
        self.connected = False
        self.leg_est = [path_len(p) / SPEED_UNITS_PER_S for p in LEG_PATHS]
        self.exit_est = path_len(EXIT_PATH) / SPEED_UNITS_PER_S
        self.clear()

    def clear(self):
        """Forget everything about the jeep (on every new connection)."""
        self.synced = False
        self.last_msg = 0.0
        self.state = "PARKED"
        self.next_stop = EXIT_STOP
        self.depot = True
        self.from_depot = False        # True while driving the depot -> BL exit path
        self.leg_start = None          # when the jeep started its current leg
        self.arrive_time = None        # when it arrived at its last station
        self.frac = 0.0                # estimated progress along the current leg (0..1)
        self.leg_clean = True          # False if the jeep was stopped mid-leg (do not learn from it)
        self.dist = None
        self.lights = False
        self.batt = None
        self.crit = False
        self.lowbatt = False
        self.paused = False
        self.patrol = False
        self.para = False
        self.dwell = DWELL_S
        self.load = self.unload = False
        self.ir = ""
        self.pick = [0] * N
        self.drop = [0] * N
        self.wait_ids, self.ride_ids = [], []

    @property
    def last_stop(self):
        return (self.next_stop - 1) % N

    def cur_est(self):
        return max(self.exit_est if self.from_depot else self.leg_est[self.last_stop], 1.0)

    def cur_path(self):
        return EXIT_PATH if self.from_depot else LEG_PATHS[self.last_stop]

    def learn(self, observed, was_depot_leg, old_next):
        if not (2.0 < observed < 600.0):
            return
        if was_depot_leg:
            self.exit_est = (1 - LEARN_ALPHA) * self.exit_est + LEARN_ALPHA * observed
        else:
            i = (old_next - 1) % N
            self.leg_est[i] = (1 - LEARN_ALPHA) * self.leg_est[i] + LEARN_ALPHA * observed

    def update(self, msg, now):
        """Apply one STATUS message. Returns True if it was a valid status."""
        state = str(msg.get("state", "")).upper()
        if state not in STATES:
            return False
        self.last_msg = now
        prev, old_next, was_depot_leg, first = self.state, self.next_stop, self.from_depot, not self.synced
        self.synced = True
        self.state = state
        nxt = msg.get("next")
        if isinstance(nxt, int) and 0 <= nxt < N:
            self.next_stop = nxt
        self.depot = bool(msg.get("depot", state == "PARKED"))
        self.dist = msg.get("dist", self.dist)
        self.lights = bool(msg.get("head", self.lights))
        self.batt = msg.get("batt", self.batt) if isinstance(msg.get("batt", self.batt), (int, float)) else None
        self.crit = bool(msg.get("crit", False))
        self.lowbatt = bool(msg.get("lowbatt", False))
        self.paused = bool(msg.get("paused", self.lowbatt))
        self.patrol = bool(msg.get("patrol", False))
        self.para = bool(msg.get("para", False))
        self.dwell = max(1.0, to_float(msg.get("dwell"), self.dwell))
        self.load, self.unload = bool(msg.get("load", False)), bool(msg.get("unload", False))
        self.ir = str(msg.get("ir", ""))
        self.pick = (int_list(msg.get("pick")) + [0] * N)[:N]
        self.drop = (int_list(msg.get("drop")) + [0] * N)[:N]
        self.wait_ids, self.ride_ids = int_list(msg.get("wait")), int_list(msg.get("ride"))

        if not first and self.next_stop != old_next:                 # a station tag was read
            if self.leg_start is not None and self.leg_clean:
                self.learn(now - self.leg_start, was_depot_leg, old_next)
            self.from_depot = False
            self.leg_start, self.frac, self.leg_clean = None, 0.0, True
            if state in MOVING:                                      # passed it without stopping
                self.leg_start = now

        if state == "LOADING_UNLOADING":
            if prev != state:
                self.arrive_time = now
            self.leg_start, self.frac = None, 0.0
        elif state in MOVING:
            if prev == "LOADING_UNLOADING":                          # just left the station
                self.leg_start, self.frac, self.leg_clean = now, 0.0, True
            elif prev == "PARKED":                                   # just left the depot
                self.from_depot, self.leg_start, self.frac, self.leg_clean = True, now, 0.0, True
            elif prev in ("OBSTACLE_HOLD", "LINE_LOST", "EMERGENCY_STOP"):   # resumed: keep progress
                self.leg_start = now - self.frac * self.cur_est()
            elif self.leg_start is None:                             # joined mid-leg: assume it just left
                self.leg_start, self.leg_clean = now, False
        elif state == "PARKED":
            self.leg_start, self.frac, self.from_depot, self.leg_clean = None, 0.0, False, True
        else:                                                        # held mid-leg (obstacle, fault, e-stop)
            self.leg_clean = False
        return True

    def update_frac(self, now):
        if self.state in MOVING and self.leg_start is not None:
            self.frac = min((now - self.leg_start) / self.cur_est(), 0.97)

    def position(self):
        """Where to draw the jeep on the 600 x 650 map (an estimate between stations)."""
        if self.depot:
            return DEPOT_POS
        if self.leg_start is not None:
            return point_at(self.cur_path(), self.frac)
        return STOPS[self.last_stop][1]

    def stops_at(self, i):
        return self.patrol or self.pick[i] > 0 or self.drop[i] > 0

    def eta_to_next(self, now, dispatch=False):
        """Seconds until the next station tag. dispatch=True: if parked, as if it left right now."""
        if self.state == "LOADING_UNLOADING":
            left = max(0.0, self.dwell - (now - (self.arrive_time or now)))
            return left + self.leg_est[self.last_stop]
        if self.state in MOVING and self.leg_start is not None:
            return max(0.0, self.cur_est() - (now - self.leg_start))
        if self.state == "PARKED" and dispatch:
            return DISPATCH_S + self.exit_est
        return None

    def eta_to_stop(self, idx, now, dispatch=False, lap_if_here=False):
        """Seconds until the jeep reaches station idx (0 = it is there now)."""
        if self.state == "LOADING_UNLOADING" and self.last_stop == idx:
            return self.lap_time() if lap_if_here else 0.0
        t = self.eta_to_next(now, dispatch)
        if t is None:
            return None
        cur = self.next_stop
        for _ in range(N):
            if cur == idx:
                break
            t += (self.dwell if self.stops_at(cur) else 0.0) + self.leg_est[cur]
            cur = (cur + 1) % N
        return t

    def lap_time(self):
        return sum(self.leg_est) + (N * self.dwell if self.patrol else 0.0)


# ======================= SIMULATED JEEP (same rules as the firmware) =======================
class JeepSim:
    """The jeep's brain for Demo mode. Follows the state table: step(dt) advances time,
    command(dict) handles app messages, status() builds the STATUS message, and everything the
    jeep reports as an event is collected in self.out."""

    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.t = 0.0
        self.state = "PARKED"
        self.depot = True
        self.leg, self.prog = EXIT, 0.0
        self.leg_time = self.roll_leg_time()
        self.depot_tag_done = False
        self.stop_here = None
        self.dwell_left = 0.0
        self.E = self.F = self.B = self.ret = False      # e-stop, line lost, low battery, return ordered
        self.G = self.R = False                          # go and reset pulses
        self.patrol = False
        self.para = False
        self.dwell = DWELL_S
        self.batt = BATT_FULL
        self.crit = False
        self.low_since = None
        self.obstacle_until = 0.0
        self.load = self.unload = False
        self.book = []                                   # {"id", "from", "to", "on"}
        self.out = []
        self.dirty = True

    # ----- small helpers -----
    @property
    def next_stop(self):
        return EXIT_STOP if self.leg == EXIT else (self.leg + 1) % N

    @property
    def paused(self):
        return self.B or self.ret

    def work(self):
        return bool(self.book) or self.para

    def flags(self, k):
        p = any(b["from"] == k and not b["on"] for b in self.book)
        d = any(b["to"] == k and b["on"] for b in self.book)
        return p, d

    def event(self, ev, **kw):
        self.out.append({"type": "event", "ev": ev, **kw})

    def enter(self, s):
        if s != self.state:
            self.state = s
            self.dirty = True

    def roll_leg_time(self):
        path = EXIT_PATH if self.leg == EXIT else LEG_PATHS[self.leg]
        return path_len(path) / SPEED_UNITS_PER_S * self.rng.uniform(0.95, 1.1)

    def start_leg(self, k):
        self.leg, self.prog, self.depot_tag_done = k, 0.0, False
        self.leg_time = self.roll_leg_time()
        self.dirty = True

    def cancel_waiting(self, ev, **kw):
        ids = [b["id"] for b in self.book if not b["on"]]
        self.book = [b for b in self.book if b["on"]]
        self.event(ev, cancelled=ids, **kw)
        self.dirty = True

    # ----- commands from the app -----
    def command(self, c):
        cmd = c.get("cmd")
        if cmd == "request":
            bid, a, b = c.get("id"), c.get("from"), c.get("to")
            if not all(isinstance(v, int) for v in (bid, a, b)) or not (0 <= a < N and 0 <= b < N) or a == b:
                self.event("REJECTED", id=bid, reason="Invalid request")
            elif any(x["id"] == bid for x in self.book):
                pass                                                  # duplicate message
            elif self.paused:
                self.event("REJECTED", id=bid, reason="Service paused (low battery or returning to depot)")
            elif self.state in ("EMERGENCY_STOP", "LINE_LOST"):
                self.event("REJECTED", id=bid, reason="The jeep is stopped (emergency stop or fault)")
            elif len(self.book) >= MAX_ACTIVE:
                self.event("REJECTED", id=bid, reason=f"Too many active rides (limit {MAX_ACTIVE})")
            else:
                self.book.append({"id": bid, "from": a, "to": b, "on": False})
                if self.state == "PARKED":
                    self.G = True                                     # a request wakes the jeep
            self.dirty = True
        elif cmd == "cancel":
            bid = c.get("id")
            b = next((x for x in self.book if x["id"] == bid), None)
            if b is not None and b["on"]:
                self.event("CANCELLED", id=bid, ok=False)             # already on board
            else:
                if b is not None:
                    self.book.remove(b)
                self.event("CANCELLED", id=bid, ok=True)
            self.dirty = True
        elif cmd == "para":
            ok = not self.depot
            if ok:
                self.para = True
            self.event("PARA", ok=ok)
            self.dirty = True
        elif cmd == "estop":
            self.E = True
            self.event("ESTOP")
        elif cmd == "reset":
            self.E = self.F = False
            self.R = True
            self.event("RESET")
        elif cmd == "dispatch":
            self.G = True
        elif cmd == "return":
            if not self.depot and not self.ret:
                self.ret = True
                self.cancel_waiting("RETURNING")
        elif cmd == "mode":
            patrol = c.get("value") == "patrol"
            if patrol != self.patrol:
                self.patrol = patrol
                self.event("MODE", patrol=patrol)
                self.dirty = True
        elif cmd == "dwell":
            v = max(1.0, min(30.0, to_float(c.get("value"), self.dwell)))
            if v != self.dwell:
                self.dwell = v
                self.dirty = True
        elif cmd == "sync":
            ids = set(int_list(c.get("ids")))
            self.book = [b for b in self.book if b["id"] in ids]
            self.dirty = True
        elif cmd == "sim":
            what = c.get("what")
            if what == "obstacle":
                self.obstacle_until = self.t + 6.0
            elif what == "lineloss" and self.state in MOVING:
                self.F = True
            elif what == "lowbatt":
                self.batt = 6.5

    # ----- time step -----
    def step(self, dt):
        self.t += dt
        O = self.t < self.obstacle_until
        R, G = self.R, self.G
        self.R = self.G = False
        self.update_battery(dt)
        st = self.state
        if st == "PARKED":
            if self.E:
                self.enter("EMERGENCY_STOP")
            elif G and not self.B:
                self.depot = False
                self.event("DISPATCHED")
                self.enter("RUNNING")
        elif st in MOVING:
            self.drive(dt, O)
        elif st == "LOADING_UNLOADING":
            if self.E:
                self.enter("EMERGENCY_STOP")
            else:
                self.dwell_left -= dt
                if self.dwell_left <= 0:
                    self.event("DEPARTED", stop=self.stop_here)
                    self.load = self.unload = False
                    self.resume()
        elif st == "OBSTACLE_HOLD":
            if self.E:
                self.enter("EMERGENCY_STOP")
            elif not O:
                self.event("OBSTACLE_CLEAR")
                self.resume()
        elif st == "LINE_LOST":
            if self.E:
                self.enter("EMERGENCY_STOP")
            elif R:
                self.resume()
        elif st == "EMERGENCY_STOP":
            if R:
                self.enter("PARKED") if self.depot else self.resume()

    def resume(self):
        self.enter("LOW_BATTERY" if self.paused else "RUNNING")

    def update_battery(self, dt):
        if self.state in MOVING and not self.crit:
            self.batt = max(5.0, self.batt - BATT_DRAIN_V_PER_S * dt)
        elif self.depot and self.state == "PARKED":
            self.batt = min(BATT_FULL, self.batt + CHARGE_V_PER_S * dt)
        if self.batt < BATT_LOW:                                      # must stay low for 5 s (filters sag)
            if self.low_since is None:
                self.low_since = self.t
            elif not self.B and self.t - self.low_since >= 5.0:
                self.B = True
                self.cancel_waiting("LOW_BATT", batt=round(self.batt, 2))
        else:
            self.low_since = None
        if self.B and self.depot and self.batt > BATT_RECHARGED:
            self.B = False
            self.event("BATT_OK")
            self.dirty = True
        self.crit = self.batt < BATT_CRIT

    def drive(self, dt, O):
        if self.E:
            self.enter("EMERGENCY_STOP")
            return
        if self.F:
            self.event("FAULT", what="line lost")
            self.enter("LINE_LOST")
            return
        if O:
            self.event("OBSTACLE", dist=self.rng.randint(8, 14))
            self.enter("OBSTACLE_HOLD")
            return
        if self.state == "RUNNING" and self.paused:
            self.enter("LOW_BATTERY")
        if self.crit:
            return                                                    # motors cut below the critical voltage
        self.prog += dt / self.leg_time
        if self.leg == DEPOT_LEG and not self.depot_tag_done and self.prog >= DEPOT_FRAC:
            self.depot_tag_done = True                                # depot-entry tag read
            if not self.work() and (not self.patrol or self.paused):
                self.park()
                return
        if self.prog >= 1.0:
            self.read_tag(self.next_stop)

    def read_tag(self, k):
        p, d = self.flags(k)
        if p or d or self.para or (self.patrol and not self.paused):  # STOP = P + D + A + M.notB
            self.arrive(k, p, d)
        else:
            self.event("TAG_PASS", stop=k)
            self.start_leg(k)

    def arrive(self, k, p, d):
        unload = d or self.para
        done = [b["id"] for b in self.book if b["on"] and b["to"] == k]
        boarded = [b["id"] for b in self.book if not b["on"] and b["from"] == k]
        self.book = [b for b in self.book if b["id"] not in done]
        for b in self.book:
            if b["id"] in boarded:
                b["on"] = True
        self.para = False
        self.load, self.unload = p, unload
        self.stop_here, self.dwell_left = k, self.dwell
        self.start_leg(k)
        self.enter("LOADING_UNLOADING")
        self.event("ARRIVED", stop=k, load=p, unload=unload, boarded=boarded, done=done)

    def park(self):
        self.depot, self.ret = True, False
        self.start_leg(EXIT)
        self.enter("PARKED")
        self.event("PARKED")

    def status(self):
        O = self.t < self.obstacle_until
        return {"type": "status", "state": self.state, "next": self.next_stop, "depot": self.depot,
                "batt": round(self.batt, 2), "dist": self.rng.randint(8, 14) if O else self.rng.randint(40, 120),
                "head": 0, "patrol": self.patrol, "para": self.para, "lowbatt": self.B, "paused": self.paused,
                "crit": self.crit, "dwell": self.dwell, "load": self.load, "unload": self.unload,
                "ir": "000" if self.state == "LINE_LOST" else "010",
                "pick": [sum(1 for b in self.book if not b["on"] and b["from"] == i) for i in range(N)],
                "drop": [sum(1 for b in self.book if b["on"] and b["to"] == i) for i in range(N)],
                "wait": [b["id"] for b in self.book if not b["on"]],
                "ride": [b["id"] for b in self.book if b["on"]]}


# ======================= DATA SOURCES =======================
class DemoSource(threading.Thread):
    """Runs a JeepSim and sends the same messages as the real jeep."""

    def __init__(self, q):
        super().__init__(daemon=True)
        self.q = q
        self.halt = threading.Event()
        self.cmds = queue.Queue()
        self.sim = JeepSim()
        self.down_until = 0.0                    # simulated Wi-Fi drop

    def send(self, obj):
        self.cmds.put(obj)

    def stop(self):
        self.halt.set()

    def run(self):
        self.q.put(("conn", True))
        up, last, last_status = True, time.time(), 0.0
        while not self.halt.is_set():
            now = time.time()
            dt, last = min(now - last, 0.5), now
            link = now >= self.down_until
            while True:
                try:
                    c = self.cmds.get_nowait()
                except queue.Empty:
                    break
                if c.get("cmd") == "sim" and c.get("what") == "wifi":
                    self.down_until, link = now + 8.0, False
                elif link:
                    self.sim.command(c)              # commands sent while the link is down are lost
            if link != up:
                up = link
                self.q.put(("conn", up))
            self.sim.step(dt)
            out, self.sim.out = self.sim.out, []
            if link:                                 # the jeep keeps running while the link is down
                for m in out:
                    self.q.put(("msg", m))
                if self.sim.dirty or now - last_status >= 1.0:
                    self.q.put(("msg", self.sim.status()))
                    self.sim.dirty, last_status = False, now
            self.halt.wait(0.1)
        self.q.put(("conn", False))


class TcpSource(threading.Thread):
    """Reads JSON lines from the jeep over Wi-Fi (TCP). Reconnects by itself."""

    def __init__(self, host, port, q):
        super().__init__(daemon=True)
        self.host, self.port, self.q = host, port, q
        self.halt = threading.Event()
        self.sock = None
        self.lock = threading.Lock()

    def send(self, obj):
        with self.lock:
            if self.sock:
                try:
                    self.sock.sendall((json.dumps(obj) + "\n").encode())
                except OSError:
                    pass

    def stop(self):
        self.halt.set()
        with self.lock:
            if self.sock:
                try:
                    self.sock.close()
                except OSError:
                    pass

    def run(self):
        while not self.halt.is_set():
            try:
                s = socket.create_connection((self.host, self.port), timeout=4)
                s.settimeout(1.0)
                with self.lock:
                    self.sock = s
                self.q.put(("conn", True))
                buf = b""
                while not self.halt.is_set():
                    try:
                        data = s.recv(1024)
                    except socket.timeout:
                        continue
                    if not data:
                        break
                    buf += data
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        try:
                            msg = json.loads(line.decode("utf-8", "ignore"))
                        except ValueError:
                            continue
                        if isinstance(msg, dict):
                            self.q.put(("msg", msg))
            except OSError:
                pass
            finally:
                with self.lock:
                    if self.sock:
                        try:
                            self.sock.close()
                        except OSError:
                            pass
                    self.sock = None
                self.q.put(("conn", False))
            self.halt.wait(2.0)


# ======================= WIDGETS (small reusable screen parts) =======================
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


# ======================= APP =======================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        apply_theme(self)              # fonts, colors and ttk styles (see THEME section)
        self.title(APP_TITLE)
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jeep2.png")
        if os.path.exists(icon_path):
            self._app_icon = tk.PhotoImage(file=icon_path)
            self.iconphoto(True, self._app_icon)
        self.geometry("1200x780")
        self.minsize(1000, 740)
        self.q = queue.Queue()
        self.source = None
        self.tr = Tracker()
        self.bookings = []
        self.next_id = 1
        self.mode_var = tk.StringVar(value="demo")
        self.host_var = tk.StringVar(value=DEFAULT_HOST)
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.names = [s[0] for s in STOPS]
        self.sc, self.ox, self.oy = 1.0, 0.0, 0.0
        self.build_ui()
        # ----- window size: fit the finished layout so no tab is cut off, but stay on screen -----
        self.update_idletasks()
        height = min(max(780, self.winfo_reqheight() + 30), self.winfo_screenheight() - 80)   # +30: menu bar room on Linux
        self.geometry(f"1200x{height}")
        self.log_add("App started")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(250, self.tick)

    # ---------- layout ----------
    def build_ui(self):
        """Assemble the window: menu bar, map on the left, status and tabs on the right."""
        # ----- menu bar -----
        self.build_menu()
        # ----- main frame -----
        root = ttk.Frame(self, padding=PAD)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        # ----- left side: the map -----
        left = ttk.LabelFrame(root, text="Diorama map (the jeep pin is an estimate between stations)")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, PAD))
        self.cv = tk.Canvas(left, bg=PALETTE["map_bg"], highlightthickness=0)
        self.cv.pack(fill="both", expand=True, padx=PAD_S, pady=PAD_S)
        self.cv.bind("<Configure>", lambda e: self.draw_static())
        # ----- right side: connection, status card and tabs -----
        right = ttk.Frame(root)
        right.grid(row=0, column=1, sticky="ns")
        self.build_connection(right)
        self.build_status(right)
        self.nb = ttk.Notebook(right)
        self.nb.pack(fill="both", expand=True, pady=(PAD, 0))
        self.nb.add(self.build_trip(self.nb), text="Plan trip")
        self.nb.add(self.build_rides(self.nb), text="My rides")
        self.nb.add(self.build_schedule(self.nb), text="Schedule")
        self.nb.add(self.build_operator(self.nb), text="Operator")
        self.nb.add(self.build_log(self.nb), text="Log")

    def build_menu(self):
        """Menu bar: File (Exit), Demo (simulated problems) and Help."""
        bar = tk.Menu(self)
        m_file = tk.Menu(bar, tearoff=0)
        m_file.add_command(label="Exit", command=self.on_close)
        bar.add_cascade(label="File", menu=m_file)
        m_demo = tk.Menu(bar, tearoff=0)
        for text, what in (("Simulate obstacle", "obstacle"), ("Simulate line lost", "lineloss"),
                           ("Simulate low battery", "lowbatt"), ("Simulate Wi-Fi drop (8 s)", "wifi")):
            m_demo.add_command(label=text, command=lambda w=what, t=text: self.sim(w, t))
        bar.add_cascade(label="Demo", menu=m_demo)
        m_help = tk.Menu(bar, tearoff=0)
        m_help.add_command(label="How it works", command=self.show_help)
        bar.add_cascade(label="Help", menu=m_help)
        self.config(menu=bar)

    def build_connection(self, parent):
        """Connection box: choose Demo or Wi-Fi, set the jeep address and press Connect."""
        f = ttk.LabelFrame(parent, text="Connection", padding=PAD)
        f.pack(fill="x")
        ttk.Radiobutton(f, text="Demo (no jeep)", variable=self.mode_var, value="demo").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(f, text="Wi-Fi jeep", variable=self.mode_var, value="wifi").grid(row=0, column=1, sticky="w")
        ttk.Label(f, text="Host").grid(row=1, column=0, sticky="e")
        ttk.Entry(f, textvariable=self.host_var, width=16).grid(row=1, column=1, sticky="w")
        ttk.Label(f, text="Port").grid(row=1, column=2, sticky="e")
        ttk.Entry(f, textvariable=self.port_var, width=6).grid(row=1, column=3, sticky="w")
        self.btn_conn = ttk.Button(f, text="Connect", command=self.toggle_connection)
        self.btn_conn.grid(row=0, column=3, sticky="e", padx=(PAD, 0))
        self.v_conn = tk.StringVar(value="Not connected")
        ttk.Label(f, textvariable=self.v_conn).grid(row=2, column=0, columnspan=4, sticky="w", pady=(PAD_S, 0))

    def build_status(self, parent):
        """Status card. The most important facts (state, next stop, ETA) are large and sit at the top;
        battery and the Para button follow. Kept compact so the tabs below stay fully visible."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=PAD_L)
        card.pack(fill="x", pady=(PAD, 0))
        card.columnconfigure(0, weight=1)

        # ----- values shown in this card (changing one updates the screen) -----
        self.v_next, self.v_eta, self.v_etaclock = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.v_last, self.v_batt = tk.StringVar(), tk.StringVar(value="Battery: -")
        self.v_alert, self.v_note = tk.StringVar(), tk.StringVar()

        # ----- header: live state badge (left) and last station (right) -----
        self.badge = StatusBadge(card)
        self.badge.grid(row=0, column=0, sticky="w")
        ttk.Label(card, textvariable=self.v_last, style="CardMuted.TLabel").grid(
            row=0, column=1, sticky="e", padx=(PAD_L, 0))

        # ----- primary information: next stop (left) and arrival time (right) -----
        ttk.Label(card, text="Next stop", style="CardMuted.TLabel").grid(row=1, column=0, sticky="w", pady=(PAD, 0))
        ttk.Label(card, textvariable=self.v_next, style="CardDisplay.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Label(card, text="Arrives in", style="CardMuted.TLabel").grid(
            row=1, column=1, sticky="w", padx=(PAD_L, 0), pady=(PAD, 0))
        ttk.Label(card, textvariable=self.v_eta, style="CardTitle.TLabel").grid(
            row=2, column=1, sticky="w", padx=(PAD_L, 0))
        ttk.Label(card, textvariable=self.v_etaclock, style="CardMuted.TLabel").grid(
            row=3, column=1, sticky="w", padx=(PAD_L, 0))

        # ----- battery: percentage text above a colored bar -----
        ttk.Label(card, textvariable=self.v_batt, style="CardMuted.TLabel").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(PAD, 0))
        self.batt_bar = ttk.Progressbar(card, maximum=100, style="Ok.Horizontal.TProgressbar")
        self.batt_bar.grid(row=5, column=0, columnspan=2, sticky="we", pady=(PAD_S, 0))

        # ----- alert line (hidden whenever there is nothing to report) -----
        self.lbl_alert = ttk.Label(card, textvariable=self.v_alert, style="Alert.TLabel", wraplength=WRAP)
        self.lbl_alert.grid(row=6, column=0, columnspan=2, sticky="w", pady=(PAD, 0))
        self.lbl_alert.grid_remove()

        # ----- Para button and the jeep's reply to it (reply line appears only when there is one) -----
        ttk.Button(card, text="Para: stop at the next station", style="Primary.TButton",
                   command=self.do_para).grid(row=7, column=0, columnspan=2, sticky="we", pady=(PAD, 0))
        self.lbl_note = ttk.Label(card, textvariable=self.v_note, style="CardMuted.TLabel", wraplength=WRAP)
        self.lbl_note.grid(row=8, column=0, columnspan=2, sticky="w", pady=(PAD_S, 0))
        self.lbl_note.grid_remove()
        self.v_note.trace_add("write", lambda *_: self.lbl_note.grid() if self.v_note.get() else self.lbl_note.grid_remove())

    def build_trip(self, nb):
        """Plan trip tab: choose stations and passenger type, see fare and times, request a ride."""
        f = ttk.Frame(nb, padding=PAD)
        # ----- trip choices -----
        self.from_var = tk.StringVar(value=self.names[0])
        self.to_var = tk.StringVar(value=self.names[2])
        self.cat_var = tk.StringVar(value="Regular")
        ttk.Label(f, text="Ride on at").grid(row=0, column=0, sticky="w")
        ttk.Combobox(f, values=self.names, textvariable=self.from_var, state="readonly", width=16).grid(row=0, column=1, sticky="w", pady=PAD_S)
        ttk.Label(f, text="Get off at").grid(row=1, column=0, sticky="w")
        ttk.Combobox(f, values=self.names, textvariable=self.to_var, state="readonly", width=16).grid(row=1, column=1, sticky="w", pady=PAD_S)
        ttk.Label(f, text="Passenger").grid(row=2, column=0, sticky="w")
        ttk.Combobox(f, values=list(DISCOUNTS), textvariable=self.cat_var, state="readonly", width=16).grid(row=2, column=1, sticky="w", pady=PAD_S)
        # ----- fare and trip summary -----
        self.v_route, self.v_fare, self.v_wait = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.v_ride, self.v_total, self.v_arrive = tk.StringVar(), tk.StringVar(), tk.StringVar()
        ttk.Label(f, textvariable=self.v_route, wraplength=WRAP).grid(row=3, column=0, columnspan=2, sticky="w", pady=(PAD, 0))
        ttk.Label(f, text="Fare").grid(row=4, column=0, sticky="w")
        ttk.Label(f, textvariable=self.v_fare, font=F_TITLE).grid(row=4, column=1, sticky="w")
        for r, (t, v) in enumerate([("Jeep reaches you in", self.v_wait), ("Ride time", self.v_ride),
                                    ("Total", self.v_total), ("You arrive at", self.v_arrive)], start=5):
            ttk.Label(f, text=t).grid(row=r, column=0, sticky="w")
            ttk.Label(f, textvariable=v, font=F_HEADING).grid(row=r, column=1, sticky="w")
        # ----- request button and its message -----
        ttk.Button(f, text="Request ride", style="Primary.TButton", command=self.do_request).grid(row=9, column=0, columnspan=2, sticky="we", pady=(PAD, 0))
        self.v_tmsg = tk.StringVar()
        ttk.Label(f, textvariable=self.v_tmsg, wraplength=WRAP, style="Muted.TLabel").grid(row=10, column=0, columnspan=2, sticky="w", pady=(PAD, 0))
        return f

    def build_rides(self, nb):
        """My rides tab: a table of your requests and a Cancel button."""
        f = ttk.Frame(nb, padding=PAD)
        self.rtree = ttk.Treeview(f, columns=("id", "trip", "status", "eta"), show="headings", height=7, selectmode="browse")
        for c, t, w in (("id", "ID", 40), ("trip", "Trip", 80), ("status", "Status", 150), ("eta", "ETA", 70)):
            self.rtree.heading(c, text=t)
            self.rtree.column(c, width=w, anchor="w")
        self.rtree.pack(fill="x")
        ttk.Button(f, text="Cancel selected ride", command=self.do_cancel).pack(anchor="w", pady=PAD)
        self.v_rnote = tk.StringVar(value="No rides yet. Use Plan trip > Request ride.")
        ttk.Label(f, textvariable=self.v_rnote, wraplength=WRAP, style="Muted.TLabel").pack(anchor="w")
        ttk.Label(f, text="A ride can be cancelled until the jeep has picked you up. ETA is the pickup, then the drop-off.",
                  wraplength=WRAP, style="Muted.TLabel").pack(anchor="w", pady=(PAD, 0))
        return f

    def build_schedule(self, nb):
        """Schedule tab: operating hours, service status and when the jeep passes each station."""
        f = ttk.Frame(nb, padding=PAD)
        ttk.Label(f, text=f"Operating hours: {fmt12(OPEN_TIME)} to {fmt12(CLOSE_TIME)}", font=F_HEADING).pack(anchor="w")
        ttk.Label(f, text=SERVICE_DAYS).pack(anchor="w")
        self.v_service = tk.StringVar()
        self.lbl_service = ttk.Label(f, textvariable=self.v_service, font=F_HEADING)
        self.lbl_service.pack(anchor="w", pady=(PAD_S, PAD_S))
        self.v_svc = tk.StringVar()
        ttk.Label(f, textvariable=self.v_svc, wraplength=WRAP).pack(anchor="w", pady=(0, PAD))
        self.tree = ttk.Treeview(f, columns=("stn", "next", "after"), show="headings", height=4)
        for c, t, w in (("stn", "Station", 110), ("next", "Jeep passes", 100), ("after", "Following", 100)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        for i, n in enumerate(self.names):
            self.tree.insert("", "end", iid=str(i), values=(n, "-", "-"))
        self.tree.pack(fill="x")
        self.v_lap = tk.StringVar()
        ttk.Label(f, textvariable=self.v_lap, style="Muted.TLabel", wraplength=WRAP).pack(anchor="w", pady=(PAD, 0))
        return f

    def build_operator(self, nb):
        """Operator tab: vehicle controls, service settings and a live readout from the jeep."""
        f = ttk.Frame(nb, padding=PAD)

        # ----- dispatch buttons -----
        bar = ttk.Frame(f)
        bar.pack(fill="x")
        ttk.Button(bar, text="Dispatch", style="Primary.TButton", command=self.do_dispatch).pack(side="left")
        ttk.Button(bar, text="Return to depot", command=lambda: self.op("return")).pack(side="left", padx=PAD)
        ttk.Button(bar, text="Reset fault", command=lambda: self.op("reset")).pack(side="left")

        # ----- emergency stop (full width and kept apart from the other buttons) -----
        ttk.Button(f, text="EMERGENCY STOP", style="Danger.TButton",
                   command=lambda: self.op("estop")).pack(fill="x", pady=(PAD, PAD_S))

        # ----- service mode -----
        mf = ttk.LabelFrame(f, text="Service mode", padding=PAD_S)
        mf.pack(fill="x")
        self.svc_var = tk.StringVar(value="ondemand")
        ttk.Radiobutton(mf, text="On-demand", variable=self.svc_var, value="ondemand", command=self.set_mode).pack(side="left")
        ttk.Radiobutton(mf, text="Patrol (every stop)", variable=self.svc_var, value="patrol", command=self.set_mode).pack(side="left", padx=PAD_L)
        # ----- dwell time -----
        df = ttk.Frame(f)
        df.pack(fill="x", pady=(PAD_S, 0))
        ttk.Label(df, text="Dwell time (s)").pack(side="left")
        self.dwell_var = tk.StringVar(value=str(int(DWELL_S)))
        ttk.Spinbox(df, from_=1, to=30, width=5, textvariable=self.dwell_var).pack(side="left", padx=PAD)
        ttk.Button(df, text="Set", command=self.set_dwell).pack(side="left")
        # ----- live readout -----
        rf = ttk.LabelFrame(f, text="Live readout (from the jeep)", padding=PAD_S)
        rf.pack(fill="x", pady=(PAD, 0))
        self.ov = {k: tk.StringVar(value="-") for k in ("state", "mode", "batt", "sensors", "rides", "pick", "drop")}
        for r, (k, t) in enumerate((("state", "State"), ("mode", "Service mode"), ("batt", "Battery"), ("sensors", "Sensors"),
                                    ("rides", "Active rides (app)"), ("pick", "Waiting at"), ("drop", "Getting off at"))):
            ttk.Label(rf, text=t).grid(row=r, column=0, sticky="nw")
            ttk.Label(rf, textvariable=self.ov[k], wraplength=WRAP - 30).grid(row=r, column=1, sticky="w", padx=PAD)
        self.v_omsg = tk.StringVar()
        ttk.Label(f, textvariable=self.v_omsg, wraplength=WRAP, style="Muted.TLabel").pack(anchor="w", pady=(PAD_S, 0))
        return f

    def build_log(self, nb):
        """Log tab: a scrolling table of everything that happened (also saved to a file)."""
        f = ttk.Frame(nb, padding=PAD)
        self.logtree = ttk.Treeview(f, columns=("time", "event"), show="headings", height=14)
        self.logtree.heading("time", text="Time")
        self.logtree.heading("event", text="Event")
        self.logtree.column("time", width=70, anchor="w")
        self.logtree.column("event", width=290, anchor="w")
        sb = ttk.Scrollbar(f, orient="vertical", command=self.logtree.yview)
        self.logtree.configure(yscrollcommand=sb.set)
        self.logtree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        f.rowconfigure(0, weight=1)
        ttk.Button(f, text="Clear list", command=lambda: self.logtree.delete(*self.logtree.get_children())).grid(
            row=1, column=0, sticky="w", pady=(PAD, 0))
        ttk.Label(f, text="Every event is also saved to data/log.csv", style="Muted.TLabel").grid(row=2, column=0, sticky="w")
        return f

    # ---------- log and messages ----------
    def log_add(self, text):
        stamp = datetime.now()
        self.logtree.insert("", 0, values=(stamp.strftime("%H:%M:%S"), text))
        kids = self.logtree.get_children()
        if len(kids) > 500:
            self.logtree.delete(kids[-1])
        try:
            os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
            with open(LOG_FILE, "a", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerow([stamp.isoformat(timespec="seconds"), text])
        except OSError:
            pass

    def show_help(self):
        messagebox.showinfo("How it works",
                            "The jeep stops at a station only if:\n"
                            " - someone booked a pickup there,\n"
                            " - a rider on board booked a drop-off there,\n"
                            " - someone pressed Para, or\n"
                            " - the service mode is Patrol.\n\n"
                            "Otherwise it passes the station. When nobody needs it, it parks in the depot "
                            "and wakes up when a ride is requested.\n\n"
                            "Fares, times and ride counts are simulated; the jeep cannot see real passengers.")

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

    def do_request(self):
        now = time.time()
        a, b = self.trip_ends()
        why = self.reject_reason(a, b, now)
        if why:
            self.v_tmsg.set("Request rejected: " + why)
            self.log_add("Request rejected: " + why)
            return
        legs = (b - a) % N
        cat = self.cat_var.get()
        bk = Booking(self.next_id, a, b, cat, fare_for(legs, cat), now)
        self.next_id += 1
        self.bookings.append(bk)
        self.send({"cmd": "request", "id": bk.id, "from": a, "to": b})
        self.v_rnote.set("Select a ride and press Cancel to cancel it.")
        self.v_tmsg.set(f"Ride #{bk.id} requested: {self.names[a]} > {self.names[b]}, fare {CURRENCY}{bk.fare:.2f} ({cat}). "
                        "Track it in My rides.")
        self.log_add(f"Ride #{bk.id} requested: {self.names[a]} > {self.names[b]} ({cat}, {CURRENCY}{bk.fare:.2f})")

    def do_cancel(self):
        sel = self.rtree.selection()
        if not sel:
            self.v_rnote.set("Select a ride in the list first.")
            return
        bk = self.book_by_id(int(sel[0]))
        if bk is None:
            return
        if not bk.cancellable:
            self.v_rnote.set(f"Ride #{bk.id} cannot be cancelled (status: {bk.status.lower()}).")
        elif not self.fresh(time.time()):
            self.v_rnote.set("Cannot cancel while the jeep is offline. Try again when it reconnects.")
        else:
            self.send({"cmd": "cancel", "id": bk.id})
            self.v_rnote.set(f"Cancel sent for ride #{bk.id}...")

    def do_para(self):
        if not self.fresh(time.time()):
            self.v_note.set("Para not sent: the jeep is offline.")
            return
        self.send({"cmd": "para"})

    def op(self, cmd, **kw):
        if not (self.source and self.fresh(time.time())):
            self.v_omsg.set("Not connected to the jeep." + (" For a real emergency use the toggle switch on the jeep!" if cmd == "estop" else ""))
            return
        self.v_omsg.set("")
        self.send({"cmd": cmd, **kw})

    def do_dispatch(self):
        if self.tr.paused:
            self.v_omsg.set("Cannot dispatch: the battery is low. Wait for it to recharge.")
        else:
            self.op("dispatch")

    def set_mode(self):
        self.op("mode", value=self.svc_var.get())

    def set_dwell(self):
        try:
            v = float(self.dwell_var.get())
        except ValueError:
            self.v_omsg.set("Dwell time must be a number.")
            return
        if not 1 <= v <= 30:
            self.v_omsg.set("Dwell time must be between 1 and 30 seconds.")
            return
        self.op("dwell", value=v)

    def sim(self, what, text):
        if not isinstance(self.source, DemoSource):
            messagebox.showinfo("Demo only", "Connect in Demo mode first, then use this menu.")
            return
        self.log_add("Demo: " + text.lower())
        self.send({"cmd": "sim", "what": what})

    # ---------- events from the jeep ----------
    def on_event(self, m, now):
        ev = m.get("ev")

        def nm(i):
            return self.names[i] if isinstance(i, int) and 0 <= i < N else "?"

        if ev == "ARRIVED":
            self.log_add(f"Arrived at {nm(m.get('stop'))}: {stop_label(bool(m.get('load')), bool(m.get('unload')))}")
        elif ev == "DEPARTED":
            self.log_add(f"Left {nm(m.get('stop'))}")
        elif ev == "TAG_PASS":
            self.log_add(f"Passed {nm(m.get('stop'))} (nobody to pick up or drop off)")
        elif ev == "PARA":
            if m.get("ok", True):
                self.log_add("Para pressed: the jeep will stop at the next station")
                self.v_note.set("Para accepted: the jeep will stop at the next station.")
            else:
                self.log_add("Para ignored: the jeep is parked")
                self.v_note.set("Para ignored: the jeep is parked.")
        elif ev == "OBSTACLE":
            self.log_add(f"Obstacle detected ({m.get('dist', '?')} cm): jeep stopped")
        elif ev == "OBSTACLE_CLEAR":
            self.log_add("Obstacle cleared: jeep moving again")
        elif ev == "FAULT":
            self.log_add("FAULT: line lost. Put the jeep back on the line, then press Reset")
        elif ev == "ESTOP":
            self.log_add("EMERGENCY STOP")
        elif ev == "RESET":
            self.log_add("Reset")
        elif ev == "DISPATCHED":
            self.log_add("Jeep left the depot")
        elif ev == "PARKED":
            self.log_add("Jeep parked at the depot")
        elif ev == "BATT_OK":
            self.log_add("Battery recharged: service resumed")
        elif ev == "MODE":
            self.log_add("Service mode: " + ("Patrol" if m.get("patrol") else "On-demand"))
        elif ev in ("LOW_BATT", "RETURNING"):
            why = "low battery" if ev == "LOW_BATT" else "return to depot ordered"
            ids = int_list(m.get("cancelled"))
            for bid in ids:
                b = self.book_by_id(bid)
                if b and b.active:
                    b.status, b.note = "CANCELLED", why
            extra = f"{len(ids)} pending pickup(s) cancelled, " if ids else ""
            volts = f" ({m.get('batt')} V)" if ev == "LOW_BATT" else ""
            self.log_add(f"{why.capitalize()}{volts}: {extra}returning to the depot")
            if ids:
                self.v_rnote.set(f"Ride(s) {', '.join('#' + str(i) for i in ids)} cancelled: the jeep is returning to the depot.")
        elif ev == "REJECTED":
            b = self.book_by_id(m.get("id"))
            if b and b.active:
                b.status, b.note = "REJECTED", str(m.get("reason", ""))
            self.v_tmsg.set("Rejected by the jeep: " + str(m.get("reason", "")))
            self.log_add(f"Ride #{m.get('id')} rejected by the jeep: {m.get('reason', '')}")
        elif ev == "CANCELLED":
            b = self.book_by_id(m.get("id"))
            if b is None:
                return
            if m.get("ok"):
                if b.active:
                    b.status, b.note = "CANCELLED", "by you"
                self.v_rnote.set(f"Ride #{b.id} cancelled.")
                self.log_add(f"Ride #{b.id} cancelled by the passenger")
            else:
                self.v_rnote.set(f"Too late: ride #{b.id} is already on board.")

    def sync_bookings(self, now):
        """Bring the bookings in line with the jeep's wait/ride lists (the jeep is the truth)."""
        wait, ride = set(self.tr.wait_ids), set(self.tr.ride_ids)
        for b in self.bookings:
            if not b.active:
                continue
            if b.id in ride:
                if b.status != "BOARDED":
                    b.status = "BOARDED"
                    self.log_add(f"Ride #{b.id} boarded at {self.names[b.pickup]}")
            elif b.id in wait:
                continue
            elif b.status == "BOARDED":
                b.status = "COMPLETED"
                self.log_add(f"Ride #{b.id} completed at {self.names[b.drop]}")
            elif now - b.sent > REQUEST_GRACE_S:                      # the jeep no longer has it
                b.status, b.note = "CANCELLED", "dropped by the jeep"
                self.log_add(f"Ride #{b.id} is no longer on the jeep's list: cancelled")

    # ---------- connection ----------
    def toggle_connection(self):
        if self.source:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        if self.mode_var.get() == "demo":
            self.source = DemoSource(self.q)
        else:
            host = self.host_var.get().strip()
            if not host:
                self.v_conn.set("Enter the jeep's host address")
                return
            try:
                port = int(self.port_var.get())
            except ValueError:
                self.v_conn.set("Port must be a number")
                return
            if not 1 <= port <= 65535:
                self.v_conn.set("Port must be between 1 and 65535")
                return
            self.source = TcpSource(host, port, self.q)
        self.tr.clear()
        self.tr.connected = False
        self.source.start()
        self.btn_conn.config(text="Disconnect")
        self.log_add("Connecting (" + ("demo" if self.mode_var.get() == "demo" else self.host_var.get().strip()) + ")")

    def disconnect(self):
        if self.source:
            self.source.stop()
            self.source = None
            self.log_add("Disconnected")
        self.tr.connected = False
        self.btn_conn.config(text="Connect")

    def on_link(self, up):
        if up == self.tr.connected:
            return
        self.tr.connected = up
        if up:
            self.tr.clear()
            self.log_add("Connected to the jeep")
            self.send({"cmd": "sync", "ids": [b.id for b in self.bookings if b.active]})
            self.send({"cmd": "mode", "value": self.svc_var.get()})
            self.send({"cmd": "dwell", "value": to_float(self.dwell_var.get(), DWELL_S)})
        elif self.source:
            self.log_add("Connection lost")

    def on_close(self):
        self.disconnect()
        self.destroy()

    # ---------- periodic update ----------
    def tick(self):
        now = time.time()
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

    # ---------- map ----------
    def w2c(self, p):
        return (self.ox + p[0] * self.sc, self.oy + p[1] * self.sc)

    def draw_static(self):
        c = self.cv
        c.delete("all")
        cw, ch = max(c.winfo_width(), 200), max(c.winfo_height(), 200)
        self.sc = min((cw - 50) / 600.0, (ch - 50) / 650.0)
        self.ox, self.oy = (cw - 600 * self.sc) / 2, (ch - 650 * self.sc) / 2
        P, s = self.w2c, self.sc
        for x1, y1, x2, y2 in BLOCKS:
            a, b = P((x1, y1)), P((x2, y2))
            c.create_polygon(rrect(a[0], a[1], b[0], b[1], 14 * s), smooth=True, fill=PALETTE["map_block"], outline=PALETTE["map_block_edge"], tags="block")
        w = max(3, 5 * s)
        a, b = P((50, 50)), P((550, 510))
        c.create_polygon(rrect(a[0], a[1], b[0], b[1], 40 * s), smooth=True, fill="", outline=PALETTE["map_road"], width=w, tags="road")
        for p1, p2 in (((300, 50), (300, 510)), ((50, 280), (550, 280)), ((200, 510), (200, 600))):
            c.create_line(*P(p1), *P(p2), fill=PALETTE["map_road"], width=w, tags="road")
        a, b = P((160, 600)), P((240, 630))
        c.create_rectangle(a[0], a[1], b[0], b[1], fill=PALETTE["map_depot_fill"], outline=PALETTE["map_depot_edge"], tags="road")
        c.create_text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, text="Depot", font=(FONT_FAMILY, max(9, int(8 * s * 1.6))))
        for path in LEG_PATHS:                                       # direction arrows
            p1, p2 = point_at(path, 0.47), point_at(path, 0.53)
            c.create_line(*P(p1), *P(p2), arrow=tk.LAST, arrowshape=(10, 12, 5), fill=PALETTE["muted"], width=2, tags="road")
        r = max(8, 10 * s)
        for i, (name, pos) in enumerate(STOPS):
            x, y = P(pos)
            c.create_oval(x - r, y - r, x + r, y + r, fill=PALETTE["card"], outline=PALETTE["accent"], width=3, tags="stop")
            dx, dy, anc = LABEL_POS[i]
            c.create_text(x + dx, y + dy, text=f"{i + 1}. {name}", anchor=anc, font=(FONT_FAMILY, max(9, int(9 * s * 1.5)), "bold"), tags="stop")
        self.draw_dynamic(time.time())

    def draw_dynamic(self, now):
        c, P, s, tr = self.cv, self.w2c, self.sc, self.tr
        c.delete("dyn")
        a, b = self.trip_ends()                                      # highlight the planned ride
        if a != b:
            for k in range((b - a) % N):
                pts = [P(p) for p in LEG_PATHS[(a + k) % N]]
                c.create_line(*[v for p in pts for v in p], width=max(10, 13 * s), fill=PALETTE["map_route"], capstyle="round", joinstyle="round", tags=("dyn", "hl"))
            c.tag_lower("hl", "road")
        fresh = self.fresh(now)
        r = max(13, 16 * s)
        if fresh and tr.state != "PARKED":
            if not tr.depot:
                lx, ly = P(STOPS[tr.last_stop][1])
                c.create_oval(lx - r - 4, ly - r - 4, lx + r + 4, ly + r + 4, outline=PALETTE["ok"], width=3, tags="dyn")
            nx, ny = P(STOPS[tr.next_stop][1])
            c.create_oval(nx - r - 4, ny - r - 4, nx + r + 4, ny + r + 4, outline=PALETTE["map_next"], width=3, dash=(4, 3), tags="dyn")
        self.draw_requests(now)
        bx, by = P(tr.position())
        col = STATE_COLOR.get(tr.state, PALETTE["muted"]) if fresh else PALETTE["disabled"]
        br = max(15, 17 * s)
        c.create_oval(bx - br, by - br, bx + br, by + br, fill=col, outline=PALETTE["on_color"], width=2, tags="dyn")
        c.create_text(bx, by, text="JEEP", fill=PALETTE["on_color"], font=(FONT_FAMILY, max(8, int(7 * s * 1.2)), "bold"), tags="dyn")
        if fresh and tr.state in ("RUNNING", "LOW_BATTERY", "OBSTACLE_HOLD", "LINE_LOST") and tr.leg_start is not None:
            c.create_text(bx, by + br + 9, text="estimated", fill=PALETTE["muted"], font=F_SMALL, tags="dyn")
        if fresh and tr.para:
            c.create_text(bx, by - br - 9, text="PARA", fill=PALETTE["map_pickup"], font=F_SMALL_BOLD, tags="dyn")
        if fresh and tr.depot and tr.lowbatt:
            x, y = P((200, 645))
            c.create_text(x, y, text="charging", fill=PALETTE["muted"], font=F_SMALL, tags="dyn")

    def draw_requests(self, now):
        """Orange ring = someone waiting for a pickup, blue ring = a rider getting off there."""
        c, P, s = self.cv, self.w2c, self.sc
        for i in range(N):
            pick = sum(1 for b in self.bookings if b.status == "WAITING" and b.pickup == i)
            drop = sum(1 for b in self.bookings if b.status == "BOARDED" and b.drop == i)
            if not (pick or drop):
                continue
            x, y = P(STOPS[i][1])
            r = max(14, 17 * s) + 4 * math.sin(now * 4)
            col = PALETTE["map_pickup"] if pick else PALETTE["map_drop"]
            c.create_oval(x - r, y - r, x + r, y + r, outline=col, width=3, tags="dyn")
            label = " + ".join(t for t, n in (("PICKUP", pick), ("DROP", drop)) if n)
            ty = y - r - 8 if LABEL_POS[i][1] >= 0 else y + r + 8    # keep clear of the station name
            c.create_text(x, ty, text=label, fill=col, font=F_SMALL_BOLD, tags="dyn")


def main():
    App().mainloop()


if __name__ == "__main__":
    main()

# IMAGES
import os
icon_path = os.path.join(os.path.dirname(__file__), "jeep2.png")
if os.path.exists(icon_path):
    self._app_icon = tk.PhotoImage(file=icon_path)
    self.iconphoto(True, self._app_icon)
