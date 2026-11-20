# ======================= THEME (colors, fonts, spacing) =======================
# Every color, font and spacing value used on screen lives in this section. To restyle the app,
# change a value here; no other file has a color or font size typed into it.
# Design rules: one brand color (blue), three colors that always mean the same thing
# (green = fine, amber = caution, red = danger), and the cream, tan and navy of the palette for everything else.

from tkinter import font as tkfont, ttk

# ----- colors -----
# The project palette (required). Every other color below is one of these five or a small tint of one of them,
# except the three meaning colors (green, amber, red), which must stay recognizable.
NAVY, BLUE, SKY, TAN, CREAM = "#081A3D", "#1F5AA6", "#8BB8FF", "#EAD2A8", "#FFF6E5"

PALETTE = {
    # surfaces
    "bg": CREAM,                 # window background
    "card": "#FFFCF5",           # raised panels: cards, tables, input boxes (cream, lifted toward white)
    "border": "#D2B98A",         # thin outlines and dividers (tan, darker)
    "header": TAN,               # table headings, unselected tab pills, secondary buttons
    "hover": SKY,                # under the mouse: buttons and tab pills
    # text
    "text": NAVY,                # main text
    "muted": "#3B4B6B",          # hints, labels and secondary text (navy, softer)
    "disabled": "#A39B88",       # unavailable controls and the offline dot
    "on_color": CREAM,           # text drawn on top of a colored fill
    # brand
    "op_bar": NAVY,              # the header bar in Operator mode
    "accent": BLUE,              # primary buttons, selected tab, next stop
    "accent_dark": "#164A8C",    # blue while the mouse is over a button
    # meaning (same meaning on every screen)
    "ok": "#2F7D3A",             # driving, in service, battery fine
    "warn": "#A85A00",           # at a station, obstacle, low battery, offline notice
    "danger": "#B3261E",         # emergency stop, fault, out of service
    "danger_dark": "#8F1D17",    # red while the mouse is over a button
    # map drawing
    "map_bg": CREAM,
    "map_block": TAN,            # city blocks
    "map_block_edge": "#D2B98A",
    "map_road": NAVY,            # main roads
    "map_road_line": CREAM,      # dashed line down the middle of the main road
    "map_street": "#FFFCF5",     # decorative side streets (the jeep never drives these)
    "map_depot_fill": "#FFFCF5",
    "map_depot_edge": "#D2B98A",
    "map_route": BLUE,           # highlight for the trip being planned
    "map_next": "#B86F00",       # dashed ring on the next station
    "map_pickup": "#D03F0A",     # ring: someone is waiting to board
    "map_drop": NAVY,            # ring: a rider is getting off
    "map_lm_wall": CREAM,        # landmark walls
    "map_lm_roof": BLUE,         # landmark roofs, awnings and doors
    "map_lm_line": NAVY,         # landmark outlines
    "map_lm_glass": SKY,         # windows on landmarks and on the jeepney
    "map_jeep_stripe": TAN,      # the side stripe and headlight on the jeepney
    # log table
    "stripe": "#F8EBD2",         # every second row of the Log table (plain rows)
}

# ----- the two looks -----
# Passenger mode is the warm cream look above. Operator mode swaps the surfaces to a cool sky-blue look (navy header bar,
# light-blue window, tan under the mouse), so the whole window, not only the top bar, shows which mode you are in.
# Text, brand blue, the meaning colors and the map keep their values in both modes. set_mode() switches between them.
PASSENGER_PALETTE = dict(PALETTE)
OPERATOR_PALETTE = {
    "bg": "#ECF3FE",             # window background (sky, very light)
    "card": "#F9FBFF",           # cards, tables, input boxes
    "border": "#7D9FD0",         # outlines and dividers
    "header": "#CFE0FA",         # table headings, unselected tab pills, secondary buttons
    "hover": TAN,                # under the mouse: warm tan against the cool surfaces
    "muted": "#33456B",          # hints, labels and secondary text
    "stripe": "#F2F7FE",         # every second row of the Log table
}


# ----- log rows: one entry per severity -----
# level: (label in the Level column and the export, text color, fill of even rows, fill of odd rows)
# The two fills alternate so the table stays striped even when neighbouring rows share a severity.
def build_log_levels():
    """The log row colors for the current mode (the plain rows follow the mode's card and stripe colors)."""
    return {
        "info": ("Info", PALETTE["text"], PALETTE["card"], PALETTE["stripe"]),     # routine: stops, passes, mode
        "ok": ("OK", PALETTE["ok"], "#f3f9f1", "#ecf5e9"),                         # done or recovered
        "warn": ("Warn", PALETTE["warn"], "#fef7ea", "#fdf1dc"),                   # caution: rejected, low battery, offline
        "danger": ("Alert", PALETTE["danger"], "#fcebe9", "#f8dcd9"),              # obstacle, line lost, emergency stop
    }


LOG_LEVELS = build_log_levels()  # one dict for the whole program: set_mode() refills it, so every importer sees the change

# ----- fonts (one family, six sizes/styles) -----
FONT_CHOICES = ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", "DejaVu Sans")
FONT_FAMILY = "TkDefaultFont"    # replaced by the first installed choice in apply_theme()
FONT_OBJECTS = []                # keeps the font objects from apply_theme() alive
F_DISPLAY, F_TITLE, F_HEADING = "eb_display", "eb_title", "eb_heading"
F_BODY, F_ITALIC, F_SMALL, F_SMALL_BOLD = "eb_body", "eb_italic", "eb_small", "eb_small_bold"
FONT_SCALE = (                   # (font name, size in points, weight/slant)
    (F_DISPLAY, 22, "bold"),     # the single most important fact on screen (next stop)
    (F_TITLE, 16, "bold"),       # key numbers: ETA, fare, live state
    (F_HEADING, 12, "bold"),     # labels that need weight, button text, card titles
    (F_BODY, 12, "normal"),      # normal text
    (F_ITALIC, 12, "italic"),    # italicized tagline
    (F_SMALL, 11, "normal"),     # hints and secondary detail (nothing on screen is smaller than 11 pt)
    (F_SMALL_BOLD, 11, "bold"),  # small labels on the map
)
DEFAULT_PT = 12                  # size of the plain Tk default fonts (entry boxes, drop-down lists, menus)
MAP_MIN_PT = 10                  # map labels follow the map zoom but never go below this size

# ----- spacing (one scale, so gaps look the same everywhere) -----
PAD_S, PAD, PAD_L = 4, 8, 12     # small, normal and large gaps in pixels
WRAP = 400                       # width in pixels at which long text wraps
RIGHT_W = 500                     # least width of the right-hand column in pixels (room for the fare summary and the Swap button)
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
    for name, size, style in FONT_SCALE:
        # keep a reference: Tk deletes a named font as soon as its Python object is garbage collected
        kwargs = {"root": root, "name": name, "family": FONT_FAMILY, "size": size}
        if style == "italic":
            kwargs["slant"] = "italic"
        else:
            kwargs["weight"] = style
        FONT_OBJECTS.append(tkfont.Font(**kwargs))
    for default in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(default).configure(family=FONT_FAMILY, size=DEFAULT_PT)

    apply_styles(root)


def set_mode(root, operator):
    """Switch every color between the Passenger look (operator=False) and the Operator look (operator=True).
    The palette is changed in place, so code that reads PALETTE later gets the new colors. This restyles the ttk widgets;
    plain Tk widgets (canvases) and the log tags are recolored by the App (see RolesMixin.apply_mode_colors)."""
    PALETTE.update(PASSENGER_PALETTE)
    if operator:
        PALETTE.update(OPERATOR_PALETTE)
    LOG_LEVELS.clear()
    LOG_LEVELS.update(build_log_levels())
    apply_styles(root)


def apply_styles(root):
    """Style every ttk widget from the current PALETTE. Safe to call again whenever the palette changes."""
    P = PALETTE

    # ----- window and base style -----
    root.configure(bg=P["bg"])
    s = ttk.Style(root)
    if s.theme_use() != "clam":
        s.theme_use("clam")      # draws the same on Windows, macOS and Linux
    s.configure(".", font=F_BODY, background=P["bg"], foreground=P["text"], bordercolor=P["border"])

    # ----- containers: every titled group is a white card (see widgets.Card); no etched Tk borders -----
    s.configure("Card.TFrame", background=P["card"], relief="solid", borderwidth=1, bordercolor=P["border"])
    s.configure("CardInner.TFrame", background=P["card"])

    # ----- header bar: light for passengers, navy for operators (so the mode is never in doubt) -----
    s.configure("Header.TFrame", background=P["card"])
    s.configure("HeaderOp.TFrame", background=P["op_bar"])
    for name, bg, strong, quiet in (("Header", "card", "text", "muted"), ("HeaderOp", "op_bar", "on_color", "on_color")):
        s.configure(f"{name}.TLabel", background=P[bg], foreground=P[strong], font=F_TITLE)
        s.configure(f"{name}Muted.TLabel", background=P[bg], foreground=P[quiet], font=F_BODY)
        s.configure(f"{name}Tagline.TLabel", background=P[bg], foreground=P[quiet], font=F_ITALIC)

    # ----- labels: Muted.* on the window background, Card* on the white card -----
    s.configure("Muted.TLabel", foreground=P["muted"])
    s.configure("Hint.TLabel", foreground=P["muted"], font=F_SMALL)      # the reason under a disabled button (on the window background)
    for name, font, color in (("Card", F_BODY, "text"), ("CardMuted", F_SMALL, "muted"),
                              ("CardHeading", F_HEADING, "text"), ("CardTitle", F_TITLE, "text"),
                              ("CardDisplay", F_DISPLAY, "accent"), ("Alert", F_HEADING, "danger")):
        s.configure(f"{name}.TLabel", background=P["card"], foreground=P[color], font=font)

    # ----- buttons: plain (secondary), Primary (blue) and Danger (red) -----
    s.configure("TButton", padding=(PAD_L, PAD + 2), background=P["header"], foreground=P["text"],
                bordercolor=P["border"], focuscolor=P["accent"])
    s.map("TButton", background=[("active", P["hover"]), ("disabled", P["bg"])],
          foreground=[("disabled", P["muted"])])
    for name, base, hover in (("Primary", "accent", "accent_dark"), ("Danger", "danger", "danger_dark")):
        s.configure(f"{name}.TButton", background=P[base], foreground=P["on_color"],
                    bordercolor=P[base], font=F_HEADING,
                    focuscolor=P["on_color"])       # white keyboard-focus ring: a blue ring is invisible on a blue button
        # disabled: light fill with muted dark text (white text on gray fails the contrast rule)
        s.map(f"{name}.TButton", background=[("active", P[hover]), ("disabled", P["header"])],
              foreground=[("disabled", P["muted"])], bordercolor=[("disabled", P["border"])])
    s.configure("Danger.TButton", padding=(PAD_L, PAD + 4))     # the emergency button is taller

    # ----- header buttons (Operator sign-in / Sign out): outlined, so they match the bar they sit on -----
    # light bar: blue text and outline; navy bar: cream text and outline. Under the mouse: light blue with dark text / brand blue.
    for name, bg, fg, edge, hover, fg_hover in (("Header", "card", "accent", "accent", "hover", "text"),
                                                ("HeaderOp", "op_bar", "on_color", "on_color", "accent", "on_color")):
        s.configure(f"{name}.TButton", padding=(PAD_L, PAD), background=P[bg], foreground=P[fg], font=F_HEADING,
                    bordercolor=P[edge], lightcolor=P[bg], darkcolor=P[bg], focuscolor=P[fg])
        s.map(f"{name}.TButton", background=[("active", P[hover]), ("pressed", P[hover])],
              foreground=[("active", P[fg_hover]), ("pressed", P[fg_hover])],
              lightcolor=[("active", P[hover]), ("pressed", P[hover])], darkcolor=[("active", P[hover]), ("pressed", P[hover])])

    # ----- tabs -----
    # The notebook keeps the pages and the tab logic, but draws no tab strip: the rounded pills above it
    # (widgets.PillTabs) are the tab names, so the stock tabs are given an empty layout.
    s.configure("TNotebook", background=P["bg"], bordercolor=P["border"])
    s.configure("Pill.TNotebook", background=P["bg"], bordercolor=P["border"], tabmargins=0)
    s.layout("Pill.TNotebook.Tab", [])

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
    for font, (_name, size, _style) in zip(FONT_OBJECTS, FONT_SCALE):
        font.configure(size=round(size * f))
    for default in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(default).configure(size=round(DEFAULT_PT * f))
    body = next(font for font, (name, _s, _w) in zip(FONT_OBJECTS, FONT_SCALE) if name == F_BODY)
    line = body.metrics("linespace")
    ttk.Style(root).configure("Treeview", rowheight=max(ROW_H, line + 2 * PAD))
    # a read-only table (nothing to click) needs less height per row than one a person selects from
    ttk.Style(root).configure("Compact.Treeview", rowheight=max(ROW_H - 4, line + PAD))