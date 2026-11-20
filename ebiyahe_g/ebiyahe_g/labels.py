"""English and Filipino labels, and the switch between them.

Only fixed labels are translated here: headings, buttons, tab names, table headings and the map key.
Live messages (the message bar, the reason under a disabled button, the jeep's state) stay in English.

To add or fix a translation, change TEXT below. Each entry is  key: (English, Filipino).
A text may hold {placeholders}, filled in with the values given when the label is bound."""

LANGS = ("en", "fil")
LANG_NAME = {"en": "English", "fil": "Filipino"}


# ======================= THE LABELS =======================
TEXT = {
    # ----- tabs and cards -----
    "tab_plan": ("Plan trip", "Magplano"),
    "tab_rides": ("My rides", "Mga sakay ko"),
    "tab_schedule": ("Schedule", "Iskedyul"),
    "map": ("Map", "Mapa"),
    # ----- status card -----
    "next_stop": ("Next stop", "Susunod na hinto"),
    "arrives_in": ("Arrives in", "Darating sa loob ng"),
    "para": ("Para: stop at the next station", "Para: huminto sa susunod na istasyon"),
    # ----- Plan trip -----
    "ride_on": ("Ride on at", "Sakay sa"),
    "get_off": ("Get off at", "Baba sa"),
    "passenger": ("Passenger", "Pasahero"),
    "swap": ("⇅ Swap", "⇅ Palitan"),
    "fare": ("Fare", "Pamasahe"),
    "jeep_reaches": ("Jeep reaches you in", "Darating ang jeep"),
    "ride_time": ("Ride time", "Tagal ng biyahe"),
    "total": ("Total", "Kabuuan"),
    "arrive_at": ("You arrive at", "Darating ka ng"),
    "request": ("Request ride", "Humiling ng sakay"),
    # ----- My rides -----
    "col_trip": ("Trip", "Biyahe"),
    "col_status": ("Status", "Katayuan"),
    "col_eta": ("ETA", "Oras"),
    "cancel_ride": ("Cancel selected ride", "Kanselahin ang napiling sakay"),
    # ----- Schedule -----
    "hours": ("Operating hours: {open} to {close}", "Oras ng operasyon: {open} hanggang {close}"),
    "col_station": ("Station", "Istasyon"),
    "col_passes": ("Jeep passes", "Daraan ang jeep"),
    "col_following": ("Following", "Kasunod"),
    # ----- map key, map labels and hover tips -----
    "legend_title": ("Map key", "Gabay sa mapa"),
    "legend_pickup": ("Waiting for pickup", "Naghihintay ng sakay"),
    "legend_drop": ("Rider getting off", "Bababa"),
    "legend_last": ("Last station", "Huling istasyon"),
    "legend_route": ("Planned trip", "Planong biyahe"),
    "map_pickup": ("PICKUP", "SAKAY"),
    "map_drop": ("DROP", "BABA"),
    "tip_no_requests": ("No requests", "Walang kahilingan"),
}


# ======================= THE SWITCH =======================
class Labels:
    """Holds the current language and every label that must change when it does.
    bind() sets a label now and remembers how to set it again; set_language() redoes them all."""

    def __init__(self, lang="en"):
        self.lang = lang if lang in LANGS else "en"
        self.bound = []                  # (key, setter, placeholder values)
        self.listeners = []              # functions to call after a language change (redraw the map, resize the tab pills ...)

    def text(self, key, **values):
        """The label `key` in the current language."""
        english, filipino = TEXT[key]
        text = filipino if self.lang == "fil" else english
        return text.format(**values) if values else text

    def bind(self, key, setter, **values):
        """Set a label now with setter(text), and again every time the language changes."""
        self.bound.append((key, setter, values))
        setter(self.text(key, **values))

    def on_change(self, listener):
        """Call listener() after every language change."""
        self.listeners.append(listener)

    def set_language(self, lang):
        """Switch language: reset every bound label, then tell the listeners."""
        self.lang = lang if lang in LANGS else "en"
        for key, setter, values in self.bound:
            setter(self.text(key, **values))
        for listener in self.listeners:
            listener()
