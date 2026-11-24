"""Who may see and do what in Passenger and Operator modes.

OPERATOR_ONLY reserves dispatch and diagnostic controls for operators. The trip planner is
passenger-only: operators run the fixed automatic patrol and cannot choose a route.
"""

from config import TAB_NAMES


PASSENGER, OPERATOR = "passenger", "operator"
ROLE_LABEL = {PASSENGER: "Passenger mode", OPERATOR: "Operator mode"}

OPERATOR_ONLY = {
    "tabs": ("Operator", "Log"),
    "menus": ("Operator", "Demo"),
    "panels": ("connection", "estop"),
    "shortcuts": ("connect", "export", "dispatch", "return", "reset", "estop"),
}

# The operator controls the vehicle but does not choose a passenger boarding/alighting route.
OPERATOR_HIDDEN = {
    "tabs": ("My Trip",),
}


def allowed(role, kind, name):
    """Return whether a role may use a tab, menu, panel or shortcut."""
    if kind == "shortcuts" and name.startswith("tab") and name[3:].isdigit():
        index = int(name[3:]) - 1
        if not 0 <= index < len(TAB_NAMES):
            return False
        return allowed(role, "tabs", TAB_NAMES[index])
    if role == OPERATOR:
        if kind == "tabs":
            return name not in OPERATOR_HIDDEN["tabs"]
        return True
    return name not in OPERATOR_ONLY[kind]
