# TODO

- [x] f-Strings finden, bei denen Anführungszeichen "doppelt" bzw. gleich sind (z.B. verschachtelte `f"...{x['y']}..."` mit gleichem Anführungszeichen-Typ innen und außen) – betraf `generator.py:406` und `generator.py:412` (Aufrufe mit `art="jahrgaenge"`/`art="klassen"` innerhalb eines f-Strings mit doppelten Anführungszeichen; vor Python 3.12 ein SyntaxError, z.B. auf Windows-Builds mit älterem Python). Behoben durch einfache Anführungszeichen innen.
- [ ] Umstellung auf neues Format mit `Arbeitsgruppen;Cloud#Kurs;Cloud#Gruppe` (Format siehe [README.md](README.md#csv-import-format-für-mnspro-cloud))
- [ ] Ermittlung, welche Lerngruppe welcher Zielspalte (Arbeitsgruppe/Kurs/Gruppe) zugeordnet wird – Detailplanung siehe unten

## Detailplanung: Zuordnung Lerngruppe → Arbeitsgruppe / Kurs / Gruppe

Ziel: Für jede Lerngruppe (und jeden Jahrgangsteam-Eintrag) automatisch, aber konfigurierbar entscheiden, in welche der drei Zielspalten (`Arbeitsgruppen`, `Cloud#Kurs`, `Cloud#Gruppe`) sie beim Export einsortiert wird – mit Kontrollmöglichkeit vor dem eigentlichen CSV-Export.

### 1. Regel-Engine (konfigurierbar)

- Geordnete Liste von Zuordnungsregeln (Reihenfolge = Priorität, erste passende Regel gewinnt), analog zu den bestehenden Settings `kursarten_ohne_klasse` / `kursarten_nur_mit_jahrgang` in `config_gui.py`.
- Match-Kriterien pro Regel:
  - `kursartKuerzel` (Liste von Kürzeln, wie bisher schon für die Prefix-Logik verwendet)
  - optional zusätzlich Fach-Kürzel zur Verfeinerung (z.B. eine Kursart kann je nach Fach unterschiedlich behandelt werden)
  - Ziel: `Arbeitsgruppe` | `Kurs` | `Gruppe` | `Ignorieren` (letzteres = wie bestehendes `noTeams`)
- **Wichtig – klare Trennung von bestehenden Settings:** `kursarten_ohne_klasse` und `kursarten_nur_mit_jahrgang` steuern weiterhin nur den *Namens-Prefix* (Klasse/Jahrgang bei der Teambezeichnung). Die neue Regel-Engine ist eine unabhängige, zusätzliche Konfiguration für die *Zielspalte*. Beide Konfigurationen dürfen nicht vermischt werden.
- **Fallback:** Für `kursartKuerzel`, die von keiner Regel erfasst sind, gibt es keinen stillschweigenden Default – sie werden explizit als "nicht klassifiziert" markiert und in der Kontrollfunktion (siehe unten) sichtbar aufgelistet.
- **Manuelle Einzel-Overrides:** Zusätzlich zur regelbasierten Zuordnung sollte es (analog zum bestehenden `noTeams`-Mover-Dialog in `config_gui.py`) eine Möglichkeit geben, einzelne Lerngruppen-IDs abweichend von der Regel manuell einer Zielspalte zuzuweisen, für Ausnahmefälle, die sich nicht sauber über `kursartKuerzel`/Fach abbilden lassen.

### 2. Kontrolle/Vorschau der Zuordnung

- Neue Funktion/Button (ähnlich "Statistik anzeigen"), die zeigt:
  - pro `kursartKuerzel` (+ Fach) die ermittelte Zielspalte
  - Liste aller "nicht klassifizierten" Lerngruppen
  - Warnung bei doppelten Team-Bezeichnungen, die in unterschiedlichen Zielspalten landen (Arbeitsgruppe/Kurs/Gruppe sind getrennte Namensräume – gleiche Bezeichnung in zwei Spalten kann in MNSpro zu Verwechslungen führen)
- Sollte als eigener Schritt in die Button-Führung (`WorkflowStep`/`OptionalStep` in `generator.py`) aufgenommen werden, mit Farbfeedback wie bei den anderen Schritten.

### 3. Jahrgangsteams erweitern

- Aktuell: `self.jahrgangsteams = {jahrgang: [Namen]}` (eine einzige Liste pro Jahrgang, siehe `generator.py:709` `edit_jahrgangsteams`).
- Neu: pro Jahrgang drei getrennte Listen:

  ```python
  jahrgangsteams = {
      "EF": {"arbeitsgruppen": [...], "kurse": ["Abi28"], "gruppen": [...]},
      "Lehrer": {"arbeitsgruppen": [...], "kurse": [...], "gruppen": ["*"]},
  }
  ```

- GUI `edit_jahrgangsteams` entsprechend um zwei weitere Listen/Spalten erweitern.
- **Migration:** Bestehende `status.json`-Daten (alte flache Liste pro Jahrgang) müssen beim Laden abwärtskompatibel erkannt und automatisch umgesetzt werden (z.B. in `kurse` einsortiert), sonst reißt es vorhandene Konfigurationen.

### 4. Besitzer-Markierung (`^`) für Kursleiter

- Aktuell wird `^` nur für Klassenleitungen gesetzt (`generator.py:593`), nicht für Lehrkräfte, die einen Kurs unterrichten (`idsLehrer` einer Lerngruppe). Damit hätten neue `Cloud#Kurs`/`Cloud#Gruppe`-Einträge ggf. keinen Besitzer.
- Zu klären: Werden alle Lehrkräfte einer Lerngruppe als Besitzer markiert, oder nur eine ausgezeichnete Kursleitung (falls die API das unterscheidet)?
- Kontrollpunkt: 100-Besitzer-Grenze pro Kurs/Gruppe laut MNSpro-Doku – bei sehr großen Jahrgangsteams (`^` in `jahrgangsteams`) im Blick behalten.

### 5. Anpassung der Export-Funktionen

- `writeSuSCSV`/`writeLuLCSV` in `generator.py` müssen statt einer Spalte `Gruppen` drei Spalten (`Arbeitsgruppen`, `Cloud#Kurs`, `Cloud#Gruppe`) befüllen, basierend auf der Regel-Engine.
- Ziel-Schuljahr ist laut MNSpro-Doku **keine** CSV-Spalte, sondern wird separat beim Import in der MNSpro-Cloud-Oberfläche ausgewählt – muss also nicht in die CSV geschrieben werden, nur als Hinweis im Tool dokumentiert sein.

### Offene Fragen – beantwortet

- **Sollen Kursleiter grundsätzlich als Besitzer (`^`) markiert werden?**
  Antwort: Ja, per Einstellung steuerbar (Checkbox "Besitzer markieren", Standard: an). Alle Lehrkräfte einer Lerngruppe (`idsLehrer`) werden bei aktivierter Einstellung als Besitzer (`^`) markiert.
- **Wie mit "nicht klassifizierten" `kursartKuerzel` umgehen?**
  Antwort: Es gibt nur wenige verschiedene `kursartKuerzel` – der Nutzer soll für alle vorkommenden Werte problemlos eine Klassifizierung eintragen können, die dann in der JSON (status.json) gespeichert wird. Also: vollständige Erfassung erzwingen statt stiller Fallback.
- **Reicht `kursartKuerzel` (+ optional Fach) als Kriterium?**
  Antwort: Zusätzlich sollen Bezeichnungs-Muster (Regex) unterstützt werden, um einzelnen Lerngruppen unabhängig von `kursartKuerzel` eine eigene Zielkategorie zuweisen zu können. Diese Muster-Regeln werden **vorrangig vor** den allgemeinen `kursartKuerzel`-Regeln ausgewertet.

Daraus ergibt sich folgende **Prioritätsreihenfolge** bei der Zuordnung einer Lerngruppe:

1. Manueller Einzel-Override (Lerngruppen-ID) – höchste Priorität
2. Bezeichnungs-Muster (Regex, in konfigurierter Reihenfolge, erstes Match gewinnt)
3. `kursartKuerzel`-Zuordnungstabelle (muss für alle vorkommenden Kürzel vollständig gepflegt sein)

**Designprinzip (wegen unklarer Zukunft von `Arbeitsgruppen` in MNSpro):** Die drei Zielkategorien werden nicht als verstreute String-Literale im Code verwendet, sondern zentral als eine Zuordnungstabelle Ziel-Schlüssel → CSV-Spaltenname (z.B. `{"arbeitsgruppe": "Arbeitsgruppen", "kurs": "Cloud#Kurs", "gruppe": "Cloud#Gruppe"}`) definiert. Fällt `Arbeitsgruppen` künftig weg oder wird umbenannt, ändert sich nur diese eine Stelle.

## Umsetzungsplan (Schritte)

Reihenfolge zum gemeinsamen Abarbeiten, jeder Schritt einzeln umsetz- und testbar. Persistenz ist unkompliziert, da `status.json` generisch über `obj.__dict__` gespeichert/geladen wird ([SchildMNSDataMatcher_GUI.py:266](SchildMNSDataMatcher_GUI.py#L266) `save_object_to_json`, [:297](SchildMNSDataMatcher_GUI.py#L297) `load_object_from_json`) – neue `self.*`-Attribute in `Generator.__init__` werden also automatisch mitgespeichert.

- [x] **Schritt 1 – Datenmodell & Zuordnungslogik in `generator.py`**
  - Neue Attribute in `Generator.__init__`: `self.ziel_spalten`, `self.kursart_zuordnung`, `self.bezeichnung_muster`, `self.zuordnung_overrides`, `self.besitzer_markieren = True`.
  - Neue Methode `get_ziel_fuer_lerngruppe(self, lg) -> str | None` (Priorität Override → Muster → kursartKuerzel) sowie `fehlende_kursart_zuordnungen(self) -> list` (Grundlage für Schritt 2).
  - Smoke-Test in `test_ziel_zuordnung.py` (`python test_ziel_zuordnung.py`, ohne pytest/DB/GUI) – läuft grün.

- [x] **Schritt 2 – Kursart-Zuordnungsdialog (Pflichtschritt)**
  - Neue Funktion `edit_kursart_zuordnung(self, master)` in `generator.py`: sammelt alle in `self.lerngruppen` vorkommenden `kursartKuerzel` (inkl. Anzahl betroffener Lerngruppen), zeigt sie mit einer Combobox je Zeile zur Auswahl der Zielkategorie, vorbelegt mit vorhandener `self.kursart_zuordnung` bzw. ersatzweise `KURSART_ZUORDNUNG_VORSCHLAG` (Startvorschlag, basierend auf den in `status.json` gefundenen Kürzeln: `AGGT`/`EGS1`/`FOGT` → Arbeitsgruppe, `GK`/`LK`/`PUT`/`WPII` → Kurs). Übernommen wird erst mit "Speichern & Schließen".
  - Neuer Button **KursartZuordnung** im Hauptfenster (ersetzt einen der bisherigen „-ohne Funktion-"-Plätze) sowie neuer Pflichtschritt `WorkflowStep.KURSART_ZUORDNUNG` in der `REQUIRED_CHAIN` (grün, bis `fehlende_kursart_zuordnungen()` leer ist), eingeordnet nach TeamBezErstellen. Pflichtpfad-Kette in der README aktualisiert.
  - Smoke-Test in `test_ziel_zuordnung.py` erweitert (prüft den neuen Pflichtschritt vor/nach vollständiger Zuordnung) – läuft grün; zusätzlich Dialog einmalig headless testweise geöffnet (keine Exceptions).
  - **Hinweis:** Die gespeicherte Zuordnung fließt noch nicht in den eigentlichen CSV-Export ein – das folgt erst mit Schritt 7.
  - **Nachträglich (auf Wunsch):** Button-Reihenfolge in `SchildMNSDataMatcher_GUI.py` angepasst – `KursartZuordnung` steht jetzt direkt nach `TeamBezErstellen` (Zeilenanfang der Folgezeile im Button-Grid), statt am Ende. `ToolTip` nach `ui_widgets.py` ausgelagert (von `generator.py` und `SchildMNSDataMatcher_GUI.py` gemeinsam genutzt); im Zuordnungsdialog zeigt Hover über einem `kursartKuerzel` jetzt die zugehörigen Team-Bezeichnungen (`_teambez_beispiele_je_kursart`), damit z.B. klar wird, wofür `FOGT` steht.
  - Ab jetzt: neue, im Programm testbare Funktionen werden nicht mehr zusätzlich in eigene Testskripte gegossen – der Nutzer testet UI-nahe Schritte lieber direkt im Programm.

- [ ] **Schritt 3 – Bezeichnungs-Muster (Regex)**
  - Einfacher Listen-Editor (ähnlich `edit_jahrgangsteams`) zum Pflegen von `self.bezeichnung_muster`: Pattern, Zielkategorie, Reihenfolge per Verschieben.
  - Anwendung in `get_ziel_fuer_lerngruppe` vor der `kursartKuerzel`-Regel (bereits in Schritt 1 vorgesehen, hier nur die GUI dazu).

- [ ] **Schritt 4 – Kontroll-/Vorschau-Funktion**
  - Neue Funktion (z.B. `zuordnung_uebersicht`), die je Zielkategorie die betroffenen Lerngruppen auflistet, "nicht klassifizierte" Fälle sowie doppelte Bezeichnungen über Zielkategorien hinweg warnt.
  - Als Button ergänzen, idealerweise direkt vor den Export-Buttons nutzbar.

- [ ] **Schritt 5 – Besitzer-Markierung (`^`) für Kursleiter**
  - Checkbox "Besitzer markieren" in `config_gui.py` (Standard: an), Persistenz über `self.besitzer_markieren`.
  - In `writeLuLCSV` beim Aufbau der Team-Liste aus `idsLerngruppen`: bei aktivierter Einstellung `^` voranstellen, wenn die Lehrkraft in `idsLehrer` der jeweiligen Lerngruppe steht.
  - Kontrollhinweis auf die 100-Besitzer-Grenze bei sehr großen Gruppen (z.B. im Ergebnistext der Kontrollfunktion aus Schritt 4).

- [ ] **Schritt 6 – Jahrgangsteams auf drei Kategorien erweitern**
  - `self.jahrgangsteams` von `{jahrgang: [Namen]}` auf `{jahrgang: {"arbeitsgruppe": [...], "kurs": [...], "gruppe": [...]}}` umstellen.
  - Migrationscode beim Laden: alte flache Liste automatisch (z.B. nach `"kurs"`) überführen, mit Hinweis im Ergebnistext.
  - `edit_jahrgangsteams`-Dialog um die zusätzlichen Kategorien erweitern.

- [ ] **Schritt 7 – Export-Funktionen umstellen**
  - `writeSuSCSV`/`writeLuLCSV`: statt einer `Gruppen`-Spalte drei Spalten gemäß `self.ziel_spalten` befüllen (Jahrgangsteams je Kategorie vorbelegen, dann pro Lerngruppe via `get_ziel_fuer_lerngruppe` einsortieren).
  - Kopfzeile entsprechend anpassen; Ziel-Schuljahr bleibt außen vor (kein CSV-Feld, siehe README).
  - Bestehendes altes Format ggf. als Option erhalten (Umschalter „klassisch/neu"), falls noch übergangsweise benötigt.

- [ ] **Schritt 8 – Doku & Aufräumen**
  - README.md (Bedienung, Pflichtpfad-Kette) um die neuen Schritte ergänzen.
  - TODO.md-Punkte abhaken.

Vorschlag: Wir beginnen mit **Schritt 1**, da alle weiteren Schritte darauf aufbauen.
