"""The E-Biyahe window: assembles the parts (app_build, app_feedback, app_keyboard, app_commands,
app_link, app_refresh, app_map, app_roles) and sets everything up."""

import queue
import time
import tkinter as tk

from app_build import BuildMixin
from app_commands import CommandMixin
from app_feedback import FeedbackMixin
from app_keyboard import KeyboardMixin
from app_link import LinkMixin
from app_map import MapMixin
from app_refresh import RefreshMixin
from app_roles import RolesMixin
from config import APP_TITLE, TEXT_SIZES
from helpers import load_connection, load_text_size
from map_data import STOPS
from models import Tracker
from roles import PASSENGER
from theme import apply_theme


# ======================= APP =======================
class App(BuildMixin, FeedbackMixin, KeyboardMixin, CommandMixin, LinkMixin, RefreshMixin, MapMixin, RolesMixin, tk.Tk):
    """The E-Biyahe window. Its behaviour is spread over the mixin classes listed above (one file each);
    this class only sets everything up."""

    def __init__(self):
        super().__init__()
        apply_theme(self)              # fonts, colors and ttk styles (see theme.py)
        self.title(APP_TITLE)
        self.geometry("1280x860")
        self.minsize(900, 600)
        self.q = queue.Queue()
        self.source = None
        self.tr = Tracker()
        self.text_pct, self.text_factor = TEXT_SIZES[0], 1.0    # current text size (see set_text_size)
        self.reserved_cols = []        # (frame, column, font, texts, extra): columns that keep a fixed width
        self.reserved = []             # (frame, row, font, lines): rows that keep a fixed height (see reserve in app_keyboard.py)
        self.wrap_base = {}            # label -> its wrap width at normal text size
        self.col_base = []             # (table, {column: width at normal text size})
        self.shortcuts = self.shortcut_table()
        self.log_seq = 0               # counts log lines; its odd/even value keeps each row's stripe fixed
        self.log_data = {}             # row id -> (time, level, text) for every row shown in the Log tab
        self.role = PASSENGER          # the app always starts in Passenger mode (see roles.py)
        self.last_activity = time.time()   # for the operator's idle sign-out
        self.pin_dialog = None         # the PIN window while it is open
        self.mode_var = tk.StringVar(value=load_connection())   # Demo or Wi-Fi, as used last time (Demo the first time)
        self.names = [s[0] for s in STOPS]
        self.sc, self.ox, self.oy = 1.0, 0.0, 0.0
        self.build_ui()
        self.bind_keys()
        self.bind_activity()
        self.apply_role()              # Passenger mode: hide everything that is for operators
        # ----- text size (as last used) and window size: fit the finished layout, but stay on screen -----
        self.set_text_size(load_text_size(), startup=True)
        self.cb_from.focus_set()       # the first Tab press continues from the trip choices
        self.start_maximized()         # the map is the main thing on screen, so it gets the whole screen
        self.log_add("App started")
        self.ensure_connected()        # passengers have no Connection box, so the app connects by itself
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(250, self.tick)
