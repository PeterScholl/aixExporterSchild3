
import csv
import sys
import svwsapi as sv

# --- Konfigurierbare Variablen ---
schema = "svwsdb"
#base_url = f"https://nightly.svws-nrw.de/db/{schema}"
base_url = f"https://localhost/db/{schema}"
username = "admin"  # Beispiel: Benutzername (ggf. anpassen)
password = "Einstein"   # Beispiel: Passwort (ggf. anpassen)
jahr = 2018
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


# Basisinformationen prüfen
abschnitts_id = sv.gibIdSchuljahresabschnitt(jahr, abschnitt)

if abschnitts_id:
    print(f"✅ Gefundene ID des Schuljahresabschnitts ({jahr}.{abschnitt}): {abschnitts_id}")
else:
    print("⚠️ Kein passender Schuljahresabschnitt gefunden!")
    sys.exit(0)

schuelerDesAbschnitts = sv.gibSchuelerListe(abschnitts_id)

printSchuelerinnen(schuelerDesAbschnitts)

kursKuerzel = mapIdZuKuerzel(sv.gibKurse())

print("-----\n Kurs-Kuerzel")
printDictEintraege(kursKuerzel)
print("-----")

faecherKuerzel = mapIdZuKuerzel(sv.gibFaecher())

print("-----\n Faecher-Kuerzel")
printDictEintraege(faecherKuerzel)
print("-----")

klassenKuerzel = mapIdZuKuerzel(sv.gibKlassen(abschnitts_id))
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
        if (count>10): break

        gu_id = s.get("gu_id")
        nachname = s.get("nachname")
        vorname = s.get("vorname")
        klasse = klassenKuerzel.get(s.get("idKlasse")) 
        #Kurse ermitteln
        lernabschnittsdaten = sv.gibLernabschnittsdaten(s.get('id'), abschnitts_id)
        if lernabschnittsdaten.get("leistungsdaten",[]) != []:
            count += 1
        
            liste_kurse = sv.gibKursKuerzelListe(lernabschnittsdaten, kursKuerzel, faecherKuerzel)
            # Vor jedes Kürzel die Klasse setzen
            liste_kurse_mit_klasse = [f"{klasse}-{k}" for k in liste_kurse]

            kurse = "|".join(liste_kurse_mit_klasse)
            print(nachname,kurse,lernabschnittsdaten.get("leistungsdaten",[]),"\n\n")

            writer.writerow([gu_id, nachname, vorname, klasse, kurse])

print("✅ CSV-Datei 'schueler_export.csv' wurde erstellt.")
