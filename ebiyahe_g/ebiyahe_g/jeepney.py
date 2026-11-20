"""The jeepney drawing, shared by the map (the moving jeep) and the header bar (the small mark next to the app name).

It is drawn on any Tk canvas with a few polygons, so there is no image file to ship."""

from theme import PALETTE


# ======================= JEEPNEY DRAWING =======================
def draw_jeepney(c, bx, by, bw, bh, body, outline, ink, face=1, tags=()):
    """Draw a jeepney on canvas `c`, centred on (bx, by).
    bw and bh are half the body's width and height in pixels. `body` is the body color, `outline` is the color it is
    outlined with (use the background color to make it blend in) and `ink` is the color of the roof rack and wheels.
    face is 1 for a jeepney driving to the right and -1 for one driving to the left."""
    def X(u):
        return bx + face * u * bw

    def Y(v):
        return by + v * bh

    def poly(pts, fill, edge="", width=1):
        c.create_polygon([v for px, py in pts for v in (X(px), Y(py))], fill=fill, outline=edge, width=width,
                         joinstyle="round", tags=tags)

    def rect(u1, v1, u2, v2, fill, edge=""):
        c.create_rectangle(X(u1), Y(v1), X(u2), Y(v2), fill=fill, outline=edge, tags=tags)

    # ----- roof rack and bundle (behind the body) -----
    c.create_line(X(-0.85), Y(-1.28), X(0.2), Y(-1.28), fill=ink, width=2, tags=tags)
    for u in (-0.8, 0.15):
        c.create_line(X(u), Y(-1.28), X(u), Y(-1.0), fill=ink, width=2, tags=tags)
    rect(-0.65, -1.55, -0.15, -1.28, PALETTE["map_lm_roof"], ink)
    # ----- wheels (drawn first: the body covers their top half) -----
    wr = max(3.5, 0.32 * bh)
    for u in (-0.55, 0.6):
        c.create_oval(X(u) - wr, Y(0.7) - wr, X(u) + wr, Y(0.7) + wr, fill=ink, outline=outline, tags=tags)
        c.create_oval(X(u) - wr * 0.4, Y(0.7) - wr * 0.4, X(u) + wr * 0.4, Y(0.7) + wr * 0.4, fill=outline, outline="", tags=tags)
    # ----- body: tall passenger cabin at the back, lower hood at the front -----
    poly([(-1, -1.0), (0.3, -1.0), (0.42, -0.35), (0.97, -0.3), (1, -0.2), (1, 0.7), (-1, 0.7)], body, outline, 2)
    rect(-0.97, 0.05, 0.97, 0.3, PALETTE["map_jeep_stripe"])                         # side stripe
    for u1, u2 in ((-0.88, -0.52), (-0.42, -0.06)):                                  # side windows
        rect(u1, -0.82, u2, -0.4, PALETTE["map_lm_glass"])
    poly([(0.12, -0.82), (0.3, -0.82), (0.38, -0.4), (0.12, -0.4)], PALETTE["map_lm_glass"])   # windshield
    rect(0.9, -0.12, 1.0, 0.1, PALETTE["map_jeep_stripe"])                           # headlight
