
import csv
import sys
from collections import Counter
import svwsapi as sv

# --- Konfigurierbare Variablen ---
schema = "svwsdb"
#base_url = f"https://nightly.svws-nrw.de/db/{schema}"
base_url = f"https://localhost/db/{schema}"
username = "admin"  # Beispiel: Benutzername (ggf. anpassen)
password = "Einstein"   # Beispiel: Passwort (ggf. anpassen)
jahr = 2025
abschnitt = 1

# --- Authentifizierung ---
auth = (username, password)

# --- Initialisierung ---
sv.setConfig(base_url, auth)

# --- Hilfsmethoden ---

def printSchuelerinnen(schuelerListe: list, anz: int = 10):
    """Gibt Namen, Vornamen und ID von max. 'anz' SchülerInnen aus"""
    if anz == -1:
        anz = len(schuelerListe)
    for s in schuelerListe[:anz]:
        print(f"{s.get('nachname')}, {s.get('vorname')} (ID: {s.get('id')})")
        print(s)

def printDictEintraege(d: dict, anz: int = 10):
    """Gibt die ersten 'anz' Einträge eines Dictionaries aus"""
    for k, v in list(d.items())[:anz]:
        print(f"{k}: {v}")


def mapIdZuKuerzel(kf_liste: list) -> dict:
    """Erstellt ein Mapping: Kurs-ID → Kürzel"""
    return {kurs["id"]: kurs["kuerzel"] for kurs in kf_liste if kurs.get("id") and kurs.get("kuerzel")}

def zaehleEintraegePfad(data: dict, schluessel_pfad: list) -> dict:
    """
    Zählt die Werte am Ende eines verschachtelten Schlüsselpfa des JSON-Dokuments.
    Beispiel: ["lerngruppen", "kursartKuerzel"]
    """
    eintraege = []

    def durchlaufen(obj, pfad):
        if not pfad:
            eintraege.append(obj)
        elif isinstance(obj, list):
            for item in obj:
                durchlaufen(item, pfad)
        elif isinstance(obj, dict):
            schluessel = pfad[0]
            if schluessel in obj:
                durchlaufen(obj[schluessel], pfad[1:])

    durchlaufen(data, schluessel_pfad)
    return dict(Counter(eintraege))


# Basisinformationen prüfen
abschnitts_id = sv.gibIdSchuljahresabschnitt(jahr, abschnitt)

if abschnitts_id:
    print(f"✅ Gefundene ID des Schuljahresabschnitts ({jahr}.{abschnitt}): {abschnitts_id}")
else:
    print("⚠️ Kein passender Schuljahresabschnitt gefunden!")
    sys.exit(0)

# --- Schülerliste über Lernplattform-Export holen ---
lerngruppen_export = sv.gibLerngruppen(abschnitts_id, 1)
schuelerDesAbschnitts = lerngruppen_export.get("schueler", [])

printDictEintraege(zaehleEintraegePfad(lerngruppen_export,["lerngruppen","kursartKuerzel"]), anz=100)

printSchuelerinnen(schuelerDesAbschnitts)


klassenKuerzel = mapIdZuKuerzel(lerngruppen_export.get("klassen",[]))

# --- Lerngruppen extrahieren ---
lerngruppen = lerngruppen_export.get("lerngruppen", [])

# --- Mapping Schüler-ID → Liste Kurskürzel erstellen ---
from collections import defaultdict

schueler_zu_kursen = defaultdict(list)

for gruppe in lerngruppen:
    kursart = gruppe.get("kursartKuerzel")
    schueler_liste = gruppe.get("schueler", [])
    for s in schueler_liste:
        if kursart:
            schueler_zu_kursen[s["id"]].append(kursart)

# --- CSV-Datei vorbereiten ---
# --- Mapping: Lerngruppe-ID → Lerngruppe-Objekt ---
lerngruppen_liste = lerngruppen_export.get("lerngruppen", [])
lerngruppe_map = {lg["id"]: lg for lg in lerngruppen_liste if lg.get("id")}

with open("schueler_export.csv", mode="w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile, delimiter=";")
    writer.writerow(["GU_ID", "Nachname", "Vorname", "Klasse", "Kurse"])  # Kopfzeile

    count = 0
    for s in schuelerDesAbschnitts:
        if count > 300:
            break

        gu_id = s.get("gu_id")
        nachname = s.get("nachname")
        vorname = s.get("vorname")
        klasse = klassenKuerzel.get(s.get("idKlasse"))
        ids_lerngruppen = s.get("idsLerngruppen", [])

        if ids_lerngruppen:
            count += 1
            kuerzel_liste = [
                f"{klasse}-{lerngruppe_map[lg_id]['bezeichnung']}"
                for lg_id in ids_lerngruppen
                if lg_id in lerngruppe_map
                and lerngruppe_map[lg_id].get("bezeichnung")
                and klasse
            ]
            kurse = "|".join(kuerzel_liste)

            print(nachname, kurse, "\n")
            writer.writerow([gu_id, nachname, vorname, klasse, kurse])

print("✅ CSV-Datei 'schueler_export.csv' wurde erstellt.")
