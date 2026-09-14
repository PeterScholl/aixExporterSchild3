# TODO – erledigt

Archiv abgeschlossener Punkte aus [TODO.md](TODO.md), ausgelagert am 2026-09-14, damit TODO.md
übersichtlich bleibt. Code-Kommentare, die auf "Schritt N, siehe TODO.md" verweisen, beziehen sich
auf die Schritte in diesem Archiv.

- [x] f-Strings finden, bei denen Anführungszeichen "doppelt" bzw. gleich sind (z.B. verschachtelte `f"...{x['y']}..."` mit gleichem Anführungszeichen-Typ innen und außen) – betraf `generator.py:406` und `generator.py:412` (Aufrufe mit `art="jahrgaenge"`/`art="klassen"` innerhalb eines f-Strings mit doppelten Anführungszeichen; vor Python 3.12 ein SyntaxError, z.B. auf Windows-Builds mit älterem Python). Behoben durch einfache Anführungszeichen innen.
- [x] Umstellung auf neues Format mit `Arbeitsgruppen;Cloud#Kurs;Cloud#Gruppe` (Format siehe [README.md](README.md#csv-import-format-für-mnspro-cloud)) – umgesetzt in Schritt 7, noch zu testen (siehe unten)
- [x] Ermittlung, welche Lerngruppe welcher Zielspalte (Arbeitsgruppe/Kurs/Gruppe) zugeordnet wird – Detailplanung + Umsetzung siehe unten (Schritte 1–7)
- [x] "Leere Lerngruppen löschen" – neuer Button `LeereLerngruppenLöschen` (Utility, kein Pflichtschritt), löscht Lerngruppen ohne Schüler und bereinigt Verweise bei Lehrern/Schülern (`idsLerngruppen`), im Lookup-Dict und bei verwaisten Kursart-Overrides. Methode `loescheLeereLerngruppen()` in `generator.py`, mit Sicherheitsabfrage (Vorschau der betroffenen Team-Bezeichnungen) vor dem Löschen. Voraussetzung: `idsSchuelerZuLerngruppen` muss vorher gelaufen sein, sonst FEHLER-Meldung statt Fehlklassifikation. Von Peter selbst im Programm getestet.

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

- [x] **Schritt 3 – Bezeichnungs-Muster (Regex)**
  - Neuer Listen-Editor `edit_bezeichnung_muster(self, master)` in `generator.py` (Stil wie `edit_jahrgangsteams`: direkte Mutation von `self.bezeichnung_muster`, kein separates Speichern) zum Pflegen von Regex-Mustern auf die Bezeichnung → Zielkategorie. Reihenfolge = Priorität, per "▲ nach oben"/"▼ nach unten" änderbar; Hinzufügen/Aktualisieren/Löschen mit Regex-Validierung (`re.compile`, Fehlermeldung statt Absturz bei ungültigem Muster).
  - **Live-Treffervorschau:** beim Tippen zeigt ein Label direkt, wie viele/welche aktuellen Lerngruppen das Muster träfe – zum Ausprobieren direkt im Programm, ohne Testskript.
  - Anwendung in `get_ziel_fuer_lerngruppe` vor der `kursartKuerzel`-Regel war bereits in Schritt 1 vorgesehen und unverändert.
  - Neuer Button **BezeichnungsMusterBearbeiten** (Utility, kein Pflichtschritt, da Muster optional/ergänzend sind) am Ende der Button-Liste ergänzt.

- [x] **Schritt 4 – Kontroll-/Vorschau-Funktion**
  - Neue Methode `zuordnung_uebersicht(self) -> str` in `generator.py`: listet je Zielkategorie (Arbeitsgruppe/Cloud#Kurs/Cloud#Gruppe) die betroffenen Lerngruppen auf, warnt vor nicht klassifizierten Lerngruppen (inkl. `kursartKuerzel`) und vor Team-Bezeichnungen, die in mehreren Zielkategorien gleichzeitig auftauchen.
  - Neuer Button **ZuordnungUebersicht** (ans Ende der Button-Liste ergänzt, nicht direkt vor die Export-Buttons verschoben, um nicht ungefragt die Reihenfolge erneut zu zerreißen – auf Wunsch kann das wie bei `KursartZuordnung` in Schritt 2 noch nachgezogen werden).
  - Ausgabe wie bei "Statistik anzeigen": Textfeld wird geleert und neu befüllt.
  - **Nachträglich behobene Lücke:** Lerngruppen mit `kursartKuerzel = null` (typischerweise normale Fachkurse) fielen bislang überall durch (`if lg.get("kursartKuerzel")`-Filter). Jetzt eigenes Pseudo-Kürzel `KEIN_KURSARTKUERZEL = "(ohne kursartKuerzel)"` in `get_ziel_fuer_lerngruppe`, `fehlende_kursart_zuordnungen`, `edit_kursart_zuordnung` und `zuordnung_uebersicht` berücksichtigt, mit Standard-Vorschlag "Kurs" in `KURSART_ZUORDNUNG_VORSCHLAG`.

- [x] **Schritt 5 – Besitzer-Markierung (`^`) für Kursleiter**
  - Checkbox "Besitzer markieren" **nicht** in `config_gui.py` (das ist nur die DB-Verbindungseinstellung), sondern im bereits existierenden Einstellungen-Dialog `open_settings_window` in `SchildMNSDataMatcher_GUI.py` (dort steht auch schon "Sonderzeichen ersetzen") – Standard: an, Persistenz über `self.besitzer_markieren`.
  - In `writeLuLCSV` (`generator.py`) beim Aufbau der Team-Liste aus `idsLerngruppen`: `^` wird vorangestellt, wenn die Lehrkraft laut `idsLehrer` der jeweiligen Lerngruppe Kursleiter ist und die Einstellung aktiv ist. Ergebnistext zeigt die Anzahl der markierten Zuordnungen.
  - **100-Besitzer-Grenze:** direkt in `writeLuLCSV` mitgezählt (`Counter` je Team-Bezeichnung) und als Warnung im Ergebnistext ausgegeben, falls ein Team mehr als 100 als Besitzer markierte Lehrkräfte hätte – dort ist die tatsächliche Owner-Zahl bekannt, nicht in der Lerngruppen-bezogenen `zuordnung_uebersicht` aus Schritt 4.

- [x] **Schritt 6 – Jahrgangsteams auf drei Kategorien erweitern**
  - `self.jahrgangsteams` von `{jahrgang: [Namen]}` auf `{jahrgang: {"arbeitsgruppe": [...], "kurs": [...], "gruppe": [...]}}` umgestellt (Default in `__init__` direkt im neuen Format: `"Lehrer": {"arbeitsgruppe": ["*"], ...}`, da `"*"` laut MNSpro-Doku speziell der Arbeitsgruppen-Platzhalter ist).
  - Neue Methode `normalisiere_jahrgangsteams()`: migriert alte flache Listen idempotent (`"*"` → `arbeitsgruppe`, alles andere → `kurs`), mit Hinweistext. Aufgerufen beim Laden (`load_state` in `SchildMNSDataMatcher_GUI.py`, Meldung im Textfeld) sowie defensiv in `edit_jahrgangsteams` und `_alle_jahrgangsteams`.
  - Neue Methode `_alle_jahrgangsteams(jahrgang)`: fasst alle drei Kategorien zu einer flachen Liste zusammen – Übergangslösung für den noch einspaltigen CSV-Export in `writeSuSCSV`/`writeLuLCSV` (echte Aufteilung folgt in Schritt 7).
  - `edit_jahrgangsteams`-Dialog: ein Eingabefeld je Zielkategorie (dynamisch aus `self.ziel_spalten` erzeugt), Listbox zeigt jetzt eine Zusammenfassung je Jahrgang.
  - README-Abschnitt "Jahrgangsteams und LehrerTeams" aktualisiert.

- [x] **Schritt 7 – Export-Funktionen umstellen**
  - `writeSuSCSV`/`writeLuLCSV` in `generator.py`: statt einer `Gruppen`-Spalte werden jetzt drei Spalten gemäß `self.ziel_spalten` befüllt – Jahrgangsteams je Kategorie vorbelegt, dann pro Lerngruppe via `get_ziel_fuer_lerngruppe` in die passende Spalte einsortiert.
  - Kopfzeile jetzt `ReferenzId;Vorname;Nachname;Klasse(n);Arbeitsgruppen;Cloud#Kurs;Cloud#Gruppe` (Spaltennamen kommen aus `self.ziel_spalten.values()`, also automatisch konsistent mit Kursart-Zuordnung/Übersicht). Ziel-Schuljahr bleibt außen vor (kein CSV-Feld, siehe README).
  - Lerngruppen ohne ermittelbare Zielkategorie werden übersprungen statt geraten – Anzahl und Beispiele landen im Ergebnistext (Verweis auf ZuordnungUebersicht/KursartZuordnung).
  - **Kein Umschalter „klassisch/neu"** ergänzt – das alte Format wird direkt abgelöst, da für Zeugnisdaten ab MNSpro 2026 ohnehin auf Cloud-Gruppen umgestellt werden muss. Bei Bedarf leicht nachrüstbar.
  - README aktualisiert (aktuelles Format, Hinweis zur Kursart-Zuordnung).

- [x] **Schritt 8 – Doku & Aufräumen**
  - README.md um alle neuen Buttons/Schritte ergänzt: Kursart-Zuordnung, Bezeichnungs-Muster (Regex), Besitzer-Markierung (^), Kontrollfunktionen (ListeTeamBez/ZuordnungUebersicht/LeereLerngruppenLöschen), erweiterte Jahrgangsteams.
  - Veraltete Passagen bereinigt: "altes Format"-Beschreibung durch das jetzt tatsächlich erzeugte Format ersetzt, Verweis auf "offenen TODO-Punkt" durch konkrete Erklärung (KursartZuordnung/BezeichnungsMusterBearbeiten) ersetzt, Pflichtpfad-Kette und Farb-Legende (Unverändert-Buttons) aktualisiert.
  - TODO.md-Punkte abgehakt (dieser Punkt hier).

## Status: Schritte 1–8 abgeschlossen

Die Umstellung auf das neue MNSpro-Cloud-Format (`Arbeitsgruppen`/`Cloud#Kurs`/`Cloud#Gruppe`) inkl. konfigurierbarer Zuordnungslogik ist damit vollständig umgesetzt und exportiert.

## Weitere erledigte Punkte (nach der Umstellung, ab 2026-09)

- [x] Passwort wird nicht mehr in `status.json` gespeichert (`save_state()` entfernt es vor dem Schreiben und stellt es danach in der laufenden Sitzung wieder her). Beim Laden (`load_state()`) wird bei fehlendem Passwort automatisch der Verbindungseinstellungen-Dialog geöffnet, Cursor direkt im leeren Passwortfeld (`configValues(..., focus_password=True)` / `show_config_gui(..., focus_password=True)`). Enter im Passwortfeld schließt den Dialog wie "Speichern & Schließen" (`config_gui.py`, `e_pass.bind("<Return>", ...)`).
- [x] Buttons in "Werkzeuge" und "Dauerhafte Einstellungen" ausgelagert - nur noch der eigentliche Ablauf-Pfad (Verbindung → Daten holen → Zuordnen → Export) steht als Grid-Buttons im Hauptfenster. Umgesetzt als zwei `DropdownMenuButton`-Widgets (`ui_widgets.py`) in einer Toolbar unterhalb der Menüleiste, NICHT als echte `tk.Menu`-Cascades: Auf diesem Windows/Tk-8.6-Setup feuert `<<MenuSelect>>` bei echtem Maus-Hover nicht zuverlässig (per Testskript verifiziert), wodurch sich in nativen Menüs keine Tooltips pro Eintrag zeigen ließen. `DropdownMenuButton` baut die Einträge stattdessen aus normalen `tk.Button`-Widgets in einem eigenen Popup - kompatibel zur bestehenden `ToolTip`-Klasse und einheitlich in `self.buttons` für die Button-Führungsfarben verwaltet.
- [x] Button **Auto** ergänzt (`Generator.auto_ablauf()` in `generator.py`): arbeitet die `REQUIRED_CHAIN` automatisch ab, protokolliert JEDEN Schritt (auch bereits erledigte, mit "✔️ ... (bereits erledigt)"), startet "Lerngruppen holen" dabei aber immer frisch von der SVWS-Datenbank statt sich auf ggf. veraltete, aus `status.json` geladene Daten zu verlassen - nachgelagerte Schritte erkennen frische Daten automatisch als "noch nicht erledigt" und laufen dadurch von selbst neu mit. Bricht gezielt ab (⛔), wenn eine manuelle Entscheidung nötig ist: unvollständige Kursart-Zuordnung, oder eine für Schüler/Lehrer noch nicht in `status.json` gespeicherte Referenz-ID-Zuordnung. Am Ende steht immer eine "BESONDERHEITEN"-Übersicht über aktuell wirksame Dauerhafte Einstellungen (TeamBez-Rewrite, Jahrgangsteams, Teams nicht erstellen, Bezeichnungs-Muster, eigenes Server-Zertifikat). Hängt seinen Bericht an das Report-Textfeld an (löscht es nicht) und scrollt ans Ende.
- [x] Referenz-ID-Zuordnungen (Schüler wie Lehrer) werden jetzt in `self.referenz_id_mapping` gespeichert (landet damit auch in `status.json`) - `import_referenz_ids()` fragt bei vorhandener gespeicherter Zuordnung vor dem Dateiauswahl-Dialog "Daten aus JSON verwenden"/"Datei öffnen"/"Abbrechen".
- [x] Neuer Eintrag **"Zusätzliche Schüler"** im Dropdown "Dauerhafte Einstellungen" (`edit_zusaetzliche_schueler()` in `generator.py`): liest eine CSV-Datei im selben Format wie die Ausgabe von `schueler_csv` ein und speichert deren Zeilen in `self.zusaetzliche_schueler_csv_zeilen` (landet damit auch in `status.json`). `writeSuSCSV()` hängt diese Zeilen beim Erzeugen der echten `Student.csv` automatisch an (nicht bei `StudentExternal.csv` oder den "Schüler aufräumen"-Sonderdateien) und meldet die Anzahl deutlich im Log (`➕ N zusätzliche Schüler ... angehängt`).
- [x] Die drei CSV-Exporte (`schueler_csv`/`sus_extern_csv`/`lehrer_csv`) werden aus `auto_ablauf()` wieder herausgenommen - bleiben ein bewusster, manueller letzter Schritt über die jeweiligen Buttons (z.B. um vorher nochmal ZuordnungUebersicht zu prüfen). Auto protokolliert stattdessen `➡️ ... - bitte manuell über den passenden Button erstellen` bzw. `✔️ ... (bereits erledigt)`, und die Abschluss-Meldung unterscheidet jetzt zwischen "komplett durchgelaufen" und "Vorbereitung abgeschlossen, Export steht noch aus" (`_auto_bericht(..., export_ausstehend=...)`).
- [x] Button `show_objekt_by_id` in **"Suche"** umbenannt (`oeffne_suche()` in `SchildMNSDataMatcher_GUI.py`): weiterhin exakte ID-Suche als Standard, neu eine Checkbox "Regex" - durchsucht dann die komplette JSON-Serialisierung jedes Objekts eines Typs (findet Treffer in jedem Feld, auch verschachtelt, ohne das genaue Feld zu kennen). Bei mehreren Treffern zeigt das Textfeld nur noch ein Objekt auf einmal mit "◀ Vorheriges"/"Nächstes ▶" zum Durchblättern statt alle auf einmal zu dumpen.
- [x] Korrekte Fehlermeldung bei Server-Zertifikats-Diskrepanz: `svwsapi.py` bekommt eine neue Exception `ZertifikatsFehler` und einen zentralen `_get()`-Wrapper um `requests.get()` (an allen Aufrufstellen genutzt), der eine `requests.exceptions.SSLError` in eine klare, verständliche Meldung mit Abhilfe-Hinweis übersetzt ("Serverzertifikat laden" erneut ausführen, mehrzeilig formatiert und mit dem Hinweis, dass der Button unter "Dauerhafte Einstellungen" zu finden ist). `generator.py` bekommt `self.letzter_verbindungsfehler`, gesetzt von `initAbschnittsID()`/`lerngruppenHolen()` bei einem `ZertifikatsFehler`; die GUI-Buttons "Abschnitts-ID holen"/"Lerngruppen holen" sowie `auto_ablauf()` zeigen diese konkrete Meldung statt eines generischen "siehe Console"-Texts. Bestätigt: "Serverzertifikat laden" überschreibt die vorhandene `server.pem` bereits korrekt (kein Exists-Check, der das verhindern würde) - dieser Teil war schon erfüllt. Mit gemocktem `SSLError` verifiziert und von Peter zusätzlich live mit einem manipulierten `server.pem` gegen sein lokales selbstsigniertes Test-Setup gegengetestet.
- [x] README.md rundum aktualisiert: neuer Abschnitt zum Aufbau des Hauptfensters (Button-Grid/"Werkzeuge"/"Dauerhafte Einstellungen"), neuer Abschnitt zum **Auto**-Button, TeamBez-Rewrite dokumentiert (war komplett undokumentiert), Zusätzliche Schüler dokumentiert, Suche (Regex + Durchblättern) dokumentiert, Referenz-ID-JSON-Cache ("Daten aus JSON verwenden") ergänzt, Passwort-nie-gespeichert-Hinweis ergänzt, Zertifikats-Diskrepanz-Hinweis ergänzt, Button-Führung-Abschnitt und Fundort-Angaben alter Abschnitte (Jahrgangsteams, ErgänzeLehrerAusDB, generateLookupDicts, Kontrollfunktionen) auf die neuen Dropdown-Standorte aktualisiert.
- [x] Realer End-to-End-Test des MNSpro-Cloud-Exports (Arbeitsgruppen/Cloud#Kurs/Cloud#Gruppe) im Programm - war vom Nutzer bereits als erledigt markiert, aber noch nicht aus TODO.md ausgelagert.
