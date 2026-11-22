# E-Biyahe

A Tkinter tracking app for a patrolling automated guided e-jeepney (ESP32-S3 controller).
The jeep drives its loop and stops at every station. Commuters see where it is, when it reaches each station,
and look up the fare and travel time between two stations (nothing is booked); operators monitor and dispatch the jeep.
A built-in Demo mode with a simulated jeep lets every feature be tested without the hardware.

The app opens in **Passenger mode** (map, status, trip planner, schedule). The **Operator sign-in** button in the
top bar unlocks the dispatch controls, connection settings, log and Demo tools.

## Run

```
python main.py
```

Python 3.8 or newer. Tkinter only; nothing to install. Run it from this folder. The app creates a
`data/` folder next to `main.py` for the event log (`log.csv`) and your saved settings (`settings.json`: text size and the
last connection mode). The default operator PIN is `1234`; change `OPERATOR_PIN` in `config.py`.

The window opens maximized and the map takes all the room the narrow right-hand column leaves (`RIGHT_W` in `theme.py`).
Rows that change text (the alert line, the route, the reasons under buttons) keep a fixed height, so nothing moves when they change.

## The files

| File | What it holds |
|---|---|
| `main.py` | Starts the app. Its header explains how the service works and the message format. |
| `config.py` | Settings you can change: fares, hours, battery levels, operator PIN, file locations, text sizes. |
| `roles.py` | Who may see and do what: the one permissions table for Passenger and Operator. |
| `theme.py` | Colors, fonts and spacing, and the functions that apply them to Tk. The colors are the project palette: navy `#081A3D`, blue `#1F5AA6`, sky `#8BB8FF`, tan `#EAD2A8` and cream `#FFF6E5`. |
| `map_data.py` | The map as data: station positions, roads, landmarks, the depot and the jeep's seven states. |
| `helpers.py` | Small functions: distances, time text, fare, battery percent, saved settings. |
| `models.py` | `Tracker` (what the jeep reports, plus ETA guesses). |
| `sim.py` | `JeepSim`, the pretend jeep used by Demo mode. |
| `sources.py` | `DemoSource` and `TcpSource`, the two messengers that bring jeep messages to the app. |
| `jeepney.py` | The jeepney drawing, used on the map and as the mark in the header bar. |
| `widgets.py` | Reusable screen parts: `Card`, `Pill` and `PillTabs` (the rounded tab names), `StatusBadge`, `MessageBar`, `ScrollFrame`, `HeaderBar`, `PinDialog`. |
| `app.py` | The `App` window. Puts together the eight parts below. |
| `app_build.py` | Builds the screens: menu bar, connection box, status card and the four tabs. |
| `app_feedback.py` | The message bar, the log list and log export. |
| `app_keyboard.py` | Keyboard shortcuts, text size, window size and the help window. |
| `app_commands.py` | What the buttons do: dispatch, return, reset, emergency stop and dwell time. |
| `app_link.py` | The connection to the jeep and the messages that come back. |
| `app_refresh.py` | The update that runs four times a second and refreshes every screen. |
| `app_map.py` | Drawing the map: blocks and landmarks, roads, stations, the jeepney and the planned-trip highlight. |
| `app_roles.py` | The header bar, operator sign-in and sign-out, and showing or hiding what each role may use. |

## How the parts fit together

```
          config.py   theme.py   helpers.py          (no dependencies on the rest)
              \          |          /
          roles.py  map_data.py  jeepney.py          (permissions; stations, roads, states; the jeepney drawing)
              /     |       \
        models.py  sim.py  widgets.py
                      |
                  sources.py                         (Demo or Wi-Fi messenger, on its own thread)
                      |
   app_build  app_feedback  app_keyboard  app_commands  app_link  app_refresh  app_map  app_roles
                      \________________  |  ________________/
                                      app.py  ->  main.py
```

The `App` window is built from eight mixin classes (one per `app_*.py` file). Each file is one topic,
and its methods are still called as `self.<name>()` from anywhere in the window.

## Where do I change...

- a fare, an opening hour or a battery level: `config.py`
- a color, a font or a gap: `theme.py` (no other file has colors or font sizes typed into it)
- where a station sits or which way the jeep drives: `map_data.py`
- what a button does: `app_commands.py`
- who can see or use something (passenger or operator): the table in `roles.py`
- the operator PIN or the idle sign-out time: `config.py`
- what a tab looks like: `app_build.py`
- how the jeep is simulated: `sim.py`

## One rule to remember

`FONT_FAMILY` is chosen when the window starts (the first installed font from a list). Other files must
read it as `theme.FONT_FAMILY` after `import theme`. Writing `from theme import FONT_FAMILY` would copy the
value from before it was chosen.

## Passenger and operator modes

| | Passenger | Operator |
|---|---|---|
| Map, map key, status card | yes | yes |
| Plan trip (fare and times), Schedule | yes | yes |
| Battery bar | no (a warning appears when it matters) | yes |
| Connection box (Demo or Wi-Fi) | hidden: the app connects by itself | yes |
| Operator and Log tabs, Demo menu, log export | hidden | yes |
| EMERGENCY STOP | hidden | red button fixed at the bottom of the right-hand column, visible from every tab |

- The app always starts in Passenger mode and connects to the connection used last time (Demo mode the first time).
- **Operator sign-in** (top right, or Ctrl+L) asks for the PIN. Wrong PINs are explained in the window.
- In Operator mode the whole window changes look, so the mode is never in doubt:
  - Passenger is warm cream and tan. Operator is cool sky blue, with a navy top bar and a tan hover color.
  - The switch happens in one place: `RolesMixin.apply_mode_colors` calls `theme.set_mode`, which swaps the `OPERATOR_PALETTE` colors into `PALETTE`, restyles ttk, and recolors the canvases, log tags and map.
  - Text, buttons, status colors and the map keep the same colors in both modes, so nothing gets harder to read.
  - To adjust the operator look, edit `OPERATOR_PALETTE` in `theme.py`.
- Signing out, or 10 minutes without a key press or click (`OPERATOR_IDLE_MIN`), returns to Passenger mode.
- Signing in and out is written to the log.

## Hover

- **Hover.** Buttons and the tab pills react to the mouse. On the map, pointing at a station rings it and shows who is
  waiting or getting off there; pointing at the jeep shows its state and next stop.

**About the PIN.** It stops accidents (a passenger pressing Dispatch); it is not real security, because anyone who can
read `config.py` can read the PIN. In a real deployment the jeep (or a server) would decide who may send commands.
