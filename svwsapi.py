import requests
import os
import io
import gzip
import json
import socket, ssl
from urllib.parse import urlparse
from ssl import DER_cert_to_PEM_cert


base_url = ""
auth = ()
verify = ""

def download_server_cert(pem_path="server.pem"):
    if not base_url: return
    if not base_url.startswith("https://"):
        u = urlparse("https://"+base_url)
    else:
        u = urlparse(base_url)
    if u.scheme != "https":
        raise ValueError("URL muss mit https:// beginnen")
    host = u.hostname
    port = u.port or 443

    #ctx = ssl.create_default_context()
    
    # Unverifizierter Context NUR zum Abholen des Zertifikats
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                der = ssock.getpeercert(binary_form=True)
                pem = DER_cert_to_PEM_cert(der)
        with open(pem_path, "w", encoding="utf-8") as f:
            f.write(pem)
    except ConnectionRefusedError as e:
        # WinError 10061 / Zielrechner verweigert
        raise RuntimeError(f"Verbindung verweigert ({host}:{port}). Läuft der Dienst?") from e
    except socket.timeout as e:
        raise RuntimeError(f"Zeitüberschreitung beim Verbinden zu {host}:{port}.") from e
    except socket.gaierror as e:
        # DNS/Name-Auflösung
        raise RuntimeError(f"Host '{host}' konnte nicht aufgelöst werden: {e}.") from e
    except TimeoutError as e:
        # kann separat auftreten
        raise RuntimeError(f"Timeout zu {host}:{port}.") from e
    except OSError as e:
        # Restliche OS-/Netzwerk-Fehler (z. B. Netzwerk unreachable)
        raise RuntimeError(f"Netzwerkfehler zu {host}:{port}: {e}.") from e
    return pem_path

# Prüfen, ob server.pem existiert
if os.path.exists("server.pem"):
    verify = "server.pem"
else: 
    try: 
        download_server_cert()
    except RuntimeError as err:
        print(f"❗ {err}")  # oder messagebox.showerror("Fehler", str(err))


def setConfig(url: str, auth_tuple: tuple):
    global base_url, auth
    base_url = url
    auth = auth_tuple
    if os.path.exists("server.pem"):
        verify = "server.pem"
    else: 
        print("❗❗❗ ACHTUNG - Das Server Zertifkat wird heruntergeladen ❗❗❗")
        try:
            download_server_cert()
        except RuntimeError as err:
            print(f"❗ {err}")  # oder messagebox.showerror("Fehler", str(err))


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
