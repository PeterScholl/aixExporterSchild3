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


class DropdownMenuButton(tk.Button):
    """Ersatz für eine echte Menü-Cascade (tk.Menu), wenn pro Eintrag Tooltips gebraucht werden.

    Hintergrund: Für Tooltips auf tk.Menu-Einträgen gäbe es eigentlich nur das virtuelle Event
    <<MenuSelect>> (feuert, wenn der hervorgehobene Eintrag wechselt) - auf Windows mit Tk 8.6
    feuert das bei echtem Maus-Hover aber gar nicht zuverlässig (per Testskript verifiziert).
    Native Menüs geben Tk auf Windows sonst keine Möglichkeit, Hover an Python zu melden.

    Diese Klasse baut die "Menü"-Einträge deshalb aus ganz normalen tk.Button-Widgets in einem
    eigenen Popup-Fenster - jeder Eintrag ist ein echtes Widget mit normalem Enter/Leave und
    damit kompatibel zur bestehenden ToolTip-Klasse. Optischer Kompromiss: Da es kein natives
    tk.Menu mehr ist, kann es nicht in der nativen Fenster-Menüleiste hängen, sondern ist ein
    eigenes Button-Widget (z.B. in einer Toolbar unterhalb der Menüleiste).

    entries: Liste der Eintrags-Texte (Anzeigereihenfolge). tooltips: optional {Text: Tooltip-
    Text}. command: wird beim Anklicken eines Eintrags mit dessen Text aufgerufen (wie beim
    bisherigen button_clicked(text)). Die erzeugten Button-Widgets liegen in self.entry_widgets
    ({Text: Button}), um sie z.B. wie normale Grid-Buttons einzufärben (siehe
    refresh_button_highlighting in SchildMNSDataMatcher_GUI.py)."""

    def __init__(self, master, text, entries, tooltips=None, command=None, **kwargs):
        super().__init__(master, text=f"{text} ▾", relief="raised", **kwargs)
        self.command = command
        self.entry_widgets = {}
        self._offen = False
        self.configure(command=self._toggle)

        # Das Popup wird einmalig gebaut und nur ein-/ausgeblendet (nicht bei jedem Öffnen neu
        # erzeugt) - sonst würden die in self.entry_widgets gemerkten Button-Referenzen nach dem
        # ersten Schließen ungültig (zerstörtes Tk-Objekt).
        self.popup = tk.Toplevel(self)
        self.popup.withdraw()
        self.popup.wm_overrideredirect(True)
        self.popup.attributes("-topmost", True)
        rahmen = tk.Frame(self.popup, relief="raised", borderwidth=1)
        rahmen.pack()
        for eintrag_text in entries:
            b = tk.Button(rahmen, text=eintrag_text, anchor="w", relief="flat",
                          command=lambda t=eintrag_text: self._waehlen(t))
            b.pack(fill="x")
            if tooltips and tooltips.get(eintrag_text):
                ToolTip(b, tooltips[eintrag_text])
            self.entry_widgets[eintrag_text] = b

        # Klick irgendwo außerhalb (auch auf ein anderes DropdownMenuButton) schließt das Popup -
        # einmalig gebunden statt bei jedem _open()/_close(), da bind_all() app-weit gilt und
        # mehrere Instanzen sich sonst gegenseitig die Bindung wegnehmen würden.
        self.winfo_toplevel().bind_all("<Button-1>", self._on_global_click, add="+")

    def _toggle(self):
        self._close() if self._offen else self._open()

    def _open(self):
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        self.popup.wm_geometry(f"+{x}+{y}")
        self.popup.deiconify()
        self.popup.lift()
        self._offen = True

    def _on_global_click(self, event):
        if not self._offen:
            return
        w = event.widget
        # Klick auf den Auslöse-Button selbst (Toggle übernimmt das) oder innerhalb des eigenen
        # Popups (z.B. auf einen Eintrag) nicht als "außerhalb" werten.
        if w is self or str(w).startswith(str(self.popup)):
            return
        self._close()

    def _waehlen(self, text):
        self._close()
        if self.command:
            self.command(text)

    def _close(self):
        self._offen = False
        self.popup.withdraw()
