"""The map as data: station positions, roads, the depot and the jeep's seven states."""

from helpers import path_len
from theme import PALETTE


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
LABEL_POS = [(-1, 0, "e"), (0, -1, "s"), (0, -1, "s"), (1, 0, "w")]   # per station: (x direction, y direction, text anchor) = which side of the circle its name sits on

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


# fraction of leg 3 at which the depot-entry tag sits (where the spur leaves the road)
DEPOT_FRAC = path_len([(50, 395), (50, 510), (200, 510)]) / path_len(LEG_PATHS[DEPOT_LEG])
EXIT = -1                       # "leg number" of the depot -> BL exit path
