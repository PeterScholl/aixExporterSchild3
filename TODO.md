# TODO

Erledigte Punkte wurden nach [TODO_erledigt.md](TODO_erledigt.md) ausgelagert.

## Plan: Ausschlüsse, eigene Objekte, Zusatzzuweisungen (Feature-Branch)

Alle drei Punkte landen im Dropdown "Dauerhafte Einstellungen", werden in `status.json` gespeichert, tauchen in der BESONDERHEITEN-Box von Auto auf und werden im README dokumentiert. Jeder Schritt wird einzeln umgesetzt, im Programm getestet und committet.

- [x] **Bug vorab: aufgeklappte Dropdowns bleiben im Vordergrund**, wenn man die Anwendung wechselt
  - Vermutete Ursache: Das Popup von `DropdownMenuButton` (`ui_widgets.py`) ist `-topmost` und schließt nur bei einem Klick *innerhalb* der App (`bind_all("<Button-1>")`) - ein Wechsel per Alt+Tab/Klick in ein anderes Programm schließt es nicht.
  - Lösungsansatz: Popup zusätzlich schließen, wenn das Hauptfenster den Fokus verliert bzw. minimiert wird (`<FocusOut>`/`<Unmap>` am Toplevel bzw. Prüfung per `after`), und `-topmost` nur solange das Popup offen ist beibehalten. Im Programm gegentesten (Alt+Tab, Klick auf anderes Fenster, Desktop anzeigen).
- [x] **Schritt 0 - Gemeinsames Such-/Auswahl-Widget** (Grundlage für 1-3)
  - Wiederverwendbares Widget in `ui_widgets.py`: Suchfeld + Trefferliste, filtert live nach Teilen des Namens **oder** der ID (Teilstring, Groß/Klein egal), Mehrfachauswahl, Anzeige z.B. `1234 - Muster, Max (EF)`.
  - Arbeitet auf einer beliebigen Objektliste (Schüler/Lehrer/Lerngruppen) mit einer Anzeige-Funktion je Typ.
- [x] **Schritt 1 - Schüler-Ausschlussliste**
  - Neues Attribut z.B. `self.schueler_ausschluss = {id: "Nachname, Vorname (Klasse)"}` (Namen-Schnappschuss mitspeichern, damit die Liste auch lesbar bleibt, wenn der Schüler nach dem Filtern nicht mehr in `self.schueler` steht).
  - Dialog "Schüler ausschließen" (Dauerhafte Einstellungen): Schüler über Schritt-0-Widget suchen, hinzufügen/entfernen.
  - Angewandt **zentral und früh** (nach `lerngruppenHolen`/`ergaenzeSchueler`, vor `idsSchuelerZuLerngruppen`), damit ausgeschlossene Schüler nirgends mehr auftauchen (Team-Präfix-Ermittlung, IDs prüfen, alle CSVs). Log-Zeile mit Anzahl + Namen, Eintrag in BESONDERHEITEN.
  - Offen: Ausgeschlossene, die in Schild nicht (mehr) vorkommen, in der Liste belassen und markieren?
- [ ] **Schritt 2 - Eigene Objekte (Schüler, Lehrer, Lerngruppen/"Kurse")**
  - Pflichtfelder je Typ anhand der echten Objekte in `status.json` festlegen; Dialog zum Anlegen/Ändern/Löschen; Speicherung z.B. `self.zusatz_objekte = {"schueler": [...], "lehrer": [...], "lerngruppen": [...]}`.
  - Beim Laden aus Schild zusammenführen: bei ID-Kollision **gewinnt der Schild-Eintrag**, das eigene Objekt wird nicht übernommen und der Nutzer bekommt eine deutliche Warnung ("bitte eigenen Eintrag mit ID x ändern").
  - Entschieden: IDs werden vom Nutzer **manuell** vergeben; der Dialog schlägt beim Anlegen die nächste freie ID ab 900000 vor (überschreibbar). Eindeutigkeit innerhalb der eigenen Objekte wird geprüft.
  - Entschieden: Die bestehende CSV-Funktion "Zusätzliche Schüler" bleibt unverändert **parallel** bestehen (sie hängt nur Zeilen an die `Student.csv` an, ohne Schild-Objekte/IDs).
- [ ] **Schritt 3 - Zusatzzuweisungen**
  - Neuer Menüpunkt "Zusatzzuweisungen": Liste von Einträgen `{lerngruppen_ids (nicht leer), schueler_ids (evtl. leer), lehrer_ids (evtl. leer)}`, Auswahl je Feld über das Schritt-0-Widget (ID und Name), auch eigene Objekte aus Schritt 2 wählbar.
  - Angewandt **nach** `idsSchuelerZuLerngruppen`/`idsLerngruppenZuLehrern` (fügt die Verknüpfungen in beide Richtungen hinzu), also im Auto-Ablauf als eigener protokollierter Schritt; Warnung bei nicht (mehr) existierenden IDs, ausgeschlossene Schüler (Schritt 1) werden ignoriert und gemeldet.
- [ ] **Abschluss:** README + TODO_erledigt aktualisieren, Auto-Bericht/BESONDERHEITEN um alle drei Einstellungen ergänzen.
