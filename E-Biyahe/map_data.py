"""The map as data: station positions, roads, the terminal and the jeep's seven states."""

from helpers import path_len
from theme import PALETTE


# ======================= MAP LAYOUT AND JEEP STATES =======================

# The map is a landscape rectangle, WORLD_W x WORLD_H map points. The jeep drives a loop road around two rows of blocks.
WORLD_W, WORLD_H = 1000, 560
LOOP = (50, 50, 950, 430)                  # the middle line of the loop road: left, top, right, bottom
ROAD_W = 40                                # how wide the road is, in map points (the jeep drives along its middle)
STREET_W = 40                              # width of the visual connecting streets

# Stations are numbered in the order the jeep visits them after leaving the Terminal: 1 THIRSTOP, 2 E.S.P. CORP.,
# 3 PARKSILICA, 4 LILIM. The Terminal exit joins the bottom road and the jeep's first stop is station 1 (THIRSTOP).
STOPS = [
    ("THIRSTOP", (740, 430)),       # 1: bottom road, right of the Terminal spur
    ("E.S.P. CORP.", (950, 160)),   # 2: upper section of the right road
    ("PARKSILICA", (300, 50)),      # 3: top road
    ("LILIM", (50, 310)),           # 4: lower section of the left road
]
# Full names shown when a station is hovered on the map (the map blocks keep the short upper-case names).
STATION_TITLES = ["Thirstop Station", "E.S.P. Corp. Station", "Parksilica Station", "Lilim Station"]
N = len(STOPS)
LEG_PATHS = [                  # leg i = from station i to station i+1 (map points)
    [(740, 430), (950, 430), (950, 160)],                   # 1 -> 2: along the bottom, then up the right side
    [(950, 160), (950, 50), (300, 50)],                     # 2 -> 3: up the right side, then across the top
    [(300, 50), (50, 50), (50, 310)],                       # 3 -> 4: across the top, then down the left side
    [(50, 310), (50, 430), (740, 430)],                     # 4 -> 1: down the left side, then along the bottom (past the Terminal spur)
]
BLOCKS = [(84, 84, 476, 216), (524, 84, 916, 216), (84, 264, 476, 396), (524, 264, 916, 396)]   # top-left, top-right, bottom-left, bottom-right (each clear of the road and the side streets)
SIDE_STREETS = (((500, 50), (500, 430)), ((50, 240), (950, 240)))  # visual cross streets; the jeep stays on its outer loop
INTERSECTION_CENTER = (500, 240)
INTERSECTION_BOX = 34              # yellow keep-clear box, sized to fit the central road crossing
CROSSWALK_OFFSET = 82              # distance from the center to each zebra crossing
# One landmark per block, in the same order as BLOCKS: (drawing, name). Drawings are made in app_map.py (draw_landmark).
LANDMARKS = [("market", "Public Market"), ("hall", "Barangay Hall"), ("school", "School"), ("park", "Park")]
# The station names are written in the map blocks (under each landmark), not beside the station circles.
BLOCK_STATION = (2, 1, 3, 0)       # for BLOCKS in order (TL, TR, BL, BR): the index in STOPS of the station named there
                                   # TL = PARKSILICA, TR = E.S.P. CORP., BL = LILIM, BR = THIRSTOP
STOP_NUMBERS = (1, 2, 3, 4)        # the number shown in each station circle, in STOPS order

# The terminal spur joins leg 4 (LILIM > THIRSTOP). Leaving it, the jeep drives along the bottom road to station 1 (THIRSTOP).
DEPOT_POS = (250, 515)
DEPOT_ROAD = ((250, 430), (250, 500))      # the spur from the loop down to the terminal
DEPOT_BOX = (200, 500, 300, 536)
DEPOT_LABEL = (192, 518)                   # the word "Terminal" sits to the left of the box, so a parked jeep does not cover it
CHARGING_POS = (250, 548)
EXIT_PATH = [DEPOT_POS, (250, 430), (740, 430)]
EXIT_STOP = 0                  # the first station tag after leaving the terminal (station 1: THIRSTOP)
DEPOT_LEG = 3                  # the leg where the terminal-entry tag sits (station 4 > station 1)

STATES = ("PARKED", "RUNNING", "LOADING_UNLOADING", "OBSTACLE_HOLD", "LINE_LOST", "EMERGENCY_STOP", "LOW_BATTERY")
MOVING = ("RUNNING", "LOW_BATTERY")
STATE_TEXT = {"PARKED": "Parked at terminal", "RUNNING": "Driving", "LOADING_UNLOADING": "At station",
              "OBSTACLE_HOLD": "Stopped: obstacle ahead", "LINE_LOST": "FAULT: line lost",
              "EMERGENCY_STOP": "EMERGENCY STOP", "LOW_BATTERY": "Returning to terminal"}
STATE_COLOR = {"RUNNING": PALETTE["ok"], "LOW_BATTERY": PALETTE["warn"],
               "LOADING_UNLOADING": PALETTE["warn"], "OBSTACLE_HOLD": PALETTE["danger"],
               "LINE_LOST": PALETTE["danger"], "EMERGENCY_STOP": PALETTE["danger"]}


# fraction of leg 4 (LILIM > THIRSTOP) at which the terminal-entry tag sits
DEPOT_FRAC = path_len([(50, 310), (50, 430), (250, 430)]) / path_len(LEG_PATHS[DEPOT_LEG])
EXIT = -1                       # "leg number" of the terminal -> BL exit path
