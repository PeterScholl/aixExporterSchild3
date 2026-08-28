"""Kleine, wiederverwendbare Tkinter-Hilfswidgets.

Ausgelagert aus SchildMNSDataMatcher_GUI.py, damit auch generator.py (z.B. für den
Kursart-Zuordnungs-Dialog) Tooltips anzeigen kann, ohne die GUI-Datei zu importieren.
"""
import tkinter as tk


class ToolTip:
    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text = text
        self.delay = delay  # Millisekunden
        self.tooltip = None
        self.after_id = None

        widget.bind("<Enter>", self.schedule_show)
        widget.bind("<Leave>", self.cancel_tooltip)

    def schedule_show(self, event):
        self.cancel_tooltip()
        self.after_id = self.widget.after(self.delay, lambda: self.show_tooltip(event))

    def show_tooltip(self, event):
        # Tooltip Fenster erstellen
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)  # Kein Fensterrahmen
        self.tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
        # Ohne Rahmen/Taskleisten-Eintrag steuert Windows das Z-Ordering nicht zuverlässig -
        # ohne diese beiden Zeilen kann das Tooltip hinter dem Elternfenster landen.
        self.tooltip.attributes("-topmost", True)
        self.tooltip.lift()
        label = tk.Label(self.tooltip, text=self.text, background="lightgrey", relief="solid", borderwidth=1, justify="left")
        label.pack()

    def cancel_tooltip(self, event=None):
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None
