import requests
import os

base_url = ""
auth = ()
verify = True  # Standard: Zertifikat wird geprüft

# Prüfen, ob server.pem existiert
if os.path.exists("server.pem"):
    verify = "server.pem"

def setConfig(url: str, auth_tuple: tuple):
    global base_url, auth
    base_url = url
    auth = auth_tuple

# --- Methoden ---
def gibIdSchuljahresabschnitt(jahr: int, abschnitt: int) -> int | None:
    """Holt die ID des Schuljahresabschnitts für angegebenes Jahr und Abschnitt"""
    url = f"{base_url}/schule/stammdaten"
    response = requests.get(url, auth=auth, verify=verify)
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
    response = requests.get(url, auth=auth, verify=verify)
    response.raise_for_status()
    return response.json()

def gibLernabschnittsdaten(schueler_id: int, abschnitt_id: int) -> dict:
    """Holt die Lernabschnittsdaten eines Schülers für einen bestimmten Abschnitt"""
    url = f"{base_url}/schueler/{schueler_id}/abschnitt/{abschnitt_id}/lernabschnittsdaten"
    response = requests.get(url, auth=auth, verify=verify)
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
    response = requests.get(url, auth=auth, verify=verify)
    response.raise_for_status()
    return response.json()

def gibFaecher() -> list:
    """Holt die Liste aller Kurse"""
    url = f"{base_url}/faecher"
    response = requests.get(url, auth=auth, verify=verify)
    response.raise_for_status()
    return response.json()

def gibKlassen(abschnitt_id: int) -> list:
    """Holt die Klassenliste für einen bestimmten Abschnitt"""
    url = f"{base_url}/klassen/abschnitt/{abschnitt_id}"
    response = requests.get(url, auth=auth, verify=verify)
    response.raise_for_status()
    return response.json()
