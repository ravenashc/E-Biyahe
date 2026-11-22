"""The data model: Tracker (what the jeep last reported, plus the ETA guesses built from it)."""

from config import DISPATCH_S, DWELL_S, LEARN_ALPHA, SPEED_UNITS_PER_S
from helpers import path_len, point_at, to_float
from map_data import DEPOT_POS, EXIT_PATH, EXIT_STOP, LEG_PATHS, MOVING, N, STATES, STOPS


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
        self.dwell = DWELL_S
        self.ir = ""

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
        self.dwell = max(1.0, to_float(msg.get("dwell"), self.dwell))
        self.ir = str(msg.get("ir", ""))

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
        """Where to draw the jeep on the map (an estimate between stations)."""
        if self.depot:
            return DEPOT_POS
        if self.leg_start is not None:
            return point_at(self.cur_path(), self.frac)
        return STOPS[self.last_stop][1]

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

    def eta_to_stop(self, idx, now, dispatch=False):
        """Seconds until the jeep reaches station idx (0 = it is there now). The jeep patrols: it stops at every station."""
        if self.state == "LOADING_UNLOADING" and self.last_stop == idx:
            return 0.0
        t = self.eta_to_next(now, dispatch)
        if t is None:
            return None
        cur = self.next_stop
        for _ in range(N):
            if cur == idx:
                break
            t += self.dwell + self.leg_est[cur]
            cur = (cur + 1) % N
        return t

    def lap_time(self):
        return sum(self.leg_est) + N * self.dwell
