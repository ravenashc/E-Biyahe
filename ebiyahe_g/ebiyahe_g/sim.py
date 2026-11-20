"""JeepSim: the pretend jeep used by Demo mode. It follows the same rules as the real jeep's firmware."""

import random

from config import (
    BATT_CRIT, BATT_DRAIN_V_PER_S, BATT_FULL, BATT_LOW, BATT_RECHARGED, CHARGE_V_PER_S, DWELL_S,
    MAX_ACTIVE, SPEED_UNITS_PER_S,
)
from helpers import int_list, path_len, to_float
from map_data import DEPOT_FRAC, DEPOT_LEG, EXIT, EXIT_PATH, EXIT_STOP, LEG_PATHS, MOVING, N


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
