#continue 3,4,5
#add pretty bg
#better fonts
#better spacings/layouts
#make prettier
#clean up code
#packs
#separate operator and passenger (hide operator) (login)?
#assign appropriate colors
#split into modules

#!/usr/bin/env python3
"""
E-BIYAHE - Tkinter dispatch and monitoring app for the automated guided e-jeepney diorama.

Run:   python main.py        (Python 3.8+, Tkinter only, nothing to pip install)

HOW THE SERVICE WORKS (on-demand)
  The jeep drives a one-way loop, counterclockwise (BR > TR > TL > BL), and parks in the depot when idle.
  At every station tag it reads, the jeep stops ONLY if
      1. someone is waiting there (a booked pickup), or
      2. someone on board booked a drop-off there (armed only AFTER that rider boarded), or
      3. Para was pressed, or
      4. the service mode is Patrol (stop at every station) and the battery is fine.
  Otherwise it logs a pass and keeps going. The jeep makes these decisions itself, so it keeps
  working if Wi-Fi drops. The app only sends requests and shows what the jeep reports.

MODES
  Demo  - a built-in simulated jeep that follows the same rules (class JeepSim). The Demo menu
          triggers an obstacle, a lost line, low battery and a Wi-Fi drop.
  Wi-Fi - connects to the jeep over TCP (default 192.168.4.1:8080, the ESP32 access point).

MESSAGES (one JSON object per line)
  App -> jeep
    {"cmd":"request","id":7,"from":0,"to":2}   book a ride (station numbers are 0..3)
    {"cmd":"cancel","id":7}                    cancel a ride that has not boarded yet
    {"cmd":"para"}  {"cmd":"estop"}  {"cmd":"reset"}  {"cmd":"dispatch"}  {"cmd":"return"}
    {"cmd":"mode","value":"ondemand"|"patrol"}      {"cmd":"dwell","value":4}
    {"cmd":"sync","ids":[7,8]}                 sent on every (re)connect: the jeep drops other bookings
  Jeep -> app: STATUS every 1 s and on every change
    {"state":"RUNNING","next":1,"depot":false,"batt":7.9,"dist":42,"head":0,"patrol":false,
     "para":false,"lowbatt":false,"paused":false,"crit":false,"dwell":4,"load":false,"unload":false,
     "ir":"010","pick":[0,1,0,0],"drop":[0,0,0,1],"wait":[7],"ride":[]}
    state = PARKED | RUNNING | LOADING_UNLOADING | OBSTACLE_HOLD | LINE_LOST | EMERGENCY_STOP | LOW_BATTERY
    next  = index of the next station tag the jeep will read; the last station is (next - 1) mod 4.
            While parked, next is 0 (the jeep leaves the depot toward BR).
    pick/drop = people waiting / on board per station;  wait/ride = booking ids waiting / on board
    paused = new requests refused (low battery, or returning to the depot)
    LOW_BATTERY is also used for "returning to depot" ordered by the operator.
  Jeep -> app: EVENT (for the log and alerts)
    {"type":"event","ev":"ARRIVED","stop":2,"load":true,"unload":false,"boarded":[7],"done":[]}
    ev = ARRIVED DEPARTED TAG_PASS PARA OBSTACLE OBSTACLE_CLEAR FAULT ESTOP RESET DISPATCHED PARKED
         LOW_BATT RETURNING BATT_OK MODE REJECTED CANCELLED
  Booking states in the app come from the STATUS lists wait/ride, so a missed event or a short
  Wi-Fi drop cannot leave a ride stuck.

KEYBOARD AND TEXT SIZE
  Everything can be done without a mouse. Press F1 (or open the menus) to see every shortcut:
  Ctrl+1 ... Ctrl+5 switch tabs, Ctrl+R requests a ride, Ctrl+P is Para, Ctrl+Shift+E is the emergency
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
#   models.py        Booking (one ride request) and Tracker (what the jeep reports, plus ETA guesses)
#   sim.py           JeepSim, the pretend jeep used by Demo mode
#   sources.py       DemoSource and TcpSource, the two messengers that bring messages in
#   widgets.py       small reusable screen parts (status badge, message bar, scroll frame)
#   app.py           the App window: puts the parts below together
#   app_build.py     builds the screens: menu bar, connection box, status card and tabs
#   app_feedback.py  message bar, log list and log export
#   app_keyboard.py  keyboard shortcuts, text size, window size and the help window
#   app_commands.py  what the buttons do: request, cancel, para, dispatch, mode, dwell
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
