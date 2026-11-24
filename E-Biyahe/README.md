# E-Biyahe

**E-Biyahe** is a desktop monitoring and operator-control application for an automated guided e-jeepney project. It uses Python and Tkinter to display the vehicle's route, station status, estimated arrivals, passenger trip information, and operator controls. The application can run with a built-in simulator or connect to an ESP32-S3 vehicle controller over Wi-Fi.

The jeepney follows a **fixed patrol loop** and stops at every station. Passengers can check fares, but trips are not booked through the application.

## Features

### Passenger mode

- Live map showing the jeepney, its fixed route, station locations, next stop, and estimated arrival.
- **My Trip** fare lookup for a selected boarding station, alighting station, and passenger category.
- **Schedule** view with operating hours and estimated station-passage times.
- Service alerts when the vehicle reports an issue or status change.

### Operator mode

- PIN-protected access to vehicle controls and diagnostics.
- Dispatch a parked jeepney, request a return to the terminal, reset a fault, or trigger the emergency-stop command.
- Adjust the station dwell time (the time the jeepney waits at each stop).
- Choose between the built-in Demo source and the Wi-Fi vehicle connection.
- View the live vehicle state, battery-voltage reading, sensor information, and event log; export the log to a file.
- **My Trip is hidden in Operator mode** so operators monitor and control the fixed patrol rather than choose passenger routes.

The battery percentage bar has been removed from the interface. The operator live readout retains the numeric battery-voltage diagnostic, and low-battery return behavior remains part of the vehicle logic.

### Demo mode

The built-in simulator follows the same patrol logic and message format as the connected vehicle. It can be used to try the interface without the ESP32 hardware. The Demo menu can simulate an obstacle, line loss, low battery, and a temporary Wi-Fi drop.

## Station order and city map

The automatic patrol visits the stations in this order:

1. **THIRSTOP Station** — BR (bottom-right)
2. **E.S.P. CORP. Station** — TR (top-right)
3. **PARKSILICA Station** — TL (top-left)
4. **LILIM Station** — BL (bottom-left)

After LILIM Station, the jeepney continues along the bottom road, passes the **Terminal** spur, and returns to THIRSTOP Station. The terminal is where the vehicle parks while waiting to be dispatched or while recharging.

The map's inner city blocks contain these visual landmarks:

- **Parking Station** — multi-level parking structure with an entrance barrier.
- **Construction Site** — construction area with a servo-powered robotic arm.
- **School**
- **Park**

The landmark drawings are part of the map display. The four roadside stations are separate from the inner-block landmarks.

## Operating information

| Setting | Current default |
|---|---|
| Service days | Monday to Sunday |
| Operating hours | 4:00 AM–10:00 PM |
| Regular fare | ₱17.00 (flat fare) |
| Student discount | 20% |
| Senior discount | 20% |
| PWD discount | 20% |
| Station dwell time | 4 seconds |
| Operator idle sign-out | 10 minutes |

Fare values are estimates. The application does not reserve seats or request a special trip; the jeepney continues to patrol the fixed loop.

## Requirements

- Python **3.9 or newer**.
- Tkinter available in the Python installation.
- For live vehicle operation: an ESP32-S3 controller/vehicle that implements the E-Biyahe TCP JSON-line message protocol described below.

No third-party Python packages are required by the desktop application. On some Linux distributions, Tkinter may need to be installed separately through the operating system's package manager.

## Run the application

Open a terminal in the `jeep_latest` directory and run:

```bash
python main.py
```

On Windows, `py main.py` can be used if the Python launcher is installed.

For example, from the repository root:

```bash
cd jeep_latest
python main.py
```

The application starts in Passenger mode. The connection used last time is remembered; Demo mode is used on the first run. The app creates and updates the `data/` directory beside `main.py` for saved settings and the event log.

## Connect to the ESP32-S3

The default Wi-Fi endpoint is:

| Setting | Default |
|---|---|
| Host | `192.168.4.1` |
| TCP port | `8080` |

These values can be changed in `config.py`. In Operator mode, choose **Wi-Fi jeep** in the Connection panel and connect. The TCP source reconnects automatically when the link is interrupted.

### Message format

The connection uses UTF-8 JSON objects, one object per line. The application sends commands to the vehicle and receives periodic status messages and event messages.

Commands sent by the app include:

```json
{"cmd":"estop"}
{"cmd":"reset"}
{"cmd":"dispatch"}
{"cmd":"return"}
{"cmd":"mode","value":"patrol"}
{"cmd":"dwell","value":4}
```

The patrol mode and configured dwell time are sent again when the app connects or reconnects.

A vehicle status message follows this general shape:

```json
{
  "type": "status",
  "state": "RUNNING",
  "next": 1,
  "depot": false,
  "batt": 7.9,
  "dist": 42,
  "head": 0,
  "patrol": true,
  "lowbatt": false,
  "paused": false,
  "crit": false,
  "dwell": 4,
  "ir": "010"
}
```

Recognized vehicle states are `PARKED`, `RUNNING`, `LOADING_UNLOADING`, `OBSTACLE_HOLD`, `LINE_LOST`, `EMERGENCY_STOP`, and `LOW_BATTERY`. The vehicle should report status periodically (the app documentation specifies once per second) and when the state changes.

Event messages use `type: "event"`; events include `ARRIVED`, `DEPARTED`, `TAG_PASS`, `OBSTACLE`, `OBSTACLE_CLEAR`, `FAULT`, `ESTOP`, `RESET`, `DISPATCHED`, `PARKED`, `LOW_BATT`, `RETURNING`, and `BATT_OK`.

**Vehicle-side safety:** The desktop emergency-stop button sends a command over the connection. It is not a replacement for a physical emergency stop or other hardware safety measures on the vehicle. Use the vehicle's physical safety control for a real emergency, especially when the app is offline.

## Operator access and safety notes

The default operator PIN in `config.py` is `1234`. **Change it before using the application in a shared or public environment.** The PIN is a basic interface safeguard, not strong authentication: anyone who can read the source code can read the configured PIN.

Operator mode automatically signs out after 10 minutes without keyboard or mouse activity (configurable with `OPERATOR_IDLE_MIN`).

The emergency-stop control is only available in Operator mode. Low-battery and fault handling also depend on the vehicle controller implementing the expected protocol and safety behavior.

## Project structure

All application source files are in `jeep_latest/`.

| File | Purpose |
|---|---|
| `main.py` | Documents the operating model and vehicle message protocol; starts the Tkinter application. |
| `app.py` | Creates the main application window and shared state. |
| `app_build.py` | Builds the map/status layout, Passenger and Operator pages, Schedule, and Log views. |
| `app_map.py` | Draws the city map, landmarks, station markers, route, terminal, and moving jeepney. |
| `app_roles.py` | Handles Passenger/Operator sign-in, sign-out, and role-specific visibility. |
| `app_commands.py` | Handles dispatch, return, reset, emergency stop, and dwell-time commands. |
| `app_link.py` | Handles connection events and messages received from the vehicle. |
| `app_refresh.py` | Periodically refreshes status, alerts, and displayed values. |
| `app_feedback.py` | Displays alerts, records events, and exports the log. |
| `app_keyboard.py` | Keyboard shortcuts, text sizing, and the help window. |
| `config.py` | Host/port, fares, discounts, hours, battery thresholds, operator PIN, and UI settings. |
| `roles.py` | Defines permissions for Passenger and Operator modes. |
| `map_data.py` | Defines station order and positions, roads, landmarks, and terminal geometry. |
| `jeepney.py` | Draws the E-Biyahe jeepney icon used on the map and header. |
| `models.py` | Stores vehicle state and calculates estimated arrival information. |
| `sim.py` | Implements the built-in simulated jeepney. |
| `sources.py` | Demo and TCP message sources. |
| `theme.py` | Application colors, fonts, and Tkinter styling. |
| `widgets.py` | Reusable interface components. |
| `helpers.py` | Shared calculations, formatting, and saved-setting helpers. |
| `data/log.csv` | Automatically recorded application events. |
| `data/settings.json` | Saved UI and connection preferences. |

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `F1` | Open the help window |
| `Ctrl+L` | Sign in to or out of Operator mode |
| `Ctrl+1`–`Ctrl+4` | Switch tabs where the current role has access |
| `Ctrl+Shift+D` | Dispatch |
| `Ctrl+Shift+H` | Return to terminal |
| `Ctrl+Shift+F` | Reset a fault |
| `Ctrl+Shift+E` | Emergency stop |
| `Ctrl++` / `Ctrl+-` / `Ctrl+0` | Increase, decrease, or reset text size |

On macOS, use `Command` instead of `Ctrl`.

## Configuration

Most project settings are centralized in `config.py`. Map geometry and stop order are in `map_data.py`; shared colors and fonts are in `theme.py`; landmark and vehicle drawings are in `app_map.py` and `jeepney.py`.

For project-specific changes, edit the relevant setting or drawing in `jeep_latest/`, then run the application again to test it.
