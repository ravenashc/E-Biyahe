"""Message bar, log list and log export: every way the app tells the user what happened.

This is one part of the App window: App (app.py) inherits FeedbackMixin, so these methods are called as self.<name>()."""

import csv
import os
from tkinter import filedialog
from datetime import datetime

from config import LOG_FILE
from theme import LOG_LEVELS


# ======================= FEEDBACK (messages and log) =======================
class FeedbackMixin:
    """Message bar, log list and log export: every way the app tells the user what happened."""

    # ---------- log and messages ----------
    def show_message(self, text, level="info"):
        """Show feedback in the message bar. level: 'info', 'ok' (done), 'warn' (cannot do that) or 'error'."""
        self.bar.show(text, level)

    def log_add(self, text, level="info"):
        """Add one line to the Log tab and to data/log.csv.
        level: 'info' (routine), 'ok' (done or recovered), 'warn' (caution) or 'danger' (needs attention)."""
        if level not in LOG_LEVELS:
            level = "info"
        stamp = datetime.now()
        self.log_seq += 1
        iid = str(self.log_seq)
        stripe = "odd" if self.log_seq % 2 else "even"     # fixed per row, so rows never change color as new ones arrive
        self.logtree.insert("", 0, iid=iid, tags=(f"{level}_{stripe}",),
                            values=(stamp.strftime("%H:%M:%S"), LOG_LEVELS[level][0], text))
        self.log_data[iid] = (stamp, level, text)
        kids = self.logtree.get_children()
        if len(kids) > 500:
            self.logtree.delete(kids[-1])
            self.log_data.pop(kids[-1], None)
        try:
            os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
            with open(LOG_FILE, "a", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerow([stamp.isoformat(timespec="seconds"), text])
        except OSError:
            pass

    def clear_log(self):
        """Empty the Log tab (data/log.csv keeps every event)."""
        self.logtree.delete(*self.logtree.get_children())
        self.log_data.clear()

    def export_log(self):
        """Save the events now shown in the Log tab to a CSV file the operator picks, oldest first."""
        rows = [self.log_data[i] for i in reversed(self.logtree.get_children()) if i in self.log_data]
        if not rows:
            self.show_message("Nothing to export: the log is empty.", "warn")
            return
        folder = os.path.dirname(LOG_FILE)
        path = filedialog.asksaveasfilename(
            parent=self, title="Export log", defaultextension=".csv",
            filetypes=[("CSV file (opens in Excel)", "*.csv"), ("All files", "*.*")],
            initialdir=folder if os.path.isdir(folder) else os.getcwd(),
            initialfile=datetime.now().strftime("ebiyahe_log_%Y%m%d_%H%M%S.csv"))
        if not path:                                        # the operator closed the dialog
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:    # utf-8-sig: Excel shows the peso sign
                out = csv.writer(fh)
                out.writerow(["Timestamp", "Severity", "Event"])
                for stamp, level, text in rows:
                    out.writerow([stamp.isoformat(sep=" ", timespec="seconds"), LOG_LEVELS[level][0], text])
        except OSError as err:
            self.show_message(f"Could not save the log: {err.strerror or err}", "error")
            return
        self.show_message(f"Exported {len(rows)} log events to {path}", "ok")
