import requests
import csv
import sys

# --- Konfigurierbare Variablen ---
schema = "GymAbiLite"
base_url = f"https://nightly.svws-nrw.de/db/{schema}"
username = "admin"  # Beispiel: Benutzername (ggf. anpassen)
password = ""   # Beispiel: Passwort (ggf. anpassen)
jahr = 2018
abschnitt = 2

# --- Authentifizierung ---
auth = (username, password)

# --- Methoden ---
def gibIdSchuljahresabschnitt(jahr: int, abschnitt: int) -> int | None:
    """Holt die ID des Schuljahresabschnitts für angegebenes Jahr und Abschnitt"""
    url = f"{base_url}/schule/stammdaten"
    response = requests.get(url, auth=auth)
    response.raise_for_status()
    stammdaten = response.json()

    abschnitte = stammdaten.get("abschnitte", [])
    for a in abschnitte:
        #print(f"Abschnitt:\n{a}\n------------")
        if a.get("schuljahr") == jahr and a.get("abschnitt") == abschnitt:
            return a.get("id")

    return None

def gibSchuelerListe(abschnitts_id: int) -> list:
    """Holt die Schülerliste über /schueler/abschnitt/{abschnitt}"""
    url = f"{base_url}/schueler/abschnitt/{abschnitts_id}"
    response = requests.get(url, auth=auth)
    response.raise_for_status()
    return response.json()

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


def gibLernabschnittsdaten(schueler_id: int, abschnitt_id: int) -> dict:
    """Holt die Lernabschnittsdaten eines Schülers für einen bestimmten Abschnitt"""
    url = f"{base_url}/schueler/{schueler_id}/abschnitt/{abschnitt_id}/lernabschnittsdaten"
    response = requests.get(url, auth=auth)
    if response.status_code == 404:
        print(f"⚠️ Keine Lernabschnittsdaten gefunden für Schueler-ID {schueler_id}, Abschnitt {abschnitt_id}")
        return {}
    response.raise_for_status()
    return response.json()

def gibKursKuerzelListe(lernabschnittsdaten: dict, kurs_map: dict, fach_map: dict) -> list:
    """Erstellt eine Liste der Kurskürzel aus den Leistungsdaten eines Schülers.
       Bei KursID=None wird das Kürzel aus der FachID genommen.
       Fehler werden ausgegeben, aber nicht in die Ergebnisliste aufgenommen.
    """
    kuerzel_liste = []
    leistungsdaten = lernabschnittsdaten.get("leistungsdaten", [])

    for l in leistungsdaten:
        kurs_id = l.get("kursID")
        fach_id = l.get("fachID")

        if kurs_id is not None:
            kuerzel = kurs_map.get(kurs_id)
            if kuerzel:
                kuerzel_liste.append(kuerzel)
            else:
                print(f"⚠️ Kurs-ID {kurs_id} nicht im Kurs-Mapping gefunden.")
        else:
            if fach_id is not None:
                kuerzel = fach_map.get(fach_id)
                if kuerzel:
                    kuerzel_liste.append(kuerzel)
                else:
                    print(f"⚠️ Fach-ID {fach_id} nicht im Fach-Mapping gefunden.")
            else:
                print("⚠️ Weder Kurs-ID noch Fach-ID vorhanden.")

    return kuerzel_liste


def gibKurse() -> list:
    """Holt die Liste aller Kurse"""
    url = f"{base_url}/kurse"
    response = requests.get(url, auth=auth)
    response.raise_for_status()
    return response.json()

def gibFaecher() -> list:
    """Holt die Liste aller Kurse"""
    url = f"{base_url}/faecher"
    response = requests.get(url, auth=auth)
    response.raise_for_status()
    return response.json()

def gibKlassen(abschnitt_id: int) -> list:
    """Holt die Klassenliste für einen bestimmten Abschnitt"""
    url = f"{base_url}/klassen/abschnitt/{abschnitt_id}"
    response = requests.get(url, auth=auth)
    response.raise_for_status()
    return response.json()


def mapIdZuKuerzel(kf_liste: list) -> dict:
    """Erstellt ein Mapping: Kurs-ID → Kürzel"""
    return {kurs["id"]: kurs["kuerzel"] for kurs in kf_liste if kurs.get("id") and kurs.get("kuerzel")}


# Basisinformationen prüfen
abschnitts_id = gibIdSchuljahresabschnitt(jahr, abschnitt)

if abschnitts_id:
    print(f"✅ Gefundene ID des Schuljahresabschnitts: {abschnitts_id}")
else:
    print("⚠️ Kein passender Schuljahresabschnitt gefunden!")
    sys.exit(0)

schuelerDesAbschnitts = gibSchuelerListe(abschnitts_id)

printSchuelerinnen(schuelerDesAbschnitts)

kursKuerzel = mapIdZuKuerzel(gibKurse())

print("-----\n Kurs-Kuerzel")
printDictEintraege(kursKuerzel)
print("-----")

faecherKuerzel = mapIdZuKuerzel(gibFaecher())

print("-----\n Faecher-Kuerzel")
printDictEintraege(faecherKuerzel)
print("-----")

klassenKuerzel = mapIdZuKuerzel(gibKlassen(abschnitts_id))
print("-----\n Klassen-Kuerzel")
printDictEintraege(klassenKuerzel)
print("-----")


# --- Schüler-Daten speichern ---

schueler_liste = schuelerDesAbschnitts

# --- CSV-Datei vorbereiten ---
with open("schueler_export.csv", mode="w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile, delimiter=";")
    writer.writerow(["GU_ID", "Nachname", "Vorname", "Klasse", "Kurse"])  # Kopfzeile

    count = 0
    for s in schueler_liste:
        count += 1
        if (count>300): break

        gu_id = s.get("gu_id")
        nachname = s.get("nachname")
        vorname = s.get("vorname")
        klasse = klassenKuerzel.get(s.get("idKlasse")) 
        #Kurse ermitteln
        lernabschnittsdaten = gibLernabschnittsdaten(s.get('id'), abschnitts_id)
        liste_kurse = gibKursKuerzelListe(lernabschnittsdaten, kursKuerzel, faecherKuerzel)
        # Vor jedes Kürzel die Klasse setzen
        liste_kurse_mit_klasse = [f"{klasse}-{k}" for k in liste_kurse]

        kurse = "|".join(liste_kurse_mit_klasse)
        print(nachname,kurse)

        writer.writerow([gu_id, nachname, vorname, klasse, kurse])

print("✅ CSV-Datei 'schueler_export.csv' wurde erstellt.")
