"""Kleine, wiederverwendbare Tkinter-Hilfswidgets.

Ausgelagert aus SchildMNSDataMatcher_GUI.py, damit auch generator.py (z.B. für den
Kursart-Zuordnungs-Dialog) Tooltips anzeigen kann, ohne die GUI-Datei zu importieren.
"""
import tkinter as tk
from tkinter import ttk


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
        self._pruefe_app_aktiv()

    def _pruefe_app_aktiv(self):
        """Schließt das Popup, sobald die Anwendung den Fokus verliert (Alt+Tab, Klick in ein
        anderes Programm, Desktop anzeigen) oder minimiert wird. Das Popup ist -topmost und würde
        sonst über allen anderen Fenstern stehen bleiben, denn <Button-1> (siehe
        _on_global_click) bekommt nur Klicks innerhalb dieser Anwendung mit. Per after()-Polling
        statt <FocusOut>, weil FocusOut auch bei jedem Fokuswechsel innerhalb der App feuert."""
        if not self._offen:
            return
        if self.focus_displayof() is None or self.winfo_toplevel().state() == "iconic":
            self._close()
            return
        self._poll_id = self.after(200, self._pruefe_app_aktiv)

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
        if getattr(self, "_poll_id", None):
            self.after_cancel(self._poll_id)
            self._poll_id = None
        self.popup.withdraw()


class SearchSelectList(ttk.Frame):
    """Such-/Auswahl-Widget: Suchfeld + Trefferliste über eine beliebige Objektliste (Schüler,
    Lehrer, Lerngruppen, ...). Filtert live nach Teilen des Namens ODER der ID - alle durch
    Leerzeichen getrennten Suchbegriffe müssen (Groß/Klein egal, als Teilstring) im Anzeigetext
    oder in der ID vorkommen, z.B. "muster ef" oder "1234".

    items: Liste beliebiger Objekte (i.d.R. Dicts). display(obj) -> Anzeigetext der Zeile;
    id_of(obj) -> ID (wird zusätzlich zum Anzeigetext durchsucht). multi: Mehrfachauswahl.
    on_activate(obj): optional, wird bei Doppelklick/Enter auf eine Zeile aufgerufen.
    Auswahl abfragen: get_selected() (Liste der Objekte); Inhalt tauschen: set_items()."""

    def __init__(self, master, items, display, id_of=lambda o: o.get("id"), multi=True,
                 on_activate=None, height=10, on_select=None, **kwargs):
        super().__init__(master, **kwargs)
        self._on_select = on_select
        self._display = display
        self._id_of = id_of
        self._on_activate = on_activate
        self._items = []
        self._shown = []  # aktuell in der Listbox angezeigte Objekte (gleiche Reihenfolge)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._suche = tk.StringVar()
        self._suche.trace_add("write", lambda *_: self._filtern())
        ttk.Entry(self, textvariable=self._suche).grid(row=0, column=0, sticky="ew", pady=(0, 4))

        rahmen = ttk.Frame(self)
        rahmen.grid(row=1, column=0, sticky="nsew")
        rahmen.columnconfigure(0, weight=1)
        rahmen.rowconfigure(0, weight=1)
        self._lb = tk.Listbox(rahmen, height=height, exportselection=False,
                              selectmode=tk.EXTENDED if multi else tk.SINGLE)
        sb = ttk.Scrollbar(rahmen, orient="vertical", command=self._lb.yview)
        self._lb.configure(yscrollcommand=sb.set)
        self._lb.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

        self._status = ttk.Label(self, foreground="#555555")
        self._status.grid(row=2, column=0, sticky="w", pady=(2, 0))

        if on_select:
            self._lb.bind("<<ListboxSelect>>", lambda e: self._auswahl_geaendert())
        if on_activate:
            self._lb.bind("<Double-Button-1>", lambda e: self._aktivieren())
            self._lb.bind("<Return>", lambda e: self._aktivieren())

        self.set_items(items)

    def set_items(self, items):
        """Ersetzt die durchsuchte Objektliste (Suchtext bleibt erhalten)."""
        self._items = list(items)
        self._filtern()

    def focus_search(self):
        self.winfo_children()[0].focus_set()

    def get_selected(self):
        return [self._shown[i] for i in self._lb.curselection()]

    def _passt(self, obj, begriffe):
        text = f"{self._id_of(obj)} {self._display(obj)}".lower()
        kompakt = text.replace(" ", "")  # "EF-L" soll auch "EF - L-GK1" finden
        return all(b in text or b in kompakt for b in begriffe)

    def _filtern(self):
        begriffe = self._suche.get().lower().split()
        self._shown = [o for o in self._items if self._passt(o, begriffe)]
        self._lb.delete(0, tk.END)
        for o in self._shown:
            self._lb.insert(tk.END, self._display(o))
        self._status.config(text=f"{len(self._shown)} von {len(self._items)} Treffern")

    def _auswahl_geaendert(self):
        auswahl = self.get_selected()
        if auswahl and self._on_select:
            self._on_select(auswahl[0])

    def _aktivieren(self):
        auswahl = self.get_selected()
        if auswahl and self._on_activate:
            self._on_activate(auswahl[0])
