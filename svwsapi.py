import requests
import os
import io
import gzip
import json

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

def gibLehrerListe() -> list:
    """Holt die Lehrerliste über /lehrer/"""
    url = f"{base_url}/lehrer"
    response = requests.get(url, auth=auth, verify=verify)
    response.raise_for_status()
    return response.json()


def gibSchuelerZuAbschnitt(abschnitt_id: int) -> list:
    """Holt die Schüler-Auswahlliste als gzip-komprimierte JSON und gibt sie als Liste zurück"""
    url = f"{base_url}/schueler/abschnitt/{abschnitt_id}/auswahlliste"
    headers = {"accept": "application/octet-stream"}
    response = requests.get(url, auth=auth, headers=headers, verify=verify)

    if response.status_code == 403:
        print("⚠️ Zugriff verweigert: Der Benutzer hat keine Rechte, um Schülerdaten anzusehen.")
        return []

    if response.status_code == 404:
        print("⚠️ Nicht alle Daten gefunden (404).")
        return []

    response.raise_for_status()

    # Gzip-Daten aus dem Response lesen
    compressed_data = io.BytesIO(response.content)
    with gzip.GzipFile(fileobj=compressed_data) as f:
        data = f.read()

    return json.loads(data)


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

def gibKurseDesAbschnitts(abschnitt_id: int) -> list:
    """Holt alle Kurse eines Schuljahresabschnitts, gibt Liste zurück"""
    url = f"{base_url}/kurse/abschnitt/{abschnitt_id}"
    response = requests.get(url, auth=auth, verify=verify)

    if response.status_code == 403:
        print("⚠️ Zugriff verweigert: Der Benutzer hat keine Rechte, um Kursdaten anzusehen.")
        return []

    if response.status_code == 404:
        print("⚠️ Keine Kurs-Einträge gefunden (404).")
        return []

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

def gibLerngruppen(abschnitt_id: int, lernplattform_id: int) -> dict:
    """Holt den Datenexport für eine Lernplattform im angegebenen Abschnitt"""
    url = f"{base_url}/v1/lernplattformen/{lernplattform_id}/{abschnitt_id}"
    response = requests.get(url, auth=auth, verify=verify)

    if response.status_code == 403:
        print("⚠️ Zugriff verweigert: Keine Rechte für Lernplattform-Export.")
        return {}

    if response.status_code == 404:
        print("⚠️ Fehlende Daten für Lernplattform-Export (404).")
        return {}

    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    schema = "svwsdb"
    #base_url = f"https://nightly.svws-nrw.de/db/{schema}"
    base_url = f"https://localhost/db/{schema}"
    username = "admin"  # Beispiel: Benutzername (ggf. anpassen)
    password = "Einstein"   # Beispiel: Passwort (ggf. anpassen)
    jahr = 2025
    abschnitt = 1

    auth=(username,password)

    # Basisinformationen prüfen
    abschnitts_id = gibIdSchuljahresabschnitt(jahr, abschnitt)

    if abschnitts_id:
        print(f"✅ Gefundene ID des Schuljahresabschnitts ({jahr}.{abschnitt}): {abschnitts_id}")
    else:
        print("⚠️ Kein passender Schuljahresabschnitt gefunden!")

    #print(gibLernabschnittsdaten(4058,1).get("leistungsdaten"))
    print(len(gibKurseDesAbschnitts(abschnitts_id)))
