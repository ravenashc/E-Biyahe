"""Settings you can change: fares, hours, battery levels, file locations and text sizes.
Every other file reads its numbers from here."""

import os
import sys


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
MESSAGE_S = {"info": 5, "ok": 5, "warn": 8, "error": 8}   # seconds a message stays in the message bar
OPERATOR_PIN = "1234"          # unlocks Operator mode. CHANGE IT. It only prevents accidents: anyone who can read this file can read the PIN
OPERATOR_IDLE_MIN = 10         # Operator mode signs out by itself after this many minutes without a key press or click
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "log.csv")
SETTINGS_FILE = os.path.join(os.path.dirname(LOG_FILE), "settings.json")    # remembers the text size between runs
TEXT_SIZES = (100, 115, 130, 150)   # text size steps in percent of normal (the first one is the normal size)
TAB_NAMES = ("Plan trip", "My rides", "Schedule", "Operator", "Log")        # tab order: Ctrl+1 ... Ctrl+5
IS_MAC = sys.platform == "darwin"
MOD, MOD_NAME = ("Command", "Cmd") if IS_MAC else ("Control", "Ctrl")      # the main shortcut key
