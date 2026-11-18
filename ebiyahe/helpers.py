"""Small functions used all over the program: distances, time text, fare, battery percent,
keyboard chords and the saved text-size setting."""

import json
import math
import os
from datetime import datetime

from config import DEFAULT_HOST, DEFAULT_PORT, BASE_FARE, BATT_FULL, BATT_LOW, DISCOUNTS, MOD, PER_STOP_FARE, SETTINGS_FILE, TEXT_SIZES


# ======================= HELPERS =======================
def path_len(pts):
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def point_at(pts, frac):
    d = max(0.0, min(1.0, frac)) * path_len(pts)
    for i in range(len(pts) - 1):
        seg = math.dist(pts[i], pts[i + 1])
        if d <= seg or i == len(pts) - 2:
            t = d / seg if seg else 0.0
            return (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t)
        d -= seg
    return pts[-1]


def fmt_dur(s):
    if s is None:
        return "-"
    s = int(round(s))
    if s < 60:
        return f"{s} s"
    m, s = divmod(s, 60)
    return f"{m} min {s:02d} s"


def fmt_clock(ts):
    return datetime.fromtimestamp(ts).strftime("%I:%M:%S %p").lstrip("0")


def fmt12(hhmm):
    return datetime.strptime(hhmm, "%H:%M").strftime("%I:%M %p").lstrip("0")


def fare_for(legs, category="Regular"):
    return round((BASE_FARE + PER_STOP_FARE * legs) * (1.0 - DISCOUNTS.get(category, 0.0)), 2)


def stop_label(load, unload):
    """LOADING if only a pickup is flagged, UNLOADING if only a drop-off or Para, otherwise both."""
    show_load = load or not unload
    show_unload = unload or not load
    if show_load and show_unload:
        return "LOADING / UNLOADING"
    return "LOADING" if show_load else "UNLOADING"


def batt_pct(v):
    return max(0.0, min(100.0, (v - BATT_LOW) / (BATT_FULL - BATT_LOW) * 100.0))


def int_list(v):
    return [x for x in v if isinstance(x, int) and not isinstance(x, bool)] if isinstance(v, list) else []


def to_float(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def set_enabled(widget, on):
    """Enable (on=True) or disable (on=False) a ttk widget such as a button."""
    widget.state(["!disabled"] if on else ["disabled"])


def chord(key, shift=False):
    """Tk key patterns for MOD+key (or MOD+Shift+key). Letters are bound in both cases, so Caps Lock
    cannot break a shortcut (this matters most for the emergency stop)."""
    mods = f"{MOD}-Shift-" if shift else f"{MOD}-"
    keys = {key.lower(), key.upper()} if key.isalpha() else {key}
    return [f"<{mods}Key-{k}>" for k in sorted(keys)]


def load_settings():
    """Everything saved in settings.json, as a dict (empty if there is no file or it cannot be read)."""
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_setting(key, value):
    """Save one setting without losing the others. A failure to write must never stop the app."""
    data = load_settings()
    data[key] = value
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    except OSError:
        pass


def load_text_size():
    """The text size saved last time (percent), or the normal size if there is none."""
    try:
        pct = int(load_settings().get("text_size", TEXT_SIZES[0]))
    except (ValueError, TypeError):
        return TEXT_SIZES[0]
    return pct if pct in TEXT_SIZES else TEXT_SIZES[0]


def save_text_size(pct):
    save_setting("text_size", pct)


def load_connection():
    """The connection used last time as (mode, host, port): mode is 'demo' or 'wifi'.
    With nothing saved (or anything unreadable) it is Demo mode with the default address."""
    saved = load_settings().get("connection", {})
    if not isinstance(saved, dict):
        saved = {}
    mode = saved.get("mode") if saved.get("mode") in ("demo", "wifi") else "demo"
    host = saved.get("host") if isinstance(saved.get("host"), str) and saved.get("host").strip() else DEFAULT_HOST
    port = str(saved.get("port")) if str(saved.get("port", "")).isdigit() else str(DEFAULT_PORT)
    return mode, host, port


def rrect(x1, y1, x2, y2, r):
    return [x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y1 + r, x2, y2 - r, x2, y2 - r,
            x2, y2, x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r,
            x1, y1 + r, x1, y1]
