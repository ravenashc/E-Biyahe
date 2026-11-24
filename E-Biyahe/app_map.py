"""Drawing the map: blocks and landmarks, roads, stations, the map key, the jeepney and the planned-trip highlight.

This is one part of the App window: App (app.py) inherits MapMixin, so these methods are called as self.<name>()."""

import math
import time
import tkinter as tk

import theme
from helpers import fmt_dur, point_at, rrect
from jeepney import draw_jeepney
from map_data import (
    BLOCKS, BLOCK_STATION, CHARGING_POS, CROSSWALK_OFFSET, DEPOT_BOX, DEPOT_LABEL, DEPOT_ROAD, INTERSECTION_BOX, INTERSECTION_CENTER,
    LANDMARKS, LEG_PATHS, LOOP, N, SIDE_STREETS, STATE_COLOR, ROAD_W, STATION_TITLES, STOP_NUMBERS, STOPS, STREET_W, WORLD_H, WORLD_W,
)
from theme import F_SMALL, F_SMALL_BOLD, PAD, PALETTE


# ======================= MAP DRAWING =======================
class MapMixin:
    """Drawing the map: blocks and landmarks, roads, stations, the map key, the jeepney and the planned-trip highlight."""

    # ---------- map ----------
    def w2c(self, p):
        return (self.ox + p[0] * self.sc, self.oy + p[1] * self.sc)

    def road_px(self):
        """How wide the road is on screen, in pixels (it grows and shrinks with the map)."""
        return max(22, ROAD_W * self.sc)

    def stop_radius(self):
        """Radius in pixels of a station circle at the current map zoom (big enough to hold its number)."""
        return max(11 * self.text_factor, 15 * self.sc)

    def draw_static(self):
        """Draw the parts of the map that never move: blocks, roads, terminal, stations and the map key.
        Called again only when the map is resized."""
        c = self.cv
        c.delete("all")
        cw, ch = max(c.winfo_width(), 200), max(c.winfo_height(), 200)
        self.sc = min((cw - 24) / WORLD_W, (ch - 24) / WORLD_H)      # a small margin: the map fills its card
        self.ox, self.oy = (cw - WORLD_W * self.sc) / 2, (ch - WORLD_H * self.sc) / 2
        P, s = self.w2c, self.sc

        # ----- city blocks (green decoration) -----
        for x1, y1, x2, y2 in BLOCKS:
            a, b = P((x1, y1)), P((x2, y2))
            c.create_polygon(rrect(a[0], a[1], b[0], b[1], 14 * s), smooth=True, fill=PALETTE["map_block"], outline=PALETTE["map_block_edge"], tags="block")

        # ----- landmarks: a small drawing in each block, with the name of the station it belongs to below it -----
        for (x1, y1, x2, y2), (kind, _name), stop in zip(BLOCKS, LANDMARKS, BLOCK_STATION):
            self.draw_landmark(kind, STOPS[stop][0], (x1 + x2) / 2, (y1 + y2) / 2, (y2 - y1) / 2)

        # ----- connecting asphalt streets: visual crossroad only; the jeep route remains on the outer loop -----
        street_w = max(16, STREET_W * s)
        for p1, p2 in SIDE_STREETS:
            c.create_line(*P(p1), *P(p2), fill=PALETTE["map_street"], width=street_w, capstyle=tk.BUTT, tags="road")
            c.create_line(*P(p1), *P(p2), fill=PALETTE["map_road_line"],
                          width=max(1, 1.6 * s), dash=(max(4, int(12 * s)), max(3, int(9 * s))),
                          tags=("road", "street_centerline"))

        # ----- main loop road: soft gray with a dashed center line -----
        w = self.road_px()
        a, b = P(LOOP[:2]), P(LOOP[2:])
        loop = rrect(a[0], a[1], b[0], b[1], 45 * s)
        c.create_polygon(loop, smooth=True, fill="", outline=PALETTE["map_road"], width=w, tags="road")
        c.create_polygon(loop, smooth=True, fill="", outline=PALETTE["map_road_line"], width=2, dash=(10, 10), tags="road")

        # ----- central four-way intersection (visual only; no route or station changes) -----
        self.draw_intersection()

        # ----- terminal: road, box and label (the label sits beside the box so a parked jeep does not cover it) -----
        c.create_line(*P(DEPOT_ROAD[0]), *P(DEPOT_ROAD[1]), fill=PALETTE["map_road"], width=w, tags="road")
        a, b = P(DEPOT_BOX[:2]), P(DEPOT_BOX[2:])
        c.create_rectangle(a[0], a[1], b[0], b[1], fill=PALETTE["map_depot_fill"], outline=PALETTE["map_depot_edge"], tags="road")
        x, y = P(DEPOT_LABEL)
        c.create_text(x, y, text="Terminal", anchor="e", fill=PALETTE["text"], font=(theme.FONT_FAMILY, self.map_pt(8 * s * 1.6)), tags="road")

        # ----- direction arrows (white on the road, one per leg) -----
        for path in LEG_PATHS:
            p1, p2 = point_at(path, 0.47), point_at(path, 0.53)
            c.create_line(*P(p1), *P(p2), arrow=tk.LAST, arrowshape=(14, 16, 7), fill=PALETTE["on_color"], width=3, tags=("road", "arrow"))

        # ----- stations: a numbered circle (the name is written in the block, under its landmark) -----
        r = self.stop_radius()
        for i, (_name, pos) in enumerate(STOPS):
            x, y = P(pos)
            c.create_oval(x - r, y - r, x + r, y + r, fill=PALETTE["card"], outline=PALETTE["accent"], width=3, tags="stop")
            c.create_text(x, y, text=str(STOP_NUMBERS[i]), fill=PALETTE["accent"], font=(theme.FONT_FAMILY, self.map_pt(8 * s * 1.3), "bold"), tags="stop")

        # ----- map key and the moving layer -----
        self.draw_legend(cw, ch, s)
        self.draw_dynamic(time.time())

    def draw_intersection(self):
        """Draw the central four-way junction: zebra crossings, stop bars, yellow box and signals.
        All elements are decorative; the jeep continues to follow LEG_PATHS on the outer loop."""
        c, s = self.cv, self.sc
        cx, cy = self.w2c(INTERSECTION_CENTER)
        road_half = max(8.0, STREET_W * s / 2)
        offset = CROSSWALK_OFFSET * s

        # Seven upright zebra bars on every approach. Each stripe is vertical on the map,
        # with even spacing and a little asphalt margin around the crossing.
        count = 7
        stripe_width = max(1.0, (2 * road_half - 2) / (count + (count - 1) * 0.55))
        stripe_gap = stripe_width * 0.55
        band_depth = count * stripe_width + (count - 1) * stripe_gap

        def vertical_approach(y):
            # North/south approaches: upright bars sit side-by-side across the road.
            start = cx - band_depth / 2
            for i in range(count):
                left = start + i * (stripe_width + stripe_gap)
                c.create_rectangle(left, y - band_depth / 2, left + stripe_width, y + band_depth / 2,
                                   fill=PALETTE["map_crosswalk"], outline="", tags=("intersection", "crosswalk"))

        def horizontal_approach(x):
            # East/west approaches: horizontal bars span the road, stacked vertically.
            start = cy - band_depth / 2
            for i in range(count):
                top = start + i * (stripe_width + stripe_gap)
                c.create_rectangle(x - road_half + 1, top, x + road_half - 1, top + stripe_width,
                                   fill=PALETTE["map_crosswalk"], outline="", tags=("intersection", "crosswalk"))

        vertical_approach(cy - offset)      # north approach
        vertical_approach(cy + offset)      # south approach
        horizontal_approach(cx - offset)    # west approach
        horizontal_approach(cx + offset)    # east approach

        # Stop bars just before each pedestrian crossing.
        stop_gap = 4 * s
        bar_width = max(1.2, 2 * s)
        for y in (cy - offset - band_depth / 2 - stop_gap, cy + offset + band_depth / 2 + stop_gap):
            c.create_line(cx - road_half + 1, y, cx + road_half - 1, y,
                          fill=PALETTE["map_crosswalk"], width=bar_width, tags=("intersection", "stop_bar"))
        for x in (cx - offset - band_depth / 2 - stop_gap, cx + offset + band_depth / 2 + stop_gap):
            c.create_line(x, cy - road_half + 1, x, cy + road_half - 1,
                          fill=PALETTE["map_crosswalk"], width=bar_width, tags=("intersection", "stop_bar"))

        # Yellow box junction with a diagonal cross, kept within the road's central crossing area.
        half_box = INTERSECTION_BOX * s / 2
        yellow = PALETTE["map_box"]
        mark_width = max(2.2, 4.5 * s)
        c.create_rectangle(cx - half_box, cy - half_box, cx + half_box, cy + half_box,
                           fill="", outline=yellow, width=mark_width, tags=("intersection", "yellow_box"))
        c.create_line(cx - half_box, cy - half_box, cx + half_box, cy + half_box,
                      fill=yellow, width=mark_width, capstyle=tk.ROUND, tags=("intersection", "yellow_box"))
        c.create_line(cx - half_box, cy + half_box, cx + half_box, cy - half_box,
                      fill=yellow, width=mark_width, capstyle=tk.ROUND, tags=("intersection", "yellow_box"))

        # Four small traffic-signal heads at the corners of the central crossing.
        body = PALETTE["text"]
        light_size = max(1.8, 3.2 * s)
        body_w, body_h = max(5.5, 10 * s), max(10, 19 * s)
        corner_offset = half_box + max(2 * s, body_w * 0.6)
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            x, y = cx + sx * corner_offset, cy + sy * corner_offset
            c.create_rectangle(x - body_w / 2, y - body_h / 2, x + body_w / 2, y + body_h / 2,
                               fill=body, outline=PALETTE["map_crosswalk"], width=max(1, s),
                               tags=("intersection", "signal"))
            for j, color in enumerate((PALETTE["danger"], PALETTE["warn"], PALETTE["ok"])):
                ly = y - body_h / 2 + (j + 0.5) * body_h / 3
                c.create_oval(x - light_size / 2, ly - light_size / 2, x + light_size / 2, ly + light_size / 2,
                              fill=color, outline="", tags=("intersection", "signal"))

    def draw_landmark(self, kind, name, cx, cy, half_h):
        """A small drawing (market, construction site, school or park) with the name of its station below it, in the middle of a block.
        (cx, cy) is the block's centre and half_h its half height, both in map points.
        A small map gets a smaller drawing, and no name when space is short."""
        c, s = self.cv, self.sc
        x, y = self.w2c((cx, cy))
        name_h = 20 * self.text_factor                 # room for the station name under the drawing
        ground = min(y + 0.55 * half_h * s, y + half_h * s - name_h - 4)    # the bottom of the drawing; its name goes below it
        avail = ground - (y - half_h * s) - 8          # pixels from that line up to the top edge of the block (8 px margin)
        k = max(5.0, min(30 * s, (avail - 2) / 2.6))   # one drawing unit in pixels
        c.create_text(x, ground + 6, text=name, anchor="n", fill=PALETTE["text"],
                      font=(theme.FONT_FAMILY, self.map_pt(8 * s * 1.45), "bold"), tags="landmark")
        wall, roof, line, glass = PALETTE["map_lm_wall"], PALETTE["map_lm_roof"], PALETTE["map_lm_line"], PALETTE["map_lm_glass"]

        def rect(x1, y1, x2, y2, fill):                # coordinates are in units of k from the ground line, y up is negative
            c.create_rectangle(x + x1 * k, ground + y1 * k, x + x2 * k, ground + y2 * k, fill=fill, outline=line, tags="landmark")

        def poly(pts, fill):
            c.create_polygon([v for px, py in pts for v in (x + px * k, ground + py * k)], fill=fill, outline=line, tags="landmark")

        def seg(x1, y1, x2, y2):
            c.create_line(x + x1 * k, ground + y1 * k, x + x2 * k, ground + y2 * k, fill=line, width=2, tags="landmark")

        if kind == "park":
            # THIRSTOP/BR Park, inspired by the user's physical model:
            # a raised rectangular planter with wood-toned fascia, green side strips,
            # a paved centre, a decorative tree, front steps and a row of bollards.
            park_wood = "#C97945"
            park_wood_light = "#E39A62"
            park_rim = "#E8E9E3"
            park_concrete = "#89969C"
            park_concrete_light = "#BFC9CC"
            park_concrete_dark = "#59666D"
            park_grass = "#5D9B4A"
            park_grass_light = "#83B65D"
            park_grass_dark = "#39783D"
            park_metal = "#26323A"
            park_silver = "#AEB8BC"
            park_tree = "#287A58"
            park_tree_light = "#39986A"
            park_blue = "#4F9ED1"
            park_gold = "#F3C94C"

            def park_poly(points, fill, outline=park_concrete_dark, weight=0.035):
                coords = [v for px, py in points for v in (x + px * k, ground + py * k)]
                c.create_polygon(coords, fill=fill, outline=outline,
                                 width=max(1.0, weight * k), joinstyle=tk.ROUND, tags="landmark")

            def park_line(x1, y1, x2, y2, color, weight=0.035, dash=None):
                opts = {"fill": color, "width": max(1.0, weight * k),
                        "capstyle": tk.ROUND, "tags": "landmark"}
                if dash:
                    opts["dash"] = dash
                c.create_line(x + x1 * k, ground + y1 * k,
                              x + x2 * k, ground + y2 * k, **opts)

            def park_oval(x1, y1, x2, y2, fill, outline=park_concrete_dark, weight=0.025):
                c.create_oval(x + x1 * k, ground + y1 * k,
                              x + x2 * k, ground + y2 * k,
                              fill=fill, outline=outline,
                              width=max(1.0, weight * k), tags="landmark")

            # Raised planter shadow beneath the base; no visible support pillars.
            park_poly([(-2.12, -0.48), (1.88, -0.48), (2.24, -0.68), (-1.77, -0.68)],
                      "#39454B", "#39454B", 0.02)

            # Orange-brown front and side fascia, like the wooden raised frame.
            park_poly([(-2.18, -1.78), (-1.78, -0.78), (-1.78, -0.55), (-2.18, -1.53)],
                      park_wood, "#96532F", 0.045)
            park_poly([(1.78, -1.78), (2.18, -0.78), (2.18, -0.55), (1.78, -1.53)],
                      park_wood, "#96532F", 0.045)
            park_poly([(-1.78, -0.78), (2.18, -0.78), (2.18, -0.55), (-1.78, -0.55)],
                      park_wood, "#96532F", 0.045)
            park_line(-1.78, -0.72, 2.18, -0.72, park_wood_light, 0.035)

            # Raised pale rim; the inner face is a shallow perspective rectangle.
            park_poly([(-2.18, -1.78), (1.78, -1.78), (2.18, -0.78), (-1.78, -0.78)],
                      park_rim, "#AAB4B7", 0.045)
            park_poly([(-1.98, -1.64), (1.66, -1.64), (2.00, -0.91), (-1.70, -0.91)],
                      "#D4DADD", "#B4BEC2", 0.025)

            # Green planted strips along both long sides and the back edge.
            park_poly([(-1.91, -1.58), (-1.55, -1.58), (-1.27, -0.98), (-1.62, -0.98)],
                      park_grass, park_grass_dark, 0.02)
            park_poly([(1.31, -1.58), (1.62, -1.58), (1.91, -0.98), (1.60, -0.98)],
                      park_grass, park_grass_dark, 0.02)
            park_poly([(-1.84, -1.62), (1.59, -1.62), (1.64, -1.49), (-1.78, -1.49)],
                      park_grass_light, park_grass_dark, 0.02)

            # Grass texture: short blades and small shrubs along the planter strips.
            for gx in (-1.83, -1.73, -1.63, -1.53, 1.38, 1.48, 1.58, 1.68):
                park_line(gx, -1.48, gx - 0.035, -1.37, park_grass_light, 0.035)
                park_line(gx + 0.025, -1.34, gx + 0.055, -1.25, park_grass_dark, 0.03)
            for gx in (-1.55, -1.15, -0.70, -0.25, 0.20, 0.65, 1.10, 1.48):
                park_oval(gx - 0.035, -1.60, gx + 0.035, -1.53, park_grass_light, park_grass, 0.01)

            # Central paved feature and shallow entrance steps.
            park_poly([(-1.25, -1.48), (1.22, -1.48), (1.51, -1.00), (-1.02, -1.00)],
                      park_concrete, park_concrete_dark, 0.025)
            park_poly([(-0.70, -0.99), (1.05, -0.99), (1.18, -0.89), (-0.57, -0.89)],
                      park_concrete_light, park_concrete_dark, 0.02)
            for sy in (-0.95, -0.88, -0.81):
                park_line(-0.62, sy, 1.13, sy, park_silver, 0.025)

            # Small ornamental tree with a round base and blue/gold decorations.
            park_oval(-0.10, -1.16, 0.52, -0.98, park_concrete_light, park_concrete_dark, 0.025)
            park_line(0.21, -1.12, 0.21, -1.54, "#76583C", 0.085)
            park_poly([(0.21, -1.90), (-0.18, -1.48), (0.60, -1.48)], park_tree, park_grass_dark, 0.025)
            park_poly([(0.21, -1.76), (-0.10, -1.40), (0.52, -1.40)], park_tree_light, park_grass_dark, 0.02)
            park_poly([(0.21, -1.62), (0.00, -1.34), (0.42, -1.34)], park_tree, park_grass_dark, 0.02)
            for tx, ty, tc in ((0.01, -1.49, park_blue), (0.40, -1.51, park_gold),
                               (0.12, -1.68, park_gold), (0.34, -1.77, park_blue),
                               (0.22, -1.39, "#E7E9E8")):
                park_oval(tx - 0.045, ty - 0.045, tx + 0.045, ty + 0.045, tc, park_rim, 0.018)
            park_oval(0.13, -1.94, 0.29, -1.86, park_gold, "#A27B29", 0.015)

            # Silver entrance apron in front of the planter and an evenly spaced row of black bollards.
            park_poly([(-1.88, -0.56), (2.15, -0.56), (2.30, -0.39), (-1.73, -0.39)],
                      park_silver, park_concrete_dark, 0.025)
            for bx in (-1.47, -1.05, -0.63, -0.21, 0.21, 0.63, 1.05, 1.47, 1.89):
                park_line(bx, -0.49, bx, -0.70, park_metal, 0.075)
                park_oval(bx - 0.045, -0.53, bx + 0.045, -0.46, park_metal, "#11191E", 0.018)
                park_line(bx - 0.018, -0.50, bx - 0.018, -0.57, park_silver, 0.012)

        elif kind == "school":
            # LILIM station, front elevation based on the user's physical model:
            # a tall office block with a blue louvered roof and a row of eight blue windows,
            # a white segmented canopy on black posts, a peach/grey side block, three round
            # trees, two dark gate pillars with a swing gate, and a picket fence round a lawn.
            # Decorative only; it does not affect routing.
            lawn = "#3FAE49"
            lawn_edge = "#2C7F36"
            peach = "#F2BC93"
            peach_edge = "#B8845F"
            tan = "#C4B38D"
            grey = "#B1B5B7"
            grey_edge = "#6F777B"
            navy = "#1B3F78"
            win = "#1D5C8D"
            louver = "#1D82B2"
            canopy = "#E4F0F3"
            canopy_edge = "#7A8E96"
            post = "#161B20"
            pillar = "#4B4F53"
            tree = "#3E9F42"
            tree_edge = "#2B6E33"
            fence = "#5A6068"

            def lm_rect(x1, y1, x2, y2, fill, outline=line, weight=0.03):
                c.create_rectangle(x + x1 * k, ground + y1 * k, x + x2 * k, ground + y2 * k,
                                   fill=fill, outline=outline, width=max(1.0, weight * k), tags="landmark")

            def lm_poly(points, fill, outline=line, weight=0.03):
                coords = [v for px, py in points for v in (x + px * k, ground + py * k)]
                c.create_polygon(coords, fill=fill, outline=outline, width=max(1.0, weight * k),
                                 joinstyle=tk.ROUND, tags="landmark")

            def lm_line(x1, y1, x2, y2, color, weight=0.03):
                c.create_line(x + x1 * k, ground + y1 * k, x + x2 * k, ground + y2 * k,
                              fill=color, width=max(1.0, weight * k), capstyle=tk.ROUND, tags="landmark")

            def lm_oval(x1, y1, x2, y2, fill, outline=tree_edge, weight=0.03):
                c.create_oval(x + x1 * k, ground + y1 * k, x + x2 * k, ground + y2 * k,
                              fill=fill, outline=outline, width=max(1.0, weight * k), tags="landmark")

            # Green lawn the whole station stands on.
            lm_rect(-2.45, -2.75, 2.45, -0.02, lawn, lawn_edge, 0.04)

            # Main office block (left, behind the canopy): blue louvered roof, tan band, 8 windows.
            lm_rect(-2.05, -2.70, 0.45, -2.15, peach, peach_edge, 0.03)
            lm_rect(-1.95, -2.64, 0.35, -2.21, navy, navy, 0.02)
            for i in range(6):
                ly = -2.60 + i * 0.07
                lm_line(-1.92, ly, 0.32, ly, louver, 0.04)
            lm_line(-0.80, -2.64, -0.80, -2.21, navy, 0.05)
            lm_rect(-2.05, -2.15, 0.45, -1.80, tan, peach_edge, 0.03)
            for i in range(8):
                wx = -1.98 + i * 0.30
                lm_rect(wx, -1.80, wx + 0.22, -1.22, win, navy, 0.02)

            # Second block (right): peach top, grey lower face.
            lm_rect(0.72, -2.70, 1.72, -1.70, peach, peach_edge, 0.03)
            lm_rect(0.72, -1.70, 1.72, -0.45, grey, grey_edge, 0.03)
            lm_rect(0.72, -1.74, 1.72, -1.66, peach_edge, peach_edge, 0.01)
            lm_oval(0.64, -1.48, 0.78, -1.34, "#D94B40", "#8E2B25", 0.02)    # red lamp on its edge

            # White segmented canopy on black posts, in front of the office block.
            for px in (-2.00, 0.38):
                lm_rect(px, -1.35, px + 0.06, -0.55, post, post, 0.01)
            lm_rect(-2.05, -1.55, 0.45, -0.85, canopy, canopy_edge, 0.03)
            for i in range(1, 4):
                ly = -1.55 + i * 0.175
                lm_line(-2.05, ly, 0.45, ly, canopy_edge, 0.02)
            lm_rect(-2.05, -1.55, 0.45, -1.46, "#F6F8F8", canopy_edge, 0.02)

            # Three round trees stacked down the left edge.
            for ty in (-1.72, -1.28, -0.84):
                lm_oval(-2.40, ty - 0.24, -1.92, ty + 0.24, tree, tree_edge, 0.03)
                lm_oval(-2.30, ty - 0.16, -2.08, ty - 0.02, "#63BE5A", "#63BE5A", 0.01)

            # Gate: two dark pillars, a grey kiosk panel and an angled swing gate between them.
            lm_rect(-1.55, -0.62, -1.30, -0.08, pillar, post, 0.03)
            lm_rect(-1.30, -0.50, -0.80, -0.14, "#AEB2B4", grey_edge, 0.02)
            lm_poly([(-0.55, -0.55), (-0.18, -0.42), (-0.18, -0.12), (-0.55, -0.25)], "#9AA0A3", grey_edge, 0.02)
            lm_rect(-0.10, -0.62, 0.15, -0.08, pillar, post, 0.03)
            # Small yellow lamps along the driveway.
            for ly in (-1.00, -0.78, -0.56):
                lm_oval(0.30, ly - 0.035, 0.38, ly + 0.035, "#F3C94C", "#A27B29", 0.015)

            # Picket fence along the front and both sides of the lawn.
            for fx in [-2.40 + i * 0.12 for i in range(41)]:
                lm_line(fx, -0.17, fx, -0.02, fence, 0.03)
            lm_line(-2.42, -0.14, 2.42, -0.14, fence, 0.025)
            for fy in [-2.72 + i * 0.13 for i in range(21)]:
                lm_line(-2.44, fy, -2.36, fy, fence, 0.03)
                lm_line(2.36, fy, 2.44, fy, fence, 0.03)

        elif kind == "market":
            # Front-elevation parking station based on the user's physical model.
            # The attached multi-storey building is on the LEFT; the open two-level
            # garage spans the RIGHT. This is decorative and does not affect routing.
            asphalt = "#11171D"
            asphalt_edge = "#090D12"
            concrete = "#707C84"
            concrete_light = "#B5BEC4"
            concrete_mid = "#929DA4"
            concrete_dark = "#465159"
            facade = "#C8C5BD"
            facade_warm = "#B8B0A3"
            facade_band = "#D9D7D0"
            glass = "#5598B9"
            glass_glint = "#A9D6E6"
            bay_line = "#E6E5DC"
            yellow = "#F4D51C"
            hedge = "#6E963E"
            booth_wall = "#9DA8AF"

            def park_rect(x1, y1, x2, y2, fill, outline=asphalt_edge, weight=0.035):
                c.create_rectangle(x + x1 * k, ground + y1 * k, x + x2 * k, ground + y2 * k,
                                   fill=fill, outline=outline, width=max(1.0, weight * k), tags="landmark")

            def park_poly(points, fill, outline=asphalt_edge, weight=0.04):
                coords = [v for px, py in points for v in (x + px * k, ground + py * k)]
                c.create_polygon(coords, fill=fill, outline=outline, width=max(1.0, weight * k),
                                 joinstyle=tk.ROUND, tags="landmark")

            def park_line(x1, y1, x2, y2, color, weight=0.035, dash=None):
                opts = {"fill": color, "width": max(1.0, weight * k), "capstyle": tk.ROUND, "tags": "landmark"}
                if dash:
                    opts["dash"] = dash
                c.create_line(x + x1 * k, ground + y1 * k, x + x2 * k, ground + y2 * k, **opts)

            # LEFT: attached three-storey building, shown from the front.
            park_rect(-2.88, -3.05, -1.42, -0.18, facade, concrete_dark, 0.045)
            # Alternating wall tones and wide horizontal floor bands.
            park_rect(-2.84, -2.94, -1.46, -2.18, facade, concrete_dark, 0.025)
            park_rect(-2.84, -1.96, -1.46, -1.20, facade_warm, concrete_dark, 0.025)
            park_rect(-2.84, -0.98, -1.46, -0.27, facade, concrete_dark, 0.025)
            park_rect(-2.94, -3.14, -1.36, -2.94, facade_band, concrete_dark, 0.035)
            park_rect(-2.94, -2.20, -1.36, -2.02, facade_band, concrete_dark, 0.035)
            park_rect(-2.94, -1.22, -1.36, -1.04, facade_band, concrete_dark, 0.035)
            park_rect(-2.94, -0.30, -1.36, -0.14, facade_band, concrete_dark, 0.035)

            # Blue windows on all three floors, with visible pale frames and glazing highlights.
            for wy in (-2.78, -1.80, -0.83):
                for wx in (-2.70, -2.24, -1.78):
                    park_rect(wx, wy, wx + 0.27, wy + 0.39, concrete_dark, concrete_dark, 0.025)
                    park_rect(wx + 0.035, wy + 0.035, wx + 0.235, wy + 0.35, glass, glass, 0.015)
                    park_line(wx + 0.06, wy + 0.10, wx + 0.21, wy + 0.10, glass_glint, 0.018)

            # Ground-floor doorway and a narrow planted strip like the model's frontage.
            park_rect(-2.23, -0.82, -1.91, -0.31, concrete_dark, concrete_dark, 0.025)
            park_rect(-2.19, -0.78, -1.95, -0.34, concrete_mid, concrete_dark, 0.015)
            park_rect(-2.88, -0.23, -1.42, -0.17, hedge, hedge, 0.01)
            for hx in (-2.78, -2.63, -2.48, -1.72, -1.57):
                park_poly([(hx - 0.07, -0.19), (hx, -0.11), (hx + 0.07, -0.19)], hedge, hedge, 0.01)

            # RIGHT: dark open-sided two-storey parking garage, seen straight-on.
            # Recessed black interior establishes the two visible parking decks.
            park_rect(-1.33, -2.66, 2.88, -0.38, asphalt, asphalt_edge, 0.045)
            # Roof slab / top overhang.
            park_rect(-1.48, -2.91, 2.98, -2.66, asphalt, concrete_dark, 0.045)
            park_line(-1.43, -2.88, 2.91, -2.88, concrete_mid, 0.025)

            # Upper-deck parking bay markings set behind the front structure.
            for px in (-1.12, -0.72, -0.30, 0.12, 0.54, 0.96, 1.38, 1.80, 2.22, 2.60):
                park_line(px, -2.54, px, -1.92, bay_line, 0.027, (2, 2))
            park_line(-1.18, -1.92, 2.72, -1.92, concrete_mid, 0.025)

            # Lower-level parking bays and dashed markings.
            for px in (-1.12, -0.66, -0.20, 0.26, 0.72, 1.18, 1.64, 2.10, 2.56):
                park_line(px, -1.35, px, -0.78, bay_line, 0.027, (2, 2))
            park_line(-1.18, -0.78, 2.72, -0.78, concrete_mid, 0.025)

            # Sloping internal ramp on the right, matching the prominent diagonal in the model.
            park_poly([(0.64, -0.43), (1.12, -0.43), (2.66, -1.57), (2.22, -1.57)], concrete_dark, asphalt_edge, 0.05)
            park_line(0.82, -0.48, 2.36, -1.55, concrete_light, 0.055)
            park_line(1.00, -0.50, 2.52, -1.55, asphalt_edge, 0.025)
            # Ramp edge / guard strip.
            park_line(2.34, -1.51, 2.72, -1.51, concrete_mid, 0.045)

            # Main front beams and slab edges create the strong horizontal façade lines.
            park_rect(-1.44, -1.72, 2.96, -1.50, concrete, concrete_dark, 0.045)
            park_rect(-1.48, -0.58, 2.98, -0.36, concrete_dark, asphalt_edge, 0.04)
            park_rect(-1.46, -0.43, 2.96, -0.34, concrete, concrete_dark, 0.025)

            # Exposed square columns between the open parking bays on both levels.
            for px in (-1.30, -0.30, 0.76, 1.82, 2.82):
                park_rect(px - 0.075, -2.66, px + 0.075, -1.72, concrete_light, concrete_dark, 0.035)
                park_rect(px - 0.075, -1.50, px + 0.075, -0.58, concrete_light, concrete_dark, 0.035)

            # Front fascia / teal foundation strip visible along the bottom of the model.
            park_rect(-1.48, -0.17, 2.98, -0.06, "#398E9B", "#246773", 0.025)

            # Small front entrance booth in the lower level, offset to the right of the building.
            park_rect(-0.12, -0.61, 0.92, -0.15, booth_wall, concrete_dark, 0.035)
            park_rect(-0.20, -0.66, 1.00, -0.57, concrete_light, concrete_dark, 0.025)
            park_rect(0.08, -0.49, 0.72, -0.25, asphalt, concrete_dark, 0.025)
            park_rect(0.16, -0.46, 0.42, -0.29, glass, concrete_dark, 0.02)
            park_rect(0.49, -0.46, 0.65, -0.29, concrete_dark, concrete_dark, 0.015)

            # Yellow one-way arrows on the right-side driveway.
            park_line(2.55, -0.70, 2.55, -0.46, yellow, 0.075)
            park_poly([(2.55, -0.35), (2.42, -0.55), (2.68, -0.55)], yellow, yellow, 0.015)
            park_line(2.55, -1.15, 2.55, -1.37, yellow, 0.075)
            park_poly([(2.55, -1.48), (2.42, -1.28), (2.68, -1.28)], yellow, yellow, 0.015)

            # Vehicle barrier gate, physically mounted to the small ticket booth.
            # The motor housing touches the booth's lower-right wall, so the arm
            # visibly grows out of the booth instead of standing on a separate island.
            gate_yellow = "#F4CF24"
            gate_black = "#20262C"
            gate_red = "#D94B40"

            # Reinforced side mount: overlaps the booth corner and reaches down to the arm pivot.
            park_rect(0.78, -0.94, 1.10, -0.56, concrete_dark, asphalt_edge, 0.04)
            park_rect(0.82, -0.91, 1.075, -0.60, concrete_light, concrete_dark, 0.025)
            park_rect(0.845, -0.875, 1.05, -0.765, asphalt_edge, asphalt_edge, 0.015)
            # Red/green status lamps are placed on the booth-mounted control head.
            c.create_oval(x + 0.855 * k, ground - 0.86 * k,
                          x + 0.905 * k, ground - 0.81 * k,
                          fill=gate_red, outline=gate_black, width=max(1, k * 0.025), tags="landmark")
            c.create_oval(x + 0.985 * k, ground - 0.86 * k,
                          x + 1.035 * k, ground - 0.81 * k,
                          fill="#55A65A", outline=gate_black, width=max(1, k * 0.025), tags="landmark")
            # A short visible hinge links the control head to the striped barrier arm.
            park_rect(1.015, -0.975, 1.15, -0.865, concrete_dark, gate_black, 0.03)
            c.create_oval(x + 1.055 * k, ground - 0.965 * k,
                          x + 1.145 * k, ground - 0.875 * k,
                          fill=gate_yellow, outline=gate_black, width=max(1, k * 0.03), tags="landmark")

            # Barrier arm: black beam with alternating yellow reflective stripes,
            # extending from the booth-mounted hinge across the vehicle lane.
            park_rect(1.10, -0.995, 2.94, -0.895, gate_black, asphalt_edge, 0.03)
            for gx in (1.19, 1.43, 1.67, 1.91, 2.15, 2.39, 2.63, 2.77):
                park_poly([(gx, -0.995), (gx + 0.105, -0.995),
                           (gx + 0.205, -0.895), (gx + 0.100, -0.895)],
                          gate_yellow, gate_yellow, 0.012)
            # Yellow end cap and a receiver post at the far side of the driveway.
            park_rect(2.89, -1.035, 2.98, -0.855, gate_yellow, gate_black, 0.025)
            park_rect(2.91, -1.20, 2.98, -0.80, concrete_dark, asphalt_edge, 0.035)
            park_rect(2.925, -1.16, 2.965, -0.91, gate_black, gate_black, 0.015)

        elif kind == "hall":
            # A miniature active construction site, based on the supplied model photo.
            # Keep the whole scene inside this block; it is decorative and does not affect routing.
            soil = PALETTE["map_site_soil"]
            gravel = PALETTE["map_site_gravel"]
            concrete = PALETTE["map_site_concrete"]
            steel = PALETTE["map_site_steel"]
            fence = PALETTE["map_site_fence"]
            yellow = PALETTE["map_site_yellow"]
            machine = PALETTE["map_site_machine"]

            def site_line(x1, y1, x2, y2, color, weight=0.07):
                c.create_line(x + x1 * k, ground + y1 * k, x + x2 * k, ground + y2 * k,
                              fill=color, width=max(1.0, weight * k), tags="landmark")

            def site_oval(x1, y1, x2, y2, fill):
                c.create_oval(x + x1 * k, ground + y1 * k, x + x2 * k, ground + y2 * k,
                              fill=fill, outline=line, width=max(1, 0.025 * k), tags="landmark")

            # Dark earth pad and a pale gravel pile, like the open yard in the reference.
            rect(-2.28, -1.82, 2.28, -0.05, soil)
            poly([(-1.0, -0.35), (-0.42, -0.78), (0.25, -0.72), (0.66, -0.35), (0.18, -0.18), (-0.65, -0.16)], gravel)
            for px, py, radius in ((-0.72, -0.55, 0.055), (-0.38, -0.66, 0.045),
                                   (0.12, -0.52, 0.05), (0.52, -0.42, 0.045),
                                   (-0.2, -0.3, 0.035), (0.82, -1.05, 0.04),
                                   (-0.72, -1.05, 0.04), (1.1, -0.38, 0.035)):
                site_oval(px - radius, py - radius, px + radius, py + radius, concrete)

            # Unfinished concrete frame at the left: slab, columns, beams and exposed rebar.
            rect(-2.08, -1.55, -0.88, -0.28, concrete)
            rect(-2.12, -1.62, -0.84, -1.48, steel)
            for px in (-2.0, -1.58, -1.03):
                rect(px - 0.075, -1.55, px + 0.075, -0.18, steel)
                site_line(px - 0.025, -1.58, px - 0.025, -2.05, yellow, 0.035)
                site_line(px + 0.025, -1.58, px + 0.025, -2.05, yellow, 0.035)
            rect(-2.1, -1.34, -0.82, -1.22, concrete)
            rect(-2.1, -0.42, -0.82, -0.30, concrete)
            for px in (-1.9, -1.55, -1.2, -0.9):
                site_line(px, -1.48, px + 0.22, -1.26, steel, 0.035)

            # Small blue-roofed site office on the right, echoing the shed in the photo.
            rect(1.48, -1.22, 2.12, -0.43, steel)
            rect(1.58, -1.03, 2.02, -0.47, concrete)
            rect(1.77, -0.92, 1.96, -0.62, PALETTE["map_lm_line"])
            poly([(1.35, -1.18), (1.78, -1.58), (2.25, -1.18)], roof)
            for i in range(6):
                px = 1.47 + i * 0.13
                site_line(px, -1.2, px + 0.18, -1.52, PALETTE["map_lm_glass"], 0.025)

            # A small yellow dump truck and excavator working in the yard.
            site_oval(0.38, -0.70, 0.68, -0.40, PALETTE["text"])
            site_oval(1.12, -0.70, 1.42, -0.40, PALETTE["text"])
            poly([(0.34, -0.48), (0.56, -0.92), (1.17, -0.92), (1.38, -0.62), (1.32, -0.48)], machine)
            poly([(0.45, -0.5), (0.64, -0.78), (1.23, -0.78), (1.30, -0.5)], yellow)
            rect(0.94, -0.82, 1.23, -0.55, PALETTE["map_lm_glass"])
            site_line(0.48, -0.93, 1.30, -0.93, steel, 0.06)
            # Excavator arm and bucket beside the truck.
            site_line(-0.05, -0.72, 0.20, -1.00, yellow, 0.14)
            site_line(0.20, -1.00, 0.50, -0.88, yellow, 0.12)
            poly([(0.47, -0.89), (0.67, -0.88), (0.60, -1.03), (0.43, -1.02)], steel)
            site_oval(-0.18, -0.78, 0.12, -0.48, PALETTE["text"])
            rect(-0.13, -0.70, 0.08, -0.49, machine)

            # Blue corrugated perimeter fence along the front and right edges.
            rect(-2.28, -0.25, 2.28, -0.04, fence)
            for i in range(29):
                px = -2.24 + i * 0.16
                site_line(px, -0.24, px, -0.055, PALETTE["map_lm_glass"], 0.018)
            site_line(2.24, -1.82, 2.24, -0.12, fence, 0.18)
            for py in (-1.68, -1.42, -1.16, -0.9, -0.64, -0.38):
                site_line(2.16, py, 2.27, py, PALETTE["map_lm_glass"], 0.025)

            # Servo-motor-powered industrial robot arm, replacing the tower-crane placeholder.
            # The articulated orange arm has a rotating base, shoulder/elbow/wrist servos and a gripper.
            servo_orange = PALETTE["map_site_servo_orange"]
            servo_dark = PALETTE["map_site_servo_dark"]
            servo_black = PALETTE["map_site_servo_black"]
            servo_silver = PALETTE["map_site_servo_silver"]

            def arm_line(x1, y1, x2, y2, color, weight):
                c.create_line(x + x1 * k, ground + y1 * k, x + x2 * k, ground + y2 * k,
                              fill=color, width=max(2.0, weight * k), capstyle=tk.ROUND,
                              joinstyle=tk.ROUND, tags="landmark")

            def arm_oval(cx, cy, rx, ry, fill, outline=servo_black, edge=0.055):
                c.create_oval(x + (cx - rx) * k, ground + (cy - ry) * k,
                              x + (cx + rx) * k, ground + (cy + ry) * k,
                              fill=fill, outline=outline, width=max(1.0, edge * k), tags="landmark")

            def arm_poly(points, fill):
                coords = [v for px, py in points for v in (x + px * k, ground + py * k)]
                c.create_polygon(coords, fill=fill, outline=servo_black,
                                 width=max(1.0, 0.035 * k), joinstyle=tk.ROUND, tags="landmark")

            def arm_link(x1, y1, x2, y2, weight=0.48):
                # Dark casing edge under the orange servo housing gives the arm a solid molded shape.
                arm_line(x1, y1, x2, y2, servo_black, weight + 0.10)
                arm_line(x1, y1, x2, y2, servo_orange, weight)

            # Heavy black mounting plate with visible fasteners and a compact rotating pedestal.
            arm_poly([(-0.64, -0.16), (-0.48, -0.34), (0.50, -0.34), (0.68, -0.16)], servo_black)
            for bx in (-0.48, -0.18, 0.18, 0.48):
                arm_oval(bx, -0.245, 0.035, 0.035, servo_silver, servo_black, 0.018)
            arm_poly([(-0.39, -0.34), (-0.28, -0.59), (0.28, -0.59), (0.39, -0.34)], servo_dark)
            arm_oval(0.0, -0.53, 0.34, 0.105, servo_black, servo_black, 0.035)
            arm_oval(0.0, -0.51, 0.27, 0.075, servo_silver, servo_dark, 0.025)

            # Shoulder servo: broad orange motor housing with a black circular end cap.
            arm_oval(0.10, -0.78, 0.43, 0.39, servo_dark, servo_black, 0.07)
            arm_oval(0.10, -0.79, 0.37, 0.33, servo_orange, servo_orange, 0.035)
            arm_oval(0.18, -0.79, 0.205, 0.205, servo_black, servo_black, 0.035)
            arm_oval(0.18, -0.79, 0.145, 0.145, servo_dark, servo_silver, 0.025)

            # Main arm segment rising diagonally to the elbow, with a sculpted shoulder transition.
            arm_link(0.02, -0.96, -0.63, -1.72, 0.54)
            arm_poly([(-0.27, -1.20), (-0.56, -1.64), (-0.78, -1.68), (-0.49, -1.18)], servo_orange)
            # Elbow drive housing and its dark centre cap.
            arm_oval(-0.65, -1.73, 0.32, 0.30, servo_dark, servo_black, 0.06)
            arm_oval(-0.65, -1.73, 0.265, 0.245, servo_orange, servo_orange, 0.035)
            arm_oval(-0.65, -1.73, 0.155, 0.15, servo_black, servo_black, 0.025)
            arm_oval(-0.65, -1.73, 0.095, 0.09, servo_dark, servo_silver, 0.02)

            # Forearm: orange horizontal servo modules with black joint collars and a wrist motor.
            arm_link(-0.42, -1.84, 0.72, -1.98, 0.39)
            arm_line(-0.18, -1.86, -0.14, -2.18, servo_black, 0.075)
            arm_line(0.20, -1.91, 0.24, -2.23, servo_black, 0.075)
            arm_oval(-0.16, -1.88, 0.14, 0.18, servo_orange, servo_dark, 0.045)
            arm_oval(0.25, -1.93, 0.14, 0.17, servo_orange, servo_dark, 0.045)
            arm_oval(0.70, -1.98, 0.255, 0.235, servo_dark, servo_black, 0.055)
            arm_oval(0.70, -1.98, 0.205, 0.19, servo_orange, servo_orange, 0.03)
            arm_oval(0.70, -1.98, 0.105, 0.105, servo_black, servo_silver, 0.025)

            # Flexible black servo cable routed along the outside of the upper arm.
            c.create_line(x + 0.31 * k, ground - 1.03 * k,
                          x + 0.10 * k, ground - 1.21 * k,
                          x - 0.13 * k, ground - 1.44 * k,
                          x - 0.26 * k, ground - 1.63 * k,
                          smooth=True, splinesteps=18, fill=servo_black,
                          width=max(2.0, 0.055 * k), capstyle=tk.ROUND, tags="landmark")

            # Wrist coupler and two-prong metal gripper with open jaws.
            arm_link(0.86, -1.99, 1.03, -1.99, 0.25)
            arm_poly([(1.00, -2.15), (1.24, -2.12), (1.31, -1.98),
                      (1.24, -1.83), (1.00, -1.82), (0.96, -1.98)], servo_silver)
            # Upper and lower fingers: dark outlines, silver links and inward-facing tips.
            arm_line(1.18, -2.10, 1.52, -2.25, servo_black, 0.16)
            arm_line(1.18, -2.10, 1.52, -2.25, servo_silver, 0.105)
            arm_line(1.52, -2.25, 1.39, -2.16, servo_black, 0.12)
            arm_line(1.52, -2.25, 1.39, -2.16, servo_silver, 0.075)
            arm_line(1.18, -1.86, 1.52, -1.70, servo_black, 0.16)
            arm_line(1.18, -1.86, 1.52, -1.70, servo_silver, 0.105)
            arm_line(1.52, -1.70, 1.39, -1.79, servo_black, 0.12)
            arm_line(1.52, -1.70, 1.39, -1.79, servo_silver, 0.075)
            # Small dark pivot circles make the parallel-jaw mechanism read as a powered gripper.
            arm_oval(1.17, -2.10, 0.055, 0.055, servo_dark, servo_black, 0.02)
            arm_oval(1.17, -1.86, 0.055, 0.055, servo_dark, servo_black, 0.02)


    def draw_legend(self, cw, ch, s):
        """Small key fixed to the bottom-right corner of the map canvas."""
        items = (("Last station", "ok", None), ("Next stop", "map_next", (4, 3)), ("Planned trip", "map_route", "bar"))
        row, width = round(20 * self.text_factor), round(170 * self.text_factor)
        height = PAD * 2 + row * (len(items) + 1) - 4
        x0, y0 = cw - width - 12, ch - height - 12
        c = self.cv
        # ----- key background and title -----
        c.create_polygon(rrect(x0, y0, x0 + width, y0 + height, 8), smooth=True, fill=PALETTE["card"], outline=PALETTE["border"], tags="legend")
        c.create_text(x0 + PAD, y0 + PAD, text="Map key", anchor="nw", fill=PALETTE["text"], font=F_SMALL_BOLD, tags="legend")
        # ----- one row per symbol -----
        for k, (name, color, style) in enumerate(items, start=1):
            y = y0 + PAD + row * k + 9
            ix = x0 + PAD + 9
            if style == "bar":
                c.create_line(ix - 9, y, ix + 9, y, width=8, fill=PALETTE[color], capstyle="round", tags="legend")
            else:
                c.create_oval(ix - 7, y - 7, ix + 7, y + 7, outline=PALETTE[color], width=3, dash=style, tags="legend")
            c.create_text(ix + 20, y, text=name, anchor="w", fill=PALETTE["text"], font=F_SMALL, tags="legend")

    def draw_dynamic(self, now):
        """Redraw the parts of the map that change: the planned-trip highlight, rings and the jeep."""
        c, P, s, tr = self.cv, self.w2c, self.sc, self.tr
        c.delete("dyn")

        # ----- highlight along the planned ride -----
        a, b = self.trip_ends()
        if a != b:
            for k in range((b - a) % N):
                pts = [P(p) for p in LEG_PATHS[(a + k) % N]]
                flat = [v for p in pts for v in p]
                c.create_line(*flat, width=self.road_px() * 1.3, fill=PALETTE["map_route"], capstyle="round", joinstyle="round", tags=("dyn", "hl"))
                c.create_line(*flat, width=self.road_px() * 0.45, fill=PALETTE["map_route"], capstyle="round", joinstyle="round", tags=("dyn", "lane"))
            c.tag_lower("hl", "road")            # the wide outline goes under the road: it shows as an edge around it
            c.tag_lower("lane", "stop")          # the stripe goes on the road itself (under the stations, jeep and rings) ...
            c.tag_raise("arrow", "lane")         # ... and the white direction arrows stay on top of it

        # ----- last-station ring (green) and next-stop ring (dashed amber) -----
        fresh = self.fresh(now)
        r = self.stop_radius() + 6
        if fresh and tr.state != "PARKED":
            if not tr.depot and not tr.from_depot:                       # leaving the terminal: no last station yet
                lx, ly = P(STOPS[tr.last_stop][1])
                c.create_oval(lx - r, ly - r, lx + r, ly + r, outline=PALETTE["ok"], width=3, tags="dyn")
            nx, ny = P(STOPS[tr.next_stop][1])
            c.create_oval(nx - r, ny - r, nx + r, ny + r, outline=PALETTE["map_next"], width=3, dash=(4, 3), tags="dyn")

        # ----- the jeepney: body colored by its state, facing the way it is driving -----
        bx, by = P(tr.position())
        col = STATE_COLOR.get(tr.state, PALETTE["muted"]) if fresh else PALETTE["disabled"]
        bw, bh = self.jeep_size()
        prev = getattr(self, "jeep_prev_x", None)
        if prev is not None and abs(bx - prev) > 0.4:        # moving sideways: face that way (up and down keep the last facing)
            self.jeep_face = 1 if bx > prev else -1
        self.jeep_prev_x = bx
        draw_jeepney(c, bx, by, bw, bh, col, PALETTE["on_color"], PALETTE["text"], getattr(self, "jeep_face", 1), tags="dyn")

        # ----- small labels next to the jeep and the terminal -----
       # if fresh and tr.state in ("RUNNING", "LOW_BATTERY", "OBSTACLE_HOLD", "LINE_LOST") and tr.leg_start is not None:
       #     c.create_text(bx, by + bh + wr + 8, text="estimated", fill=PALETTE["muted"], font=F_SMALL, tags="dyn")
        if fresh and tr.depot and tr.lowbatt:
            x, y = P(CHARGING_POS)
            c.create_text(x, y, text="charging", fill=PALETTE["muted"], font=F_SMALL, tags="dyn")

        # ----- hover: a ring on the station (or a tooltip for the jeep) under the mouse -----
        self.draw_hover(now, fresh)

    # ---------- hover ----------
    def jeep_size(self):
        """Half the width and half the height of the jeepney on the map, in pixels."""
        return max(26 * self.text_factor, 30 * self.sc), max(14 * self.text_factor, 16 * self.sc)

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
        """Ring and tooltip for the hovered station or jeep; live ETA is not displayed."""
        if self.hover_item is None:
            return
        kind, i = self.hover_item
        c, tr = self.cv, self.tr
        if kind == "stop":
            x, y = self.w2c(STOPS[i][1])
            r = self.stop_radius()
            c.create_oval(x - r - 3, y - r - 3, x + r + 3, y + r + 3, outline=PALETTE["accent"], width=2, tags="dyn")
            lines = [STATION_TITLES[i]]
            self.draw_tooltip(x, y, r + 3, lines)
        else:
            bx, by = self.w2c(tr.position())
            lines = [self.state_text() if fresh else "Offline"]
            if fresh and tr.state != "PARKED" and not tr.depot:
                lines.append(f'Next stop: {STATION_TITLES[tr.next_stop]}')
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
