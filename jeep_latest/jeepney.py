"""A compact side-view drawing of the E-Biyahe physical jeepney model.

The same vector icon is used on the map and beside the app name. Sensors and wiring
are intentionally omitted; the drawing focuses on the blue, white, red and yellow body.
"""

from theme import PALETTE


def draw_jeepney(c, bx, by, bw, bh, body=None, outline=None, ink=None, face=1, tags=()):
    """Draw the project's boxy e-jeepney on a Tk canvas.

    `face` is 1 when travelling right and -1 when travelling left. The optional
    color arguments remain in the signature for callers, but the vehicle uses
    its fixed real-model colors regardless of the live service state.
    """
    def X(u):
        # Local u=-1 is the front; mirror the bus to match its travel direction.
        return bx - face * u * bw

    def Y(v):
        return by + v * bh

    dark = PALETTE["map_jeep_trim"]
    roof = PALETTE["map_jeep_roof"]
    white = PALETTE["map_jeep_white"]
    red = PALETTE["map_jeep_red"]
    yellow = PALETTE["map_jeep_yellow"]
    window = PALETTE["map_jeep_window"]
    tire = PALETTE["map_jeep_tire"]
    hub = PALETTE["map_jeep_hub"]

    def poly(points, fill, edge=dark, width=None):
        edge_width = max(1.0, bh * 0.055) if width is None else width
        coords = []
        for u, v in points:
            coords.extend((X(u), Y(v)))
        c.create_polygon(coords, fill=fill, outline=edge, width=edge_width,
                         joinstyle="round", tags=tags)

    def rect(u1, v1, u2, v2, fill, edge=""):
        x1, x2 = sorted((X(u1), X(u2)))
        y1, y2 = sorted((Y(v1), Y(v2)))
        c.create_rectangle(x1, y1, x2, y2, fill=fill, outline=edge, tags=tags)

    def oval(u, v, rx, ry, fill, edge=dark, edge_width=None):
        x, y = X(u), Y(v)
        ew = max(1.0, bh * 0.045) if edge_width is None else edge_width
        c.create_oval(x - rx * bw, y - ry * bh, x + rx * bw, y + ry * bh,
                      fill=fill, outline=edge, width=ew, tags=tags)

    # Wheels: a prominent yellow-hub drive wheel and the smaller front caster.
    oval(0.40, 0.48, 0.205, 0.34, tire, dark)
    oval(0.40, 0.48, 0.125, 0.205, hub, dark, max(1.0, bh * 0.04))
    oval(0.40, 0.48, 0.048, 0.08, dark, dark, 1)
    oval(-0.73, 0.51, 0.13, 0.23, tire, dark)
    oval(-0.73, 0.51, 0.065, 0.12, "#BFC7CD", dark, 1)

    # Straight-sided passenger body: both front and rear end vertically.
    poly([(-0.98, -0.78), (0.98, -0.78),
          (0.98, 0.39), (-0.98, 0.39)], white, dark)

    # Broad red lower band ends neatly before the full-height yellow rear panel.
    rect(-0.96, 0.055, 0.73, 0.39, red, dark)
    rect(0.73, -0.78, 0.98, 0.39, yellow, dark)

    # Flat blue roof with straight front and rear edges.
    rect(-1.00, -0.96, 0.99, -0.79, roof, dark)
    rect(-0.97, -0.84, 0.94, -0.78, roof, "")

    # Dark side glazing. Thick white mullions keep the windows readable at icon size.
    rect(-0.82, -0.70, -0.40, -0.15, window, dark)
    rect(-0.31, -0.70, 0.14, -0.15, window, dark)
    rect(0.23, -0.70, 0.68, -0.15, window, dark)
    # Front windshield and its pale frame, drawn as a straight rectangle.
    rect(-0.97, -0.72, -0.84, -0.14, window, dark)
    # Window pillars and door line.
    for u in (-0.36, 0.18):
        rect(u, -0.73, u + 0.045, -0.11, white, "")
    rect(0.15, -0.12, 0.20, 0.05, dark, "")

    # Small model-matched details: front lamp, rear lamp and a dark lower sill.
    rect(-0.99, -0.02, -0.93, 0.12, yellow, dark)
    rect(0.92, -0.02, 0.98, 0.12, "#D84B36", dark)
    rect(-0.80, 0.36, 0.80, 0.42, dark, "")
