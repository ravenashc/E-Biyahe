"""Who may see and do what: the Passenger and Operator roles.

One table (OPERATOR_ONLY) lists everything reserved for operators; everything that is not listed is
available to both roles. The rest of the program asks allowed(...) instead of scattering
`if operator:` checks around, so changing what a role can use means changing this table only.

The PIN that unlocks Operator mode lives in config.py. It prevents accidents (a passenger tapping
Dispatch); it is not real security, because anyone who can read the file can read the PIN."""

from config import TAB_NAMES


# ======================= ROLES =======================
PASSENGER, OPERATOR = "passenger", "operator"
ROLE_LABEL = {PASSENGER: "Passenger mode", OPERATOR: "Operator mode"}


# ======================= PERMISSIONS =======================
OPERATOR_ONLY = {
    "tabs": ("Operator", "Log"),                                              # tab names (see TAB_NAMES in config.py)
    "menus": ("Operator", "Demo"),                                            # menu bar entries
    "panels": ("connection", "battery", "estop"),                             # connection box, battery bar, emergency-stop button
    "shortcuts": ("connect", "export", "dispatch", "return", "reset", "estop"),   # ids in the shortcut table (app_keyboard.py)
}


def allowed(role, kind, name):
    """True if `role` may use `name` of the given kind ('tabs', 'menus', 'panels' or 'shortcuts')."""
    if role == OPERATOR:
        return True
    if kind == "shortcuts" and name.startswith("tab") and name[3:].isdigit():   # Ctrl+1 ... Ctrl+4 follow the tabs they open
        return TAB_NAMES[int(name[3:]) - 1] not in OPERATOR_ONLY["tabs"]
    return name not in OPERATOR_ONLY[kind]
