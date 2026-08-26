# Anleitung zur Verwendung dieses Tools

**ACHTUNG** Dies ist ein Werkzeug kein fertiges Programm. Für Fragen zur Nutzung kann mir gerne eine Nachricht geschrieben werden.

## Quickstart

Exe-Datei herunterladen und starten - diese verbindet sich mit dem Nightly-Server von svws-nrw.de und dem Schema GymAbiLite. Danach einfach die Buttons in der Reihenfolge links oben beginnend ausprobieren.

## normaler Programmstart

Einfach **SchildMNSDataMatcher_GUI.py** bzw die Exe starten.

**WARNUNG** Das Serverzertifikat wird im falle eines self-signed Zertifikats automatisch heruntergeladen, wenn es nicht existiert - ggf. die Datei ``server.pem`` prüfen.

Eine ``status.json`` - Datei wird automatisch angelegt. Wenn mal etwas nicht wie erwartet läuft, vielleicht auch mal in die Console schauen.

Für einen Test ohne eigenen SVWS-Server können folgende Daten unter dem Button Verbindungseinstellung verwendet werden (Standard-Programmvorgaben)

````bash
    "host": "nightly.svws-nrw.de",
    "schema": "GymAbiLite",
    "username": "admin",
    "password": "",
    "jahr": 2018,
    "abschnitt": 1,
````

## Bedienung

### Konfiguration und Daten werden gemeinsam gesichert

Die Daten werden in der Datei status.json gespeichert. In der Datei finden sich die Daten zu Schüler, Kursen, der Datenbankverbindung und noch mehr. Für die schnellere Bearbeitung der Daten werden lookup-Dictionaries erstellt, die zu den jeweiligen IDs von Schülern, Lehreren oder Lerngruppen direkt auf die Objekte verweisen. Diese werden nicht gespeichert und müssen also ggf. nach dem Laden über den entsprechenden Button wieder erstellt werden.

### Verbindung zur Schild-Datenbank herstellen

Dazu den Button Verbindungseinstellungen betätigen und insbesondere die Datenbankverbindungseinstellungen korrekt setzen. Ob dies erfolgreich war kann über den Button *Abschnitts-ID holen* geprüft werden.
Falls es Schwierigkeiten mit der Authentifizierung des Zertifikats gibt, kann im Datei-Menü unter Einstellungen die Verifizierung des Zertifikates abgeschaltet werden oder mittels server.pem wird das Serverzertifkat (sofern nicht vorhanden) in die Datei server.pem heruntergeladen. Wenn es ein self-signed Zertifikat ist, funktioniert die Verifizierung ab dann.

Dieser holt aus der Datenbank die ID des in der Verbindung eingestellten Lernabschnitts (z.B. 2025 Abschnitt 1). Rückmeldungen werden in der Regel in dem Textfeld des GUIs angezeigt.

### Lerngruppen holen

Wenn die Verbindung steht sollten die Lerngruppen geholt werden. Das Programm nutzt dazu die api (Swagger-UI, ...) von Schild3 (Getestet mit Version 1.10 des SVWS-Servers)
Mit Statistik anzeigen erhält man einen Überblick über das was so an Daten geholt worden ist. Es werden auch aus den wichtigsten Objekten zufällige Elemente angezeigt.
*Aktuell wird automatisch die Lernplattform-ID 1 (lms.logineo) verwendet*

### Kontrolle des aktuellen Datenbestandes mit Statistik anzeigen

Über Statistik anzeigen kann man auch prüfen, welche Operationen schon erfolgt sind, also z.B. ob die lerngruppen die idsSchueler erhalten haben (Button idsSchuelerZuLerngruppen) oder ob die Lerngruppen TeamBezeichnungen erhalten haben

### LookUp-Dicts generieren

Falls mal eine Funktion nicht richtig ausgeführt wird, könnte es daran liegen, dass die Lookup-Dictionaries noch nicht erstellt wurden, das kann über diesen Button nachgeholt bzw. nach Laden erneut durchgeführt werden.

### Den Lerngruppen die Schüler-IDs zuweisen

Dieser Schritt ist ein Zwischenschritt um die Teamsbezeichnungen zu erstellen. Je nach Lerngruppe erhält die Teambezeichnung z.B. die Klasse oder den Jahrgang als prefix. Z.B. wird in einer Klasse der Sekundarstufe I die Klassenbezeichnung dem Fach Mathematik vorangestellt. In der Sek II wird die Jahrgangsbezeichnung (z.B. EF) als prefix voran gestellt. Bei AGs wird kein prefix erstellt. Um diese Prefixe zu Bestimmen wird hier jeder Lerngruppe die Schülermenge zugewiesen

### Team - Bezeichnungen erstellen

Mit diesem Button wird in jeder Lerngruppe das Attribut **teamBez** erstellt. Dazu können verschieden Kursarten in der Verbindungseinstellung gewählt werden um bei diesem Vorgang die korrekten prefixe zu ermitteln.

Bei der Erstellung der Teamnamen wird bei Klassenteams und Jahrgangsteams geprüft ob alle Schüler aus einer Klasse bzw. einem Jahrgang sind. Das ist hilfreich, da fehlerhafte Kurszuordnungen in Schild so entdeckt werden können.

Hinweis: Ob der Vorgang erfolgreich oder sinnvoll war, kann dann auch z.B. über Statistik erstellen geprüft werden oder man speichert und schaut sich status.json an.

### Kursart-Zuordnung (Arbeitsgruppe / Kurs / Gruppe)

Für das neue MNSpro-Cloud-Format (siehe unten) muss für jede vorkommende Kursart (`kursartKuerzel`) festgelegt werden, ob Lerngruppen dieser Kursart beim Export als `Arbeitsgruppen`, `Cloud#Kurs` oder `Cloud#Gruppe` behandelt werden. Der Button **KursartZuordnung** öffnet dazu einen Dialog mit allen aktuell vorkommenden Kürzeln (inkl. Anzahl betroffener Lerngruppen) und je einem Auswahlfeld für die Zielkategorie. Als Startvorschlag ist eine Vorbelegung hinterlegt, die aber erst mit "Speichern & Schließen" übernommen wird.

Der Button ist Teil der Pflicht-Button-Führung (grün, bis für alle vorkommenden Kürzel eine Zuordnung gespeichert ist).

Diese Zuordnung fließt direkt in `schueler_csv`/`sus_extern_csv`/`lehrer_csv` ein: Lerngruppen ohne (noch) ermittelbare Zielkategorie werden beim Export übersprungen und im Ergebnistext aufgeführt, statt versehentlich in die falsche Spalte zu landen.

### Bezeichnungs-Muster (Regex)

Reicht die Zuordnung über `kursartKuerzel` nicht aus (z.B. weil eine Kursart je nach Bezeichnung mal Kurs, mal Gruppe sein soll), öffnet der Button **BezeichnungsMusterBearbeiten** einen Dialog für Regex-Muster auf die Bezeichnung einer Lerngruppe. Diese Muster werden **vor** der `kursartKuerzel`-Regel ausgewertet (Reihenfolge in der Liste = Priorität, erstes Match gewinnt) und lassen sich per ▲/▼ umsortieren. Beim Tippen zeigt eine Live-Vorschau sofort, wie viele/welche aktuellen Lerngruppen das Muster träfe.

### ReferenzIDs zuweisen

Den Schülern (und über den anderen Button den Lehreren) sollten für die Verwaltung in Teams und MNSpro Referenz-IDs zugewiesen werden. Leider gibt der SVWS-Server (aus Datenschutzgründen?) die oft verwendete GUID nicht über die Schnittstelle (API) raus. Daher kann sie z.B. direkt aus Schild3 exportiert werden (Interne ID und eindeutige ID). Die dabei entstandene CSV-Datei (evtl. txt in csv umbenenen) kann hier eingelesen werden und jedem Schüler wird dann entsprechend die GUID als ReferenzId für Teams bzw. MNSpro zugewisen.

Bei den Lehrern gibt es keine eindeutige ID, daher wird hier das kuerzel als Zuordnung verwendet. Aus Schild3 muss also eine csv-Datei mit Kürzel und eindeutiger ID (GUID) exportiert werden.

### SchildID als Referenz ID

Als Alternative kann auch die Schild-ID als Referenz-ID genutzt werden. Es sollte jedoch jeder Schüler eine ReferenzID haben, bevor die Export-Datei generiert wird.

### Jahrgangsteams und LehrerTeams

Manchmal möchte man den Schülern eines Jahrgangs noch Teams zuweisen, z.B. der EF ein Team Abi28 oder dem Jahrgang 9 und 10 ein BO-Team. Dies kann in diesem Dialog erfolgen und Schüler aus dem Jahrganag erhalten dann beim Export dieses Team bzw. auch Teams.

Seit der Umstellung auf das neue MNSpro-Cloud-Format gibt es dafür drei getrennte Eingabefelder – eines je Zielkategorie (Arbeitsgruppen / Cloud#Kurs / Cloud#Gruppe, siehe [CSV-Import-Format für MNSpro Cloud](#csv-import-format-für-mnspro-cloud)). Ein alter Jahrgangsteams-Eintrag aus einer früheren `status.json` wird beim Laden automatisch migriert (Hinweis erscheint im Textfeld).

Besonders ist hier das Team für den Jahrgang **Lehrer**. Dieser Jahrgang wird allen Lehrern zugeordnet. Hier kann man im Feld **Arbeitsgruppen** z.B. `*` eintragen, um einzustellen, dass bereits vorhandene Arbeitsgruppen der Nutzer erhalten bleiben (siehe MNSpro-Doku zum `*`-Platzhalter).

### Lehrer ergänzen

Aktuell (22.08.2025) sind in dem Lerngruppenexport nicht alle Lehrer enthalten - ich habe diese über einen Anknüpfungspunkt der API ergänzt. Lehrer die nicht in dem Lerngruppenexport vorhanden sind aber in lerngruppen referenziert werden, werden dann bei lehrern ergänzt. Dann muss natürlich wieder die Referenz-ID zugewiesen werden usw.

### Besitzer-Markierung (^) für Kursleiter

Beim Export von `lehrer_csv` werden Lehrkräfte automatisch mit `^` als Besitzer der Lerngruppen markiert, die sie laut `idsLehrer` unterrichten (analog zur bestehenden `^`-Markierung bei Klassenleitungen). Das lässt sich über die Checkbox **"Besitzer markieren"** im Einstellungen-Dialog (Datei-Menü) abschalten, Standard ist an. Der Ergebnistext von `lehrer_csv` zeigt außerdem eine Warnung, falls ein Team laut MNSpro-Doku die Grenze von 100 Besitzern überschreiten würde.

### Kontrollfunktionen

- **Statistik anzeigen** / **TempHilfsfunktion** geben einen allgemeinen Überblick über die geladenen Daten.
- **ListeTeamBez** listet alle vergebenen Team-Bezeichnungen alphabetisch auf, zum Prüfen auf Sinnhaftigkeit.
- **ZuordnungUebersicht** ist der Kontrollschritt vor dem eigentlichen Export: zeigt je Zielkategorie (Arbeitsgruppe/Kurs/Gruppe) die betroffenen Lerngruppen, warnt vor nicht klassifizierten Lerngruppen und vor Team-Bezeichnungen, die in mehreren Zielkategorien gleichzeitig auftauchen.
- **LeereLerngruppenLöschen** entfernt Lerngruppen ohne Schüler (z.B. in der Planungsphase eines Schuljahres hilfreich) und bereinigt dabei auch die Verweise bei Lehrern/Schülern, im Lookup-Dict und bei Kursart-Overrides. Voraussetzung: `idsSchuelerZuLerngruppen` muss vorher gelaufen sein; fragt vor dem Löschen zur Sicherheit nach.

### Export-Dateien erstellen

Der eigentliche Export geschieht über die drei Buttons schueler_csv, sus_extern_csv und lehrer_csv - wenn alles gut läuft werden die entsprechenden csv-Dateien erstellt. Ein Blick in **ZuordnungUebersicht** vorher lohnt sich, um Überraschungen zu vermeiden.

## CSV-Import-Format für MNSpro Cloud

Quelle: [MNSpro Cloud FAQ – Schuljahreswechsel / MNSpro Cloud Hybrid](https://docs.mnspro.cloud/faq-frequently-asked-questions/mnspro-cloud/schuljahreswechsel/mnspro-cloud-hybrid) und [MNSpro Cloud – CSV-Import/Massenimport](https://docs.mnspro.cloud/mnspro-classic/cloud-gruppen-neu/csv-import-massenimport).

### Von diesem Tool erzeugtes Format

`writeSuSCSV`/`writeLuLCSV` in `generator.py` schreiben semikolon-getrennte Dateien mit der Kopfzeile

```text
ReferenzId;Vorname;Nachname;Klasse(n);Arbeitsgruppen;Cloud#Kurs;Cloud#Gruppe
```

Innerhalb der drei Zielspalten werden mehrere Team-/Kursbezeichnungen mit `|` getrennt zusammengefasst. Welche Lerngruppe in welche der drei Spalten einsortiert wird, legt die Kursart-Zuordnung fest (siehe unten) – vor dem Export lohnt sich ein Blick in **ZuordnungUebersicht**, um nicht klassifizierte Lerngruppen oder Namenskollisionen zu entdecken.

### Neues Format seit MNSpro 2026 (Cloud-Gruppen)

Mit MNSpro 2026 gibt es die neue Cloud-Gruppen-Funktion. Für den Import (u.a. Massenimport von Lehrern/Schülern) werden folgende Spalten unterstützt:

| Spalte           | Pflicht?                 | Bedeutung |
| ---------------- | ------------------------ | --------- |
| `Vorname`        | ja                       | Vorname |
| `Nachname`       | ja                       | Nachname |
| `Referenz-ID`    | optional, aber empfohlen | eindeutige Referenz-ID (z.B. GUID) |
| `Anmeldename`    | optional                 | Anmeldename |
| `Klassen`        | optional                 | Klassenzuordnung |
| `Arbeitsgruppen` | optional                 | lokale Arbeitsgruppen (klassisches MNSpro, **nicht** für Cloud-Gruppen) |
| `Cloud#Kurs`     | optional                 | Cloud-Kurse (ehemals „Arbeitsgruppen/Kurse"), mehrere Kurse durch `\|` getrennt |
| `Cloud#Gruppe`   | optional, **neu**        | Gruppen/Fachschaften, mehrere Gruppen durch `\|` getrennt |

**Wichtig:** Die Spaltennamen sind laut Dokumentation im Singular (`Cloud#Kurs`, `Cloud#Gruppe`), nicht im Plural.

Allgemeine Regeln:

- Das System erkennt sowohl **Komma** als auch **Semikolon** als Feldtrennzeichen automatisch, Zeilenumbrüche trennen die Datensätze.
- Eine **Kopfzeile** mit den obigen Spaltennamen ist zwingend erforderlich.
- Felder sollten idealerweise in **Anführungszeichen** stehen.
- Die Datei muss **UTF-8**-kodiert sein.
- Innerhalb von `Arbeitsgruppen`, `Cloud#Kurs` und `Cloud#Gruppe` gelten folgende Sonderzeichen:
  - `|` trennt mehrere Gruppen/Kurse innerhalb einer Zelle.
  - `*` ist ein Platzhalter für bereits vorhandene Arbeitsgruppen/Klassen des Benutzers (Wert bleibt unverändert).
  - `^` kennzeichnet den Benutzer als Verwalter/Besitzer der jeweiligen Gruppe.
  - Pro Kurs bzw. Gruppe gilt eine **Grenze von 100 Besitzern** – darüber hinausgehende Besitzer werden automatisch zu Mitgliedern.
- **Achtung:** Wird die Spalte `Arbeitsgruppen` angegeben, werden die Arbeitsgruppen **aller** Benutzer angepasst (überschrieben). Um sie unverändert zu lassen, muss die Spalte mit `*` befüllt werden.
- Beim Massenimport mit `Cloud#Kurs` muss zusätzlich das **Ziel-Schuljahr** ausgewählt werden, dem die Kurse zugeordnet werden.

### Unterschied Cloud#Kurs vs. Cloud#Gruppe

- **`Cloud#Kurs`**: reguläre Cloud-Kurse (Klassenteams, Jahrgangsteams, Fachkurse etc.) – jeweils einem Ziel-Schuljahr zugeordnet.
- **`Cloud#Gruppe`**: Gruppen ohne Schuljahresbezug, z.B. Fachschaften.

Für dieses Tool bedeutet das in der Regel: Klassen-, Jahrgangs- und Fachkurse werden über die Kursart-Zuordnung als `Cloud#Kurs` eingestuft, während z.B. Fachschaften eher als `Cloud#Gruppe` behandelt werden müssten. Welches `kursartKuerzel` wohin gehört, legt jede Schule selbst über **KursartZuordnung** (ggf. verfeinert über **BezeichnungsMusterBearbeiten**) fest – siehe die beiden Abschnitte oben.

## Button-Führung (Farben)

Damit man auch nach einer Pause weiß, wo man stehen geblieben ist, färbt das Programm die Buttons passend zum aktuellen Bearbeitungsstand ein. Der Zustand wird dabei nicht separat gemerkt, sondern bei jedem Klick direkt aus den vorhandenen Daten (Lerngruppen, Schüler, Lehrer, ...) neu ermittelt - er kann also nicht "falsch" werden, selbst wenn Schritte in anderer Reihenfolge oder mehrfach ausgeführt werden.

- **Grün**: der nächste noch fehlende Pflichtschritt. Gibt es für einen Schritt zwei gleichwertige Buttons (z.B. bei den Referenz-IDs "aus File" oder "aus SuS-Ids"/"aus kuerzel"), werden beide grün markiert - es reicht, einen davon zu benutzen.
- **Graublau**: bereits erledigte Schritte.
- **Gelb**: Schritte, die gerade sinnvoll wären, aber nicht zwingend nötig sind (z.B. Ergänze Schüler/Lehrer aus DB, Jahrgangsteams, Teams nicht erstellen).
- **Unverändert**: reine Hilfs- und Kontrollbuttons (Statistik anzeigen, ZuordnungUebersicht, BezeichnungsMusterBearbeiten, LeereLerngruppenLöschen, Serverzertifikat laden, ClearScreen, ...) sowie die Verbindungseinstellung sind nicht Teil der Führung und bleiben immer normal nutzbar.

Der Pflichtpfad umfasst der Reihe nach: Abschnitts-ID holen → Lerngruppen holen → generateLookupDicts → idsSchuelerZuLerngruppen → TeamBezErstellen → KursartZuordnung → Referenz-IDs für Schüler → idsLerngruppenZuLehrern → idsKlassenleitungenZuLehrern → Referenz-IDs für Lehrer → schueler_csv → sus_extern_csv → lehrer_csv.

Die genauen Zustände sind in `generator.py` als `WorkflowStep` (Pflichtschritte) und `OptionalStep` (situative Schritte) benannt.

## Exe erstellen

Die exe wird mit [PyInstaller](https://pyinstaller.org/) gebaut und landet als Einzeldatei im Ordner `dist/`. Die Konfiguration liegt in `SchildMNSDataMatcher_GUI.spec` (u.a. `console=True`, damit weiterhin ein Konsolenfenster mit den Debug-/Fehlerausgaben erscheint).

```bash
pip install pyinstaller
python -m PyInstaller SchildMNSDataMatcher_GUI.spec
```

**Wichtig:** Die vorhandene `.spec`-Datei verwenden (nicht `python -m PyInstaller --onefile SchildMNSDataMatcher_GUI.py` direkt aufrufen), damit die dort festgelegten Einstellungen wie `console=True` erhalten bleiben und nicht durch eine neu generierte Standard-`.spec` überschrieben werden.

Nach dem Build liegt `SchildMNSDataMatcher_GUI.exe` in `dist/`.
