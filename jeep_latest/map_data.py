"""The map as data: station positions, roads, the terminal and the jeep's seven states."""

from helpers import path_len
from theme import PALETTE


# ======================= MAP LAYOUT AND JEEP STATES =======================

# The map is a landscape rectangle, WORLD_W x WORLD_H map points. The jeep drives a loop road around two rows of blocks.
WORLD_W, WORLD_H = 1000, 560
LOOP = (50, 50, 950, 430)                  # the middle line of the loop road: left, top, right, bottom
ROAD_W = 40                                # how wide the road is, in map points (the jeep drives along its middle)
STREET_W = 40                              # width of the visual connecting streets

# Stations in the order the jeep visits them, with their position on the map.
# TR sits on the top road after the upper-right bend; BL sits on the bottom road just
# before the terminal spur, so the jeep reaches it before the terminal turn.
STOPS = [
    ("THIRSTOP Station", (950, 330)),       # BR
    ("E.S.P. CORP. Station", (850, 50)),     # TR
    ("PARKSILICA Station", (50, 150)),      # TL
    ("LILIM Station", (150, 430)),          # BL
]
N = len(STOPS)
LEG_PATHS = [                  # leg i = from station i to station i+1 (map points)
    [(950, 330), (950, 50), (850, 50)],                    # up the right side, then onto the top road to TR
    [(850, 50), (50, 50), (50, 150)],                      # across the top, then down to TL
    [(50, 150), (50, 430), (150, 430)],                    # down the left side, then along the bottom to BL
    [(150, 430), (250, 430), (950, 430), (950, 330)],      # past the terminal spur, then around to BR
]
BLOCKS = [(84, 84, 476, 216), (524, 84, 916, 216), (84, 264, 476, 396), (524, 264, 916, 396)]   # top-left, top-right, bottom-left, bottom-right (each clear of the road and the side streets)
SIDE_STREETS = (((500, 50), (500, 430)), ((50, 240), (950, 240)))  # visual cross streets; the jeep stays on its outer loop
INTERSECTION_CENTER = (500, 240)
INTERSECTION_BOX = 34              # yellow keep-clear box, sized to fit the central road crossing
CROSSWALK_OFFSET = 82              # distance from the center to each zebra crossing
# One landmark per block, in the same order as BLOCKS: (drawing, name). Drawings are made in app_map.py (draw_landmark).
LANDMARKS = [("market", "Public Market"), ("hall", "Barangay Hall"), ("school", "School"), ("park", "Park")]
LABEL_POS = [(-1, 0, "e"), (0, 1, "n"), (1, 0, "w"), (0, -1, "s")]  # per station: label direction and anchor

# The terminal hangs off leg 3 (LILIM > THIRSTOP). Leaving it, the jeep joins the loop toward THIRSTOP.
DEPOT_POS = (250, 515)
DEPOT_ROAD = ((250, 430), (250, 500))      # the spur from the loop down to the terminal
DEPOT_BOX = (200, 500, 300, 536)
DEPOT_LABEL = (192, 518)                   # the word "Terminal" sits to the left of the box, so a parked jeep does not cover it
CHARGING_POS = (250, 548)
EXIT_PATH = [DEPOT_POS, (250, 430), (950, 430), (950, 330)]
EXIT_STOP = 0                  # the first station tag after leaving the terminal (BR)
DEPOT_LEG = 3                  # the leg where the terminal-entry tag sits

STATES = ("PARKED", "RUNNING", "LOADING_UNLOADING", "OBSTACLE_HOLD", "LINE_LOST", "EMERGENCY_STOP", "LOW_BATTERY")
MOVING = ("RUNNING", "LOW_BATTERY")
STATE_TEXT = {"PARKED": "Parked at terminal", "RUNNING": "Driving", "LOADING_UNLOADING": "At station",
              "OBSTACLE_HOLD": "Stopped: obstacle ahead", "LINE_LOST": "FAULT: line lost",
              "EMERGENCY_STOP": "EMERGENCY STOP", "LOW_BATTERY": "Returning to terminal"}
STATE_COLOR = {"RUNNING": PALETTE["ok"], "LOW_BATTERY": PALETTE["warn"],
               "LOADING_UNLOADING": PALETTE["warn"], "OBSTACLE_HOLD": PALETTE["danger"],
               "LINE_LOST": PALETTE["danger"], "EMERGENCY_STOP": PALETTE["danger"]}


# fraction of leg 3 at which the terminal-entry tag sits (where the spur leaves the road)
DEPOT_FRAC = path_len([(150, 430), (250, 430)]) / path_len(LEG_PATHS[DEPOT_LEG])
EXIT = -1                       # "leg number" of the terminal -> BL exit path
