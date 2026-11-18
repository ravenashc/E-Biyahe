"""Drawing the map: roads, stations, the map key, the jeep and the pickup/drop-off rings.

This is one part of the App window: App (app.py) inherits MapMixin, so these methods are called as self.<name>()."""

import math
import time
import tkinter as tk

import theme
from helpers import point_at, rrect
from map_data import BLOCKS, LABEL_POS, LEG_PATHS, N, STATE_COLOR, STOPS
from theme import F_SMALL, F_SMALL_BOLD, PAD, PALETTE


# ======================= MAP DRAWING =======================
class MapMixin:
    """Drawing the map: roads, stations, the map key, the jeep and the pickup/drop-off rings."""

    # ---------- map ----------
    def w2c(self, p):
        return (self.ox + p[0] * self.sc, self.oy + p[1] * self.sc)

    def stop_radius(self):
        """Radius in pixels of a station circle at the current map zoom (big enough to hold its number)."""
        return max(11 * self.text_factor, 13 * self.sc)

    def draw_static(self):
        """Draw the parts of the map that never move: blocks, roads, depot, stations and the map key.
        Called again only when the map is resized."""
        c = self.cv
        c.delete("all")
        cw, ch = max(c.winfo_width(), 200), max(c.winfo_height(), 200)
        self.sc = min((cw - 50) / 600.0, (ch - 50) / 650.0)
        self.ox, self.oy = (cw - 600 * self.sc) / 2, (ch - 650 * self.sc) / 2
        P, s = self.w2c, self.sc

        # ----- city blocks (green decoration) -----
        for x1, y1, x2, y2 in BLOCKS:
            a, b = P((x1, y1)), P((x2, y2))
            c.create_polygon(rrect(a[0], a[1], b[0], b[1], 14 * s), smooth=True, fill=PALETTE["map_block"], outline=PALETTE["map_block_edge"], tags="block")

        # ----- side streets (decoration only: the jeep never drives on these, so they are thin and light) -----
        for p1, p2 in (((300, 50), (300, 510)), ((50, 280), (550, 280))):
            c.create_line(*P(p1), *P(p2), fill=PALETTE["map_street"], width=max(7, 10 * s), tags="road")

        # ----- main loop road: soft gray with a dashed center line -----
        w = max(12, 18 * s)
        a, b = P((50, 50)), P((550, 510))
        loop = rrect(a[0], a[1], b[0], b[1], 40 * s)
        c.create_polygon(loop, smooth=True, fill="", outline=PALETTE["map_road"], width=w, tags="road")
        c.create_polygon(loop, smooth=True, fill="", outline=PALETTE["map_road_line"], width=1, dash=(8, 8), tags="road")

        # ----- depot: road, box and label (the label sits beside the box so a parked jeep does not cover it) -----
        c.create_line(*P((200, 510)), *P((200, 598)), fill=PALETTE["map_road"], width=w, tags="road")
        a, b = P((150, 598)), P((250, 634))
        c.create_rectangle(a[0], a[1], b[0], b[1], fill=PALETTE["map_depot_fill"], outline=PALETTE["map_depot_edge"], tags="road")
        x, y = P((142, 616))
        c.create_text(x, y, text="Depot", anchor="e", fill=PALETTE["text"], font=(theme.FONT_FAMILY, self.map_pt(8 * s * 1.6)), tags="road")

        # ----- direction arrows (white on the road, one per leg) -----
        for path in LEG_PATHS:
            p1, p2 = point_at(path, 0.47), point_at(path, 0.53)
            c.create_line(*P(p1), *P(p2), arrow=tk.LAST, arrowshape=(10, 12, 5), fill=PALETTE["on_color"], width=2, tags="road")

        # ----- stations: a numbered circle with the name beside it -----
        r = self.stop_radius()
        gap = r + 16                                   # distance from the circle to its name (clears the rings)
        for i, (name, pos) in enumerate(STOPS):
            x, y = P(pos)
            c.create_oval(x - r, y - r, x + r, y + r, fill=PALETTE["card"], outline=PALETTE["accent"], width=3, tags="stop")
            c.create_text(x, y, text=str(i + 1), fill=PALETTE["accent"], font=(theme.FONT_FAMILY, self.map_pt(8 * s * 1.3), "bold"), tags="stop")
            ux, uy, anc = LABEL_POS[i]
            c.create_text(x + ux * gap, y + uy * gap, text=name, anchor=anc, fill=PALETTE["text"],
                          font=(theme.FONT_FAMILY, self.map_pt(9 * s * 1.5), "bold"), tags="stop")

        # ----- map key and the moving layer -----
        self.draw_legend(cw, ch, s)
        self.draw_dynamic(time.time())

    def draw_legend(self, cw, ch, s):
        """Small key fixed to the bottom-right corner of the map canvas."""
        items = (("Waiting for pickup", "map_pickup", None), ("Rider getting off", "map_drop", None),
                 ("Last station", "ok", None), ("Next stop", "map_next", (4, 3)), ("Planned trip", "map_route", "bar"))
        row, width = round(20 * self.text_factor), round(172 * self.text_factor)
        height = PAD * 2 + row * (len(items) + 1) - 4
        x0, y0 = cw - width - 12, ch - height - 12
        c = self.cv
        # ----- key background and title -----
        c.create_polygon(rrect(x0, y0, x0 + width, y0 + height, 8), smooth=True, fill=PALETTE["card"], outline=PALETTE["border"], tags="legend")
        c.create_text(x0 + PAD, y0 + PAD, text="Map key", anchor="nw", fill=PALETTE["text"], font=F_SMALL_BOLD, tags="legend")
        # ----- one row per symbol -----
        for k, (label, color, style) in enumerate(items, start=1):
            y = y0 + PAD + row * k + 9
            ix = x0 + PAD + 9
            if style == "bar":
                c.create_line(ix - 9, y, ix + 9, y, width=8, fill=PALETTE[color], capstyle="round", tags="legend")
            else:
                c.create_oval(ix - 7, y - 7, ix + 7, y + 7, outline=PALETTE[color], width=3, dash=style, tags="legend")
            c.create_text(ix + 20, y, text=label, anchor="w", fill=PALETTE["text"], font=F_SMALL, tags="legend")

    def draw_dynamic(self, now):
        """Redraw the parts of the map that change: the planned-trip highlight, rings and the jeep."""
        c, P, s, tr = self.cv, self.w2c, self.sc, self.tr
        c.delete("dyn")

        # ----- highlight along the planned ride -----
        a, b = self.trip_ends()
        if a != b:
            for k in range((b - a) % N):
                pts = [P(p) for p in LEG_PATHS[(a + k) % N]]
                c.create_line(*[v for p in pts for v in p], width=max(16, 25 * s), fill=PALETTE["map_route"], capstyle="round", joinstyle="round", tags=("dyn", "hl"))
            c.tag_lower("hl", "road")
            
        # ----- last-station ring (green) and next-stop ring (dashed amber) -----
        fresh = self.fresh(now)
        r = self.stop_radius() + 6
        if fresh and tr.state != "PARKED":
            if not tr.depot:
                lx, ly = P(STOPS[tr.last_stop][1])
                c.create_oval(lx - r, ly - r, lx + r, ly + r, outline=PALETTE["ok"], width=3, tags="dyn")
            nx, ny = P(STOPS[tr.next_stop][1])
            c.create_oval(nx - r, ny - r, nx + r, ny + r, outline=PALETTE["map_next"], width=3, dash=(4, 3), tags="dyn")

        # ----- pickup and drop-off rings -----
        self.draw_requests(now)

        # ----- the jeep: a rounded body with two wheels, colored by its state -----
        bx, by = P(tr.position())
        col = STATE_COLOR.get(tr.state, PALETTE["muted"]) if fresh else PALETTE["disabled"]
        bw, bh = max(22 * self.text_factor, 26 * s), max(12 * self.text_factor, 14 * s)
        wr = max(3, 4 * s)
        for wx in (bx - bw * 0.55, bx + bw * 0.55):                                   # wheels (drawn first, body covers the top half)
            c.create_oval(wx - wr, by + bh - wr, wx + wr, by + bh + wr, fill=PALETTE["text"], outline="", tags="dyn")
        c.create_polygon(rrect(bx - bw, by - bh, bx + bw, by + bh, bh * 0.7), smooth=True, fill=col, outline=PALETTE["on_color"], width=2, tags="dyn")
        c.create_text(bx, by, text="JEEP", fill=PALETTE["on_color"], font=(theme.FONT_FAMILY, self.map_pt(7 * s * 1.4), "bold"), tags="dyn")

        # ----- small labels next to the jeep and the depot -----
        if fresh and tr.state in ("RUNNING", "LOW_BATTERY", "OBSTACLE_HOLD", "LINE_LOST") and tr.leg_start is not None:
            c.create_text(bx, by + bh + wr + 8, text="estimated", fill=PALETTE["muted"], font=F_SMALL, tags="dyn")
        if fresh and tr.para:
            c.create_text(bx, by - bh - 10, text="PARA", fill=PALETTE["map_pickup"], font=F_SMALL_BOLD, tags="dyn")
        if fresh and tr.depot and tr.lowbatt:
            x, y = P((200, 646))
            c.create_text(x, y, text="charging", fill=PALETTE["muted"], font=F_SMALL, tags="dyn")

    def draw_requests(self, now):
        """Orange ring = someone waiting for a pickup, blue ring = a rider getting off there."""
        c, P = self.cv, self.w2c
        for i in range(N):
            pick = sum(1 for b in self.bookings if b.status == "WAITING" and b.pickup == i)
            drop = sum(1 for b in self.bookings if b.status == "BOARDED" and b.drop == i)
            if not (pick or drop):
                continue
            x, y = P(STOPS[i][1])
            r = self.stop_radius() + 6 + 3 * math.sin(now * 4)       # pulses gently around the station circle
            col = PALETTE["map_pickup"] if pick else PALETTE["map_drop"]
            c.create_oval(x - r, y - r, x + r, y + r, outline=col, width=3, tags="dyn")
            label = " + ".join(t for t, n in (("PICKUP", pick), ("DROP", drop)) if n)
            ty = y - r - 8 if LABEL_POS[i][1] >= 0 else y + r + 8    # keep clear of the station name
            c.create_text(x, ty, text=label, fill=col, font=F_SMALL_BOLD, tags="dyn")
