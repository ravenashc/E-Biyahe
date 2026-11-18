"""Colors, fonts and spacing shared by every screen, plus the functions that apply them to Tk.

Note for other files: FONT_FAMILY is chosen when the window starts, so read it as theme.FONT_FAMILY
(with `import theme`). Importing the name directly would copy its starting value."""

from tkinter import font as tkfont, ttk


# ======================= THEME (colors, fonts, spacing) =======================
# Every color, font and spacing value used on screen lives in this section. To restyle the app,
# change a value here; no other file has a color or font size typed into it.
# Design rules: one brand color (jeepney blue), three colors that always mean the same thing
# (green = fine, amber = caution, red = danger), and neutral grays for everything else.

# ----- colors -----
PALETTE = {
    # surfaces (warm cream, like paper tickets)
    "bg": "#faf6ec",             # window background
    "card": "#ffffff",           # raised panels: cards, tables, input boxes
    "border": "#ddd3bd",         # thin outlines and dividers
    "header": "#efe7d3",         # table headings, unselected tabs, secondary buttons
    # text
    "text": "#1d2433",           # main text (ink)
    "muted": "#4a5163",          # hints, labels and secondary text
    "disabled": "#a39d8c",       # unavailable controls and the offline dot
    "on_color": "#ffffff",       # text drawn on top of a colored fill
    # brand
    "accent": "#14467a",         # jeepney blue: primary buttons, selected tab, next stop
    "accent_dark": "#0e3459",    # blue while the mouse is over a button
    # meaning (same meaning on every screen)
    "ok": "#2f7d3a",             # driving, in service, battery fine
    "warn": "#a85a00",           # at a station, obstacle, low battery, offline notice
    "danger": "#b3261e",         # emergency stop, fault, out of service
    "danger_dark": "#8f1d17",    # red while the mouse is over a button
    # map drawing (warm base so the map matches the rest of the window)
    "map_bg": "#f1ead6",
    "map_block": "#d6e2bf",
    "map_block_edge": "#b2c196",
    "map_road": "#58606e",       # main roads (slate)
    "map_road_line": "#f1e9d2",  # dashed line down the middle of the main road
    "map_street": "#d6ccb4",     # decorative side streets (the jeep never drives these)
    "map_depot_fill": "#efe7d3",
    "map_depot_edge": "#a39d8c",
    "map_route": "#4f87c9",      # highlight for the trip being planned
    "map_next": "#b86f00",       # dashed ring on the next station
    "map_pickup": "#d03f0a",     # ring: someone is waiting to board
    "map_drop": "#1d6fb8",       # ring: a rider is getting off
    # log table
    "stripe": "#f6f1e3",         # every second row of the Log table (plain rows)
}

# ----- log rows: one entry per severity -----
# level: (label in the Level column and the export, text color, fill of even rows, fill of odd rows)
# The two fills alternate so the table stays striped even when neighbouring rows share a severity.
LOG_LEVELS = {
    "info": ("Info", PALETTE["text"], PALETTE["card"], PALETTE["stripe"]),         # routine: stops, passes, mode
    "ok": ("OK", PALETTE["ok"], "#f3f9f1", "#ecf5e9"),                             # done or recovered
    "warn": ("Warn", PALETTE["warn"], "#fef7ea", "#fdf1dc"),                       # caution: rejected, low battery, offline
    "danger": ("Alert", PALETTE["danger"], "#fcebe9", "#f8dcd9"),                  # obstacle, line lost, emergency stop
}

# ----- fonts (one family, five sizes) -----
FONT_CHOICES = ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", "DejaVu Sans")
FONT_FAMILY = "TkDefaultFont"    # replaced by the first installed choice in apply_theme()
FONT_OBJECTS = []                # keeps the font objects from apply_theme() alive
F_DISPLAY, F_TITLE, F_HEADING = "eb_display", "eb_title", "eb_heading"
F_BODY, F_SMALL, F_SMALL_BOLD = "eb_body", "eb_small", "eb_small_bold"
FONT_SCALE = (                   # (font name, size in points, weight)
    (F_DISPLAY, 22, "bold"),     # the single most important fact on screen (next stop)
    (F_TITLE, 16, "bold"),       # key numbers: ETA, fare, live state
    (F_HEADING, 12, "bold"),     # labels that need weight, button text, card titles
    (F_BODY, 12, "normal"),      # normal text
    (F_SMALL, 11, "normal"),     # hints and secondary detail (nothing on screen is smaller than 11 pt)
    (F_SMALL_BOLD, 11, "bold"),  # small labels on the map
)
DEFAULT_PT = 12                  # size of the plain Tk default fonts (entry boxes, drop-down lists, menus)
MAP_MIN_PT = 10                  # map labels follow the map zoom but never go below this size

# ----- spacing (one scale, so gaps look the same everywhere) -----
PAD_S, PAD, PAD_L = 4, 8, 12     # small, normal and large gaps in pixels
WRAP = 400                       # width in pixels at which long text wraps
ROW_H = 28                       # minimum height of a table row (large enough to tap or click comfortably)
FIELD_PAD = 6                    # inner padding of entry boxes and drop-downs


def apply_theme(root):
    """Create the named fonts and style every ttk widget. Call once, right after the window exists."""
    global FONT_FAMILY
    P = PALETTE

    # ----- fonts: pick the first installed family, then create the named sizes -----
    installed = set(tkfont.families(root))
    system_family = tkfont.nametofont("TkDefaultFont").actual("family")
    FONT_FAMILY = next((f for f in FONT_CHOICES if f in installed), system_family)
    for name, size, weight in FONT_SCALE:
        # keep a reference: Tk deletes a named font as soon as its Python object is garbage collected
        FONT_OBJECTS.append(tkfont.Font(root=root, name=name, family=FONT_FAMILY, size=size, weight=weight))
    for default in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(default).configure(family=FONT_FAMILY, size=DEFAULT_PT)

    # ----- window and base style -----
    root.configure(bg=P["bg"])
    s = ttk.Style(root)
    s.theme_use("clam")          # draws the same on Windows, macOS and Linux
    s.configure(".", font=F_BODY, background=P["bg"], foreground=P["text"], bordercolor=P["border"])

    # ----- containers: every titled group is a white card (see widgets.Card); no etched Tk borders -----
    s.configure("Card.TFrame", background=P["card"], relief="solid", borderwidth=1, bordercolor=P["border"])
    s.configure("CardInner.TFrame", background=P["card"])

    # ----- header bar: white for passengers, blue for operators (so the mode is never in doubt) -----
    s.configure("Header.TFrame", background=P["card"])
    s.configure("HeaderOp.TFrame", background=P["accent"])
    for name, bg, strong, quiet in (("Header", "card", "text", "muted"), ("HeaderOp", "accent", "on_color", "on_color")):
        s.configure(f"{name}.TLabel", background=P[bg], foreground=P[strong], font=F_TITLE)
        s.configure(f"{name}Muted.TLabel", background=P[bg], foreground=P[quiet], font=F_BODY)

    # ----- labels: Muted.* on the window background, Card* on the white card -----
    s.configure("Muted.TLabel", foreground=P["muted"])
    for name, font, color in (("Card", F_BODY, "text"), ("CardMuted", F_SMALL, "muted"),
                              ("CardHeading", F_HEADING, "text"), ("CardTitle", F_TITLE, "text"),
                              ("CardDisplay", F_DISPLAY, "accent"), ("Alert", F_HEADING, "danger")):
        s.configure(f"{name}.TLabel", background=P["card"], foreground=P[color], font=font)

    # ----- buttons: plain (secondary), Primary (blue) and Danger (red) -----
    s.configure("TButton", padding=(PAD_L, PAD + 2), background=P["header"], foreground=P["text"],
                bordercolor=P["border"], focuscolor=P["accent"])
    s.map("TButton", background=[("active", P["border"]), ("disabled", P["bg"])],
          foreground=[("disabled", P["muted"])])
    for name, base, hover in (("Primary", "accent", "accent_dark"), ("Danger", "danger", "danger_dark")):
        s.configure(f"{name}.TButton", background=P[base], foreground=P["on_color"],
                    bordercolor=P[base], font=F_HEADING,
                    focuscolor=P["on_color"])       # white keyboard-focus ring: a blue ring is invisible on a blue button
        # disabled: light fill with muted dark text (white text on gray fails the contrast rule)
        s.map(f"{name}.TButton", background=[("active", P[hover]), ("disabled", P["header"])],
              foreground=[("disabled", P["muted"])], bordercolor=[("disabled", P["border"])])
    s.configure("Danger.TButton", padding=(PAD_L, PAD + 4))     # the emergency button is taller

    # ----- tabs -----
    s.configure("TNotebook", background=P["bg"], bordercolor=P["border"])
    s.configure("TNotebook.Tab", padding=(PAD_L, PAD), background=P["header"], foreground=P["muted"])
    s.map("TNotebook.Tab", background=[("selected", P["bg"])], foreground=[("selected", P["accent"])])

    # ----- tables -----
    s.configure("Treeview", background=P["card"], fieldbackground=P["card"], foreground=P["text"],
                rowheight=ROW_H, bordercolor=P["border"])
    s.map("Treeview", background=[("selected", P["accent"])], foreground=[("selected", P["on_color"])])
    s.configure("Treeview.Heading", background=P["header"], foreground=P["text"], font=F_HEADING,
                relief="flat", padding=(PAD, PAD_S))

    # ----- input boxes, radio buttons and dividers -----
    for widget in ("TEntry", "TCombobox", "TSpinbox"):
        s.configure(widget, fieldbackground=P["card"], foreground=P["text"], bordercolor=P["border"],
                    padding=FIELD_PAD)
    s.map("TCombobox", fieldbackground=[("readonly", P["card"])],
          selectbackground=[("readonly", P["card"])], selectforeground=[("readonly", P["text"])],
          foreground=[("readonly", "focus", P["text"])])         # the clam theme turns a focused drop-down's text white on white; keep it dark
    for widget in ("TEntry", "TCombobox", "TSpinbox"):      # blue outline on the box that has the keyboard focus
        s.map(widget, bordercolor=[("focus", P["accent"])], lightcolor=[("focus", P["accent"])],
              darkcolor=[("focus", P["accent"])])
    s.configure("TRadiobutton", background=P["bg"])
    s.map("TRadiobutton", background=[("active", P["bg"])])
    s.configure("Card.TRadiobutton", background=P["card"])       # radio buttons inside a white card
    s.map("Card.TRadiobutton", background=[("active", P["card"])])
    s.configure("TSeparator", background=P["border"])

    # ----- scroll bars (the right-hand column and the log table): quiet gray that matches the palette -----
    s.configure("Vertical.TScrollbar", troughcolor=P["bg"], background=P["disabled"], bordercolor=P["border"],
                arrowcolor=P["muted"], gripcount=0)
    s.map("Vertical.TScrollbar", background=[("active", P["muted"]), ("pressed", P["muted"])])

    # ----- battery bar in three colors (see App.set_battery) -----
    for name, color in (("Ok", "ok"), ("Warn", "warn"), ("Danger", "danger")):
        s.configure(f"{name}.Horizontal.TProgressbar", troughcolor=P["border"], background=P[color],
                    bordercolor=P["border"], lightcolor=P[color], darkcolor=P[color], thickness=10)


def apply_text_size(root, percent):
    """Scale every font to `percent` of its normal size and keep the table rows tall enough for it.
    Safe to call at any time: Tk redraws each widget that uses these fonts."""
    f = percent / 100.0
    for font, (_name, size, _weight) in zip(FONT_OBJECTS, FONT_SCALE):
        font.configure(size=round(size * f))
    for default in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(default).configure(size=round(DEFAULT_PT * f))
    body = next(font for font, (name, _s, _w) in zip(FONT_OBJECTS, FONT_SCALE) if name == F_BODY)
    ttk.Style(root).configure("Treeview", rowheight=max(ROW_H, body.metrics("linespace") + 2 * PAD))
