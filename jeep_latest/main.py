#better fonts
#make prettier
#clean up code
#packs
#adjust fare, seconds, schedule (4:00 am to 10:00 pm)
#imitate others' modules
#disable emergency stop button after clicking it, need to press reset first

#!/usr/bin/env python3
"""
E-BIYAHE - Tkinter jeep tracker for the automated guided e-jeepney diorama.

Run:   python main.py        (Python 3.8+, Tkinter only, nothing to pip install)

HOW THE SERVICE WORKS (patrol)
  The jeep drives a one-way loop, counterclockwise (BR > TR > TL > BL), and stops at EVERY station for the
  dwell time. Nobody books or requests anything: the app shows passengers where the jeep is, when it reaches
  each station, and what a trip between two stations costs and how long it takes (estimates).
  The jeep parks in the depot only when the battery is low or an operator sends it back.
  The app only shows what the jeep reports (operators can also dispatch, return, reset and emergency-stop it).

MODES
  Demo  - a built-in simulated jeep that follows the same rules (class JeepSim). The Demo menu
          triggers an obstacle, a lost line, low battery and a Wi-Fi drop.
  Wi-Fi - connects to the jeep over TCP (default 192.168.4.1:8080, the ESP32 access point).

MESSAGES (one JSON object per line)
  App -> jeep
    {"cmd":"estop"}  {"cmd":"reset"}  {"cmd":"dispatch"}  {"cmd":"return"}
    {"cmd":"mode","value":"patrol"}      {"cmd":"dwell","value":4}
    (the app sends mode=patrol and the dwell time on every (re)connect)
  Jeep -> app: STATUS every 1 s and on every change
    {"state":"RUNNING","next":1,"depot":false,"batt":7.9,"dist":42,"head":0,"lowbatt":false,
     "paused":false,"crit":false,"dwell":4,"ir":"010"}
    state = PARKED | RUNNING | LOADING_UNLOADING | OBSTACLE_HOLD | LINE_LOST | EMERGENCY_STOP | LOW_BATTERY
    next  = index of the next station tag the jeep will read; the last station is (next - 1) mod 4.
            While parked, next is 0 (the jeep leaves the depot toward BR).
    paused = the jeep is not doing its rounds (low battery, or returning to the depot)
    LOW_BATTERY is also used for "returning to depot" ordered by the operator.
  Jeep -> app: EVENT (for the log and alerts)
    {"type":"event","ev":"ARRIVED","stop":2}
    ev = ARRIVED DEPARTED TAG_PASS OBSTACLE OBSTACLE_CLEAR FAULT ESTOP RESET DISPATCHED PARKED
         LOW_BATT RETURNING BATT_OK

KEYBOARD AND TEXT SIZE
  Everything can be done without a mouse. Press F1 (or open the menus) to see every shortcut:
  Ctrl+1 ... Ctrl+4 switch tabs, Ctrl+Shift+E is the emergency
  stop, and Ctrl++ / Ctrl+- / Ctrl+0 make the text larger, smaller or normal (remembered in
  data/settings.json). On a Mac use Cmd instead of Ctrl. Tab moves between controls, Space or Enter
  presses a button, and the arrow keys choose radio buttons and table rows.

Firmware note: latch every tag read until the state machine has handled it. If an obstacle or
fault wins priority on the same loop pass as a tag read, the tag must not be lost.

Edit config.py to match your diorama, fares and hours.
"""

# ----------------------------------------------------------------------------------
# FILE MAP - the files of this program (all in this folder)
#   main.py          starts the app (this file) and describes how the service works
#   config.py        settings you can change (fares, hours, battery levels, operator PIN, file locations, text sizes)
#   roles.py         who may see and do what: the Passenger and Operator permissions table
#   theme.py         colors, fonts and spacing shared by every screen
#   map_data.py      station positions, roads, the depot and the jeep's seven states
#   helpers.py       small functions (distance, time text, fare, battery percent, saved settings)
#   models.py        Tracker (what the jeep reports, plus ETA guesses)
#   sim.py           JeepSim, the pretend jeep used by Demo mode
#   sources.py       DemoSource and TcpSource, the two messengers that bring messages in
#   widgets.py       small reusable screen parts (status badge, message bar, scroll frame)
#   app.py           the App window: puts the parts below together
#   app_build.py     builds the screens: menu bar, connection box, status card and tabs
#   app_feedback.py  message bar, log list and log export
#   app_keyboard.py  keyboard shortcuts, text size, window size and the help window
#   app_commands.py  what the buttons do: dispatch, return, reset, emergency stop, dwell
#   app_link.py      the connection to the jeep and the messages that come back
#   app_refresh.py   the update that runs four times a second
#   app_map.py       drawing the map
#   app_roles.py     the header bar, operator sign-in and sign-out, and showing or hiding what each role may use
# ----------------------------------------------------------------------------------

from app import App


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
