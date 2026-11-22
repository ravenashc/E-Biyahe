"""The map as data: station positions, roads, the depot and the jeep's seven states."""

from helpers import path_len
from theme import PALETTE


# ======================= MAP LAYOUT AND JEEP STATES =======================

# The map is a landscape rectangle, WORLD_W x WORLD_H map points. The jeep drives a loop road around two rows of blocks.
WORLD_W, WORLD_H = 1000, 560
LOOP = (50, 50, 950, 430)                  # the middle line of the loop road: left, top, right, bottom
ROAD_W = 40                                # how wide the road is, in map points (the jeep drives along its middle)
STREET_W = 24                              # how wide the side streets are

# Stations in the order the jeep visits them, with their position on the map.
# All four sit on the outer road, level with the middle of a block row: BR and TR on the right side, TL and BL on the left.
STOPS = [
    ("BR Station", (950, 330)),
    ("TR Station", (950, 150)),
    ("TL Station", (50, 150)),
    ("BL Station", (50, 330)),
]
N = len(STOPS)
LEG_PATHS = [                  # leg i = from station i to station i+1 (map points)
    [(950, 330), (950, 150)],                              # up the right side
    [(950, 150), (950, 50), (50, 50), (50, 150)],          # round the top
    [(50, 150), (50, 330)],                                # down the left side
    [(50, 330), (50, 430), (950, 430), (950, 330)],        # along the bottom
]
BLOCKS = [(84, 84, 476, 216), (524, 84, 916, 216), (84, 264, 476, 396), (524, 264, 916, 396)]   # top-left, top-right, bottom-left, bottom-right (each clear of the road and the side streets)
SIDE_STREETS = (((500, 75), (500, 405)), ((75, 240), (925, 240)))      # decoration only: the jeep never drives on these
# One landmark per block, in the same order as BLOCKS: (drawing, name). Drawings are made in app_map.py (draw_landmark).
LANDMARKS = [("market", "Public Market"), ("hall", "Barangay Hall"), ("school", "School"), ("church", "Church")]
LABEL_POS = [(-1, 0, "e"), (-1, 0, "e"), (1, 0, "w"), (1, 0, "w")]   # per station: (x direction, y direction, text anchor) = which side of the circle its name sits on

# The depot hangs off leg 3 (BL > BR). Leaving it, the jeep joins the loop toward BR.
DEPOT_POS = (250, 515)
DEPOT_ROAD = ((250, 430), (250, 500))      # the spur from the loop down to the depot
DEPOT_BOX = (200, 500, 300, 536)
DEPOT_LABEL = (192, 518)                   # the word "Depot" sits to the left of the box, so a parked jeep does not cover it
CHARGING_POS = (250, 548)
EXIT_PATH = [DEPOT_POS, (250, 430), (950, 430), (950, 330)]
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
DEPOT_FRAC = path_len([(50, 330), (50, 430), (250, 430)]) / path_len(LEG_PATHS[DEPOT_LEG])
EXIT = -1                       # "leg number" of the depot -> BL exit path
