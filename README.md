# Anleitung zur Verwendung dieses Tools

## Programmstart

Zunächst muss das Zertifikat des SVWS-Servers als **server.pem** in den Ordner des Programms gespeichert oder kopiert werden. Dann
**SchildMNSDataMatcher_GUI.py starten**

## Bedienung

### Konfiguration und Daten werden gemeinsam gesichert

Die Daten werden in der Datei status.json gespeichert. In der Datei finden sich die Daten zu Schüler, Kursen, der Datenbankverbindung und noch mehr. Für die schnellere Bearbeitung der Daten werden lookup-Dictionaries erstellt, die zu den jeweiligen IDs von Schülern, Lehreren oder Lerngruppen direkt auf die Objekte verweisen. Diese werden nicht gespeichert und müssen also ggf. nach dem Laden über den entsprechenden Button wieder erstellt werden.

### Verbindung zur Schild-Datenbank herstellen

Dazu den Button Verbindungseinstellungen betätigen und insbesondere die Datenbankverbindungseinstellungen korrekt setzen. Ob dies erfolgreich war kann über den Button *Abschnitts-ID holen* geprüft werden. **Dabei wird auch die Datenbankverbindung (Authentifizierung) korrekt gesetzt** Dieser holt aus der Datenbank die ID des in der Verbindung eingestellten Lernabschnitts (z.B. 2025 Abschnitt 1). Rückmeldungen werden in der Regel in dem Textfeld des GUIs angezeigt.

### Lerngruppen holen

Wenn die Verbindung steht sollten die Lerngruppen geholt werden. Das Programm nutzt dazu die api (Swagger-UI, ...) von Schild3 (Getestet mit Version 1.10 des SVWS-Servers)
Mit Statistik anzeigen erhält man einen Überblick über das was so an Daten geholt worden ist. Es werden auch aus den wichtigsten Objekten zufällige Elemente angezeigt.

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

### ReferenzIDs zuweisen

Den Schülern (und über den anderen Button den Lehreren) sollten für die Verwaltung in Teams und MNSpro Referenz-IDs zugewiesen werden. Leider gibt der SVWS-Server (aus Datenschutzgründen?) die oft verwendete GUID nicht über die Schnittstelle (API) raus. Daher kann sie z.B. direkt aus Schild3 exportiert werden (Interne ID und eindeutige ID). Die dabei entstandene CSV-Datei (evtl. txt in csv umbenenen) kann hier eingelesen werden und jedem Schüler wird dann entsprechend die GUID als ReferenzId für Teams bzw. MNSpro zugewisen.

Bei den Lehrern gibt es keine eindeutige ID, daher wird hier das kuerzel als Zuordnung verwendet. Aus Schild3 muss also eine csv-Datei mit Kürzel und eindeutiger ID (GUID) exportiert werden.

### SchildID als Referenz ID

Als Alternative kann auch die Schild-ID als Referenz-ID genutzt werden. Es sollte jedoch jeder Schüler eine ReferenzID haben, bevor die Export-Datei generiert wird.

### Jahrgangsteams und LehrerTeams

Manchmal möchte man den Schülern eines Jahrgangs noch Teams zuweisen, z.B. der EF ein Team Abi28 oder dem Jahrgang 9 und 10 ein BO-Team. Dies kann in diesem Dialog erfolgen und Schüler aus dem Jahrganag erhalten dann beim Export dieses Team bzw. auch Teams.

Besonders ist hier das Team für den Jahrgang **Lehrer**. Dieser Jahrgang wird allen Lehrern zugeordnet. Hier kann man z.B. die Gruppe * zuordnen um einzustellen, dass alte Gruppen erhalten bleiben.

### Lehrer ergänzen

Aktuell (22.08.2025) sind in dem Lerngruppenexport nicht alle Lehrer enthalten - ich habe diese über einen Anknüpfungspunkt der API ergänzt. Lehrer die nicht in dem Lerngruppenexport vorhanden sind aber in lerngruppen referenziert werden, werden dann bei lehrern ergänzt. Dann muss natürlich wieder die Referenz-ID zugewiesen werden usw.

### Kontrollfunktionen

Man kann mittels Statistik erstellen schon ein wenig prüfen auch die TempHilfsFunktion gibt einige Einblicke. In der letzten Buttonreihe sind Kontrollfunktionen geplant, so z.B. die Liste aller TeamBezeichnungen, damit kann man diese noch einmal auf Sinnhaftigkeit prüfen.

### Export-Dateien erstellen

Der eigentliche Export geschieht über die drei Buttons schueler_csv, sus_extern_csv und lehrer_csv - wenn alles gut läuft werden die entsprechenden csv-Dateien erstellt.
