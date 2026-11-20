"""Drawing the map: blocks and landmarks, roads, stations, the map key, the jeepney and the pickup/drop-off rings.

This is one part of the App window: App (app.py) inherits MapMixin, so these methods are called as self.<name>()."""

import math
import time
import tkinter as tk

import theme
from helpers import point_at, rrect
from jeepney import draw_jeepney
from map_data import BLOCKS, LABEL_POS, LANDMARKS, LEG_PATHS, N, STATE_COLOR, STOPS
from theme import F_SMALL, F_SMALL_BOLD, PAD, PALETTE


# ======================= MAP DRAWING =======================
class MapMixin:
    """Drawing the map: blocks and landmarks, roads, stations, the map key, the jeepney and the pickup/drop-off rings."""

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

        # ----- landmarks: a small drawing and a name in each block -----
        for (x1, y1, x2, y2), (kind, name) in zip(BLOCKS, LANDMARKS):
            self.draw_landmark(kind, name, (x1 + x2) / 2, (y1 + y2) / 2, (y2 - y1) / 2)

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
        gap = r + 24                                   # distance from the circle to its name (clears the pickup/drop-off ring, radius + 18)
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

    def draw_landmark(self, kind, name, cx, cy, half_h):
        """A small drawing (market, hall, school or church) with its name below, in the upper half of a block.
        The block's middle row is left free because the station names sit there. (cx, cy) is the block's centre and
        half_h its half height, both in map points. A small map gets a smaller drawing, and no name when space is short."""
        c, s = self.cv, self.sc
        x, y = self.w2c((cx, cy))
        ground = y - 15                                # the drawing stands on this line, clear of the station-name row
        avail = half_h * s - 15 - 5                    # pixels from that line up to the top edge of the block (5 px margin)
        name_h = 14 if (avail - 14) / 2.6 >= 7 else 0  # show the name only when the drawing can still be at least a decent size
        k = max(5.0, min(16 * s, (avail - name_h - 2) / 2.6))      # one drawing unit in pixels
        if name_h:
            c.create_text(x, ground - name_h / 2, text=name, fill=PALETTE["muted"], font=F_SMALL, tags="landmark")
            ground -= name_h
        wall, roof, line, glass = PALETTE["map_lm_wall"], PALETTE["map_lm_roof"], PALETTE["map_lm_line"], PALETTE["map_lm_glass"]

        def rect(x1, y1, x2, y2, fill):                # coordinates are in units of k from the ground line, y up is negative
            c.create_rectangle(x + x1 * k, ground + y1 * k, x + x2 * k, ground + y2 * k, fill=fill, outline=line, tags="landmark")

        def poly(pts, fill):
            c.create_polygon([v for px, py in pts for v in (x + px * k, ground + py * k)], fill=fill, outline=line, tags="landmark")

        def seg(x1, y1, x2, y2):
            c.create_line(x + x1 * k, ground + y1 * k, x + x2 * k, ground + y2 * k, fill=line, width=2, tags="landmark")

        if kind == "church":
            rect(-0.8, -1.1, 0.8, 0, wall)
            poly([(-1.0, -1.1), (0, -2.0), (1.0, -1.1)], roof)
            rect(-0.25, -0.6, 0.25, 0, roof)           # door
            seg(0, -2.0, 0, -2.6)                      # cross
            seg(-0.3, -2.35, 0.3, -2.35)
        elif kind == "school":
            rect(-1.3, -1.1, 1.3, 0, wall)
            rect(-1.4, -1.3, 1.4, -1.1, roof)          # flat roof
            rect(-1.1, -0.9, -0.6, -0.45, glass)       # windows
            rect(0.6, -0.9, 1.1, -0.45, glass)
            rect(-0.25, -0.7, 0.25, 0, roof)           # door
            seg(1.0, -1.3, 1.0, -2.5)                  # flagpole and flag
            poly([(1.0, -2.5), (1.7, -2.25), (1.0, -2.0)], roof)
        elif kind == "market":
            rect(-1.0, -0.9, 1.0, 0, wall)             # stall
            for i in range(4):                         # striped awning
                x0 = -1.2 + i * 0.6
                poly([(x0 * 0.85, -1.9), ((x0 + 0.6) * 0.85, -1.9), (x0 + 0.6, -1.0), (x0, -1.0)], roof if i % 2 == 0 else wall)
            for px, col in ((-0.5, "ok"), (0, "warn"), (0.5, "danger")):      # fruit on the counter
                c.create_oval(x + (px - 0.18) * k, ground - 0.55 * k, x + (px + 0.18) * k, ground - 0.19 * k,
                              fill=PALETTE[col], outline="", tags="landmark")
        elif kind == "hall":
            poly([(-1.3, -1.5), (0, -2.3), (1.3, -1.5)], roof)         # pediment
            rect(-1.3, -1.5, 1.3, -1.3, wall)
            for px in (-1.0, -0.35, 0.35, 1.0):        # columns
                rect(px - 0.12, -1.3, px + 0.12, -0.2, wall)
            rect(-1.4, -0.2, 1.4, 0, wall)             # steps

    def draw_legend(self, cw, ch, s):
        """Small key fixed to the bottom-right corner of the map canvas."""
        items = (("legend_pickup", "map_pickup", None), ("legend_drop", "map_drop", None),
                 ("legend_last", "ok", None), ("next_stop", "map_next", (4, 3)), ("legend_route", "map_route", "bar"))
        row, width = round(20 * self.text_factor), round(214 * self.text_factor)
        height = PAD * 2 + row * (len(items) + 1) - 4
        x0, y0 = cw - width - 12, ch - height - 12
        c = self.cv
        # ----- key background and title -----
        c.create_polygon(rrect(x0, y0, x0 + width, y0 + height, 8), smooth=True, fill=PALETTE["card"], outline=PALETTE["border"], tags="legend")
        c.create_text(x0 + PAD, y0 + PAD, text=self.labels.text("legend_title"), anchor="nw", fill=PALETTE["text"], font=F_SMALL_BOLD, tags="legend")
        # ----- one row per symbol -----
        for k, (key, color, style) in enumerate(items, start=1):
            y = y0 + PAD + row * k + 9
            ix = x0 + PAD + 9
            if style == "bar":
                c.create_line(ix - 9, y, ix + 9, y, width=8, fill=PALETTE[color], capstyle="round", tags="legend")
            else:
                c.create_oval(ix - 7, y - 7, ix + 7, y + 7, outline=PALETTE[color], width=3, dash=style, tags="legend")
            c.create_text(ix + 20, y, text=self.labels.text(key), anchor="w", fill=PALETTE["text"], font=F_SMALL, tags="legend")

    def draw_dynamic(self, now):
        """Redraw the parts of the map that change: the planned-trip highlight, rings and the jeep."""
        c, P, s, tr = self.cv, self.w2c, self.sc, self.tr
        c.delete("dyn")

        # ----- highlight along the planned ride -----
        a, b = self.trip_ends()
        if a != b:
            for k in range((b - a) % N):
                pts = [P(p) for p in LEG_PATHS[(a + k) % N]]
                c.create_line(*[v for p in pts for v in p], width=max(24, 38 * s), fill=PALETTE["map_route"], capstyle="round", joinstyle="round", tags=("dyn", "hl"))
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

        # ----- the jeepney: body colored by its state, facing the way it is driving -----
        bx, by = P(tr.position())
        col = STATE_COLOR.get(tr.state, PALETTE["muted"]) if fresh else PALETTE["disabled"]
        bw, bh = self.jeep_size()
        prev = getattr(self, "jeep_prev_x", None)
        if prev is not None and abs(bx - prev) > 0.4:        # moving sideways: face that way (up and down keep the last facing)
            self.jeep_face = 1 if bx > prev else -1
        self.jeep_prev_x = bx
        draw_jeepney(c, bx, by, bw, bh, col, PALETTE["on_color"], PALETTE["text"], getattr(self, "jeep_face", 1), tags="dyn")

        # ----- small labels next to the jeep and the depot -----
       # if fresh and tr.state in ("RUNNING", "LOW_BATTERY", "OBSTACLE_HOLD", "LINE_LOST") and tr.leg_start is not None:
       #     c.create_text(bx, by + bh + wr + 8, text="estimated", fill=PALETTE["muted"], font=F_SMALL, tags="dyn")
        if fresh and tr.para:
            c.create_text(bx, by - bh * 1.5 - 10, text="PARA", fill=PALETTE["map_pickup"], font=F_SMALL_BOLD, tags="dyn")
        if fresh and tr.depot and tr.lowbatt:
            x, y = P((200, 646))
            c.create_text(x, y, text="charging", fill=PALETTE["muted"], font=F_SMALL, tags="dyn")

        # ----- hover: a ring on the station (or a tooltip for the jeep) under the mouse -----
        self.draw_hover(now, fresh)

    # ---------- hover ----------
    def jeep_size(self):
        """Half the width and half the height of the jeepney on the map, in pixels."""
        return max(26 * self.text_factor, 30 * self.sc), max(14 * self.text_factor, 16 * self.sc)

    def request_counts(self, i):
        """(people waiting to be picked up, riders getting off) at station i."""
        pick = sum(1 for b in self.bookings if b.status == "WAITING" and b.pickup == i)
        drop = sum(1 for b in self.bookings if b.status == "BOARDED" and b.drop == i)
        return pick, drop

    def on_map_motion(self, event):
        """The mouse moved over the map: find the station or the jeep under it (if any) and redraw when that changes."""
        hit = None
        reach = self.stop_radius() + 8
        for i, (_name, pos) in enumerate(STOPS):
            x, y = self.w2c(pos)
            if math.hypot(event.x - x, event.y - y) <= reach:
                hit = ("stop", i)
                break
        if hit is None:
            bx, by = self.w2c(self.tr.position())
            bw, bh = self.jeep_size()
            if abs(event.x - bx) <= bw and -1.6 * bh <= event.y - by <= bh + 6:
                hit = ("jeep", 0)
        if hit != self.hover_item:
            self.hover_item = hit
            self.draw_dynamic(time.time())

    def on_map_leave(self, event=None):
        if self.hover_item is not None:
            self.hover_item = None
            self.draw_dynamic(time.time())

    def draw_hover(self, now, fresh):
        """Ring and tooltip for what the mouse is over. A station shows its name and who is waiting or getting off;
        the jeep shows its state and next stop."""
        if self.hover_item is None:
            return
        kind, i = self.hover_item
        c, tr = self.cv, self.tr
        if kind == "stop":
            x, y = self.w2c(STOPS[i][1])
            r = self.stop_radius()
            c.create_oval(x - r - 3, y - r - 3, x + r + 3, y + r + 3, outline=PALETTE["accent"], width=2, tags="dyn")
            pick, drop = self.request_counts(i)
            lines = [STOPS[i][0]]
            if pick:
                lines.append(f'{self.labels.text("legend_pickup")}: {pick}')
            if drop:
                lines.append(f'{self.labels.text("legend_drop")}: {drop}')
            if not (pick or drop):
                lines.append(self.labels.text("tip_no_requests"))
            self.draw_tooltip(x, y, r + 3, lines)
        else:
            bx, by = self.w2c(tr.position())
            lines = [self.state_text() if fresh else "Offline"]
            if fresh and tr.state != "PARKED" and not tr.depot:
                lines.append(f'{self.labels.text("next_stop")}: {STOPS[tr.next_stop][0]}')
            self.draw_tooltip(bx, by, self.jeep_size()[0], lines)

    def draw_tooltip(self, x, y, gap, lines):
        """A small white box with `lines`, beside the point (x, y) and kept inside the map."""
        c, pad = self.cv, 6
        text = c.create_text(0, 0, text="\n".join(lines), anchor="nw", fill=PALETTE["text"], font=F_SMALL,
                             justify="left", tags="dyn")
        x1, y1, x2, y2 = c.bbox(text)
        w, h = x2 - x1, y2 - y1
        cw, ch = c.winfo_width(), c.winfo_height()
        left = x + gap + 10 + pad                                  # to the right of the point ...
        if left + w + pad > cw - 4:
            left = x - gap - 10 - pad - w                          # ... or to the left when there is no room
        left = max(pad + 4, min(left, cw - w - pad - 4))
        top = max(pad + 4, min(y - h / 2, ch - h - pad - 4))
        c.move(text, left - x1, top - y1)
        box = c.create_polygon(rrect(left - pad, top - pad, left + w + pad, top + h + pad, 8), smooth=True,
                               fill=PALETTE["card"], outline=PALETTE["accent"], tags="dyn")
        c.tag_lower(box, text)                                     # the box goes behind its text

    # ---------- pickup and drop-off rings ----------
    def draw_requests(self, now):
        """Orange ring = someone waiting for a pickup, blue ring = a rider getting off there."""
        c, P = self.cv, self.w2c
        halo = False
        for i in range(N):
            pick, drop = self.request_counts(i)
            if not (pick or drop):
                continue
            x, y = P(STOPS[i][1])
            r = self.stop_radius() + 15 + 3 * math.sin(now * 4)      # pulses gently, outside the next-stop and last-station rings (radius + 6)
            col = PALETTE["map_pickup"] if pick else PALETTE["map_drop"]
            c.create_oval(x - r, y - r, x + r, y + r, fill=col, stipple="gray25", outline="", tags=("dyn", "halo"))   # soft filled halo
            c.create_oval(x - r, y - r, x + r, y + r, outline=col, width=3, tags="dyn")
            halo = True
            label = " + ".join(self.labels.text(k) for k, n in (("map_pickup", pick), ("map_drop", drop)) if n)
            ty = y - r - 8 if LABEL_POS[i][1] >= 0 else y + r + 8    # keep clear of the station name
            c.create_text(x, ty, text=label, fill=col, font=F_SMALL_BOLD, tags="dyn")
        if halo:
            c.tag_lower("halo", "stop")        # the halo goes under the station circles, so the numbers stay clear
