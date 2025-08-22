import tkinter as tk
from tkinter import filedialog, ttk
import csv
import sys
from collections import Counter
from config_gui import load_config, show_config_gui
import fetch
import svwsapi as sv
import config_gui

class Generator():
    def __init__(self):
        self.host = "localhost"
        self.schema="svwsdb"
        self.base_url=f'https://{self.host}/db/{self.schema}'
        self.username = "admin"
        self.password = "pass"
        self.jahr = 2025
        self.abschnitt = 1
        self.svws_abschnitts_id = None
        self.kursarten_ohne_klasse = []
        self.lookupDict = {} # Dictionaries, die zur jeweiligen ID einen Verweis auf das zugehörige Objekt liefern
        sv.setConfig(self.base_url, (self.username, self.password))

    def initAbschnittsID(self):
        sv.setConfig(self.base_url, (self.username, self.password))
        self.svws_abschnitts_id = sv.gibIdSchuljahresabschnitt(self.jahr, self.abschnitt)

        if self.svws_abschnitts_id:
            print(f"✅ Gefundene ID des Schuljahresabschnitts ({self.jahr}.{self.abschnitt}): {self.svws_abschnitts_id}")
            return True
        else:
            print("⚠️ Kein passender Schuljahresabschnitt gefunden!")
            return False
        
    def configValues(self, root):
        cfg = {}
        cfg["schema"] = self.schema if self.schema else "svwsdb"
        cfg["host"]= self.host if self.host else "localhost"
        cfg["username"] = self.username if self.username else "admin"
        cfg["password"] = self.password if self.password else "pass"
        cfg["jahr"] = self.jahr if self.jahr else 2025
        cfg["abschnitt"] = self.abschnitt if self.abschnitt else 1
        cfg["kursarten_ohne_klasse"] = self.kursarten_ohne_klasse if self.kursarten_ohne_klasse else ["AGGT"]
        cfg["kursarten_nur_mit_jahrgang"] = getattr(self,"kursarten_nur_mit_jahrgang", [])

        print("show config - start")

        result = show_config_gui(root, cfg)
        print("show config - end")
        print(f"Result: {result}")
        for key, value in result.items():
            print(f"Key {key} erhält Value: {value}")
            setattr(self, key, value)
        sv.setConfig(self.base_url, (self.username, self.password))

    def lerngruppenHolen(self, keys = ["jahrgaenge","klassen","lehrer","faecher","lerngruppen", "schueler"]):
        lerngruppen_export = sv.gibLerngruppen(self.svws_abschnitts_id,1)
        for key, value in lerngruppen_export.items():
            if key in keys:
                print(f"Key von Lerngruppen wird übertragen: {key}")
                setattr(self, key, value)

    def generateLookups(self):
        for key in ["jahrgaenge","klassen","lehrer","faecher","lerngruppen", "schueler"]:
            self.lookupDict[key] = {obj["id"]: obj for obj in getattr(self, key, [])}

    def addSuSIdsZuLerngruppen(self):
        # Zähler als Rückmeldung der Tätigkeit
        count = 0

        # sicherstellen, dass das lookupDict für die Schueler existiert
        if len(getattr(self.lookupDict,"schueler",{}))==0 or len(self.lookupDicts.get("lerngruppen",{})) == 0:
            self.generateLookups()

        # sicherstellen, dass jedes Lerngruppenobjekt ein Feld idsSchueler hat
        for lg in self.lookupDict.get("lerngruppen", {}).values():
            lg.setdefault("idsSchueler", [])

        # alle Schüler durchgehen
        for schueler in getattr(self, "schueler", []):
            sid = schueler["id"]
            for lg_id in schueler.get("idsLerngruppen", []):
                if lg_id in self.lookupDict["lerngruppen"]:
                    ids = self.lookupDict["lerngruppen"][lg_id]["idsSchueler"]
                    if sid not in ids:   # doppelte vermeiden
                        ids.append(sid)
                        count+=1

        return count
    
    def addTeamBezZuLerngruppen(self):
        resultText = "" #Ergebnistext
        count=0 #Zähler für das Ergebnis
        countlg=0 # Zähler insgesamt

        lookupSuS = self.lookupDict.get("schueler",{})
        if len(lookupSuS) == 0:
            return "FEHLER: Schueler-Lookup-Dict ist leer\n"

        # alle Lerngruppen durchgehen
        for lg in getattr(self, "lerngruppen", []):
            countlg+=1
            kursartKuerzel = lg.get("kursartKuerzel", None)
            lgbezeichnung = lg.get("bezeichnung", None)
            if "kursartKuerzel" in lg:
                if lgbezeichnung != None:
                    if kursartKuerzel in getattr(self, "kursarten_ohne_klasse", []):
                        count += 1
                        lg["teamBez"] = lgbezeichnung
                    else: # Jetzt muss entweder Jahrgang oder Klasse vorangestellt werden
                        idsSchueler = lg.get("idsSchueler", [])
                        if (len(idsSchueler) > 0):
                            if kursartKuerzel in getattr(self, "kursart_nur_mit_jahrgang", []):
                                #Jahrgang eines Schuelers holen
                                prefix = self.get_jahrgang_von_schueler(idsSchueler[0])
                            else:
                                #Klasse eines Schuelers holen
                                prefix = self.get_klasse_von_schueler(idsSchueler[0])
                            if prefix:
                                count+=1
                                lg["teamBez"] = prefix+" - "+lgbezeichnung
                            else:
                                resultText+=f'FEHLER: Klasse oder Jahrgang zu {lg} kann nicht gefunden werden\n'
                        else:
                            resultText+=f'FEHLER: Lerngruppe {lg} hat keine Schüler\n'
                        
                else: #Diese Lerngruppe hat keine Bezeichnung
                    resultText+= f'Keine Bezeichnung bei {lg.get("id",lg)}\n'
            else: #kursartkuerzel gibt es nicht
                resultText+= f'Kein Kursartkuerzel bei {lg.get("id",lg)} - Wert {kursartKuerzel}\n'

        resultText+=f'Es wurden {count} Teambezeichnungen bei insgesamt {countlg} Lerngruppen zugeordnet\n'
        return resultText
    
    def get_klasse_von_schueler(self, schueler_id: int) -> str | None:
        # Schüler nachschlagen
        schueler = self.lookupDict.get("schueler", {}).get(schueler_id)
        if not schueler:
            return None

        # Klassen-ID aus Schüler holen
        klassen_id = schueler.get("idKlasse")
        if not klassen_id:
            return None

        # Klasse nachschlagen
        klasse = self.lookupDict.get("klassen", {}).get(klassen_id)
        if not klasse:
            return None

        # Kürzel zurückgeben, falls vorhanden
        return klasse.get("kuerzelAnzeige")

    def get_jahrgang_von_schueler(self, schueler_id: int) -> str | None:
        # Schüler nachschlagen
        schueler = self.lookupDict.get("schueler", {}).get(schueler_id)
        if not schueler:
            return None

        # jahrgang-ID aus Schüler holen
        jahrgang_id = schueler.get("idJahrgang")
        if not jahrgang_id:
            return None

        # Klasse nachschlagen
        jahrgang = self.lookupDict.get("jahrgaenge", {}).get(jahrgang_id)
        if not jahrgang:
            return None

        # Kürzel zurückgeben, falls vorhanden
        return jahrgang.get("kuerzelAnzeige")
    
    def writeSuSCSV(self, statusList = [2], filename="Student.csv"): # Status 2 - aktiv, 6 - extern
        ergText = ""
        # Voraussetzungen prüfen (ReferenzID vorhanden, TeamsBez in den Lerngruppen)
        if not all("referenzId" in schueler for schueler in getattr(self,"schueler",{})):
            return "Keine Schüler vorhanden oder nicht alle haben eine referenzId\n"
        if not all("teamBez" in lerngruppe for lerngruppe in getattr(self,"lerngruppen",{})):
            return "Nicht alle Lerngruppen haben eine Teams-Bezeichnung (key: teamBez)\n"
        with open(filename, mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile, delimiter=";")
            # Original Kopfzeile: ReferenzId;Vorname;Nachname;Klasse;Gruppen
            writer.writerow(["ReferenzId", "Vorname", "Nachname", "Klasse", "Gruppen"])  # Kopfzeile

            count = 0
            lookup_lg = self.lookupDict.get("lerngruppen",{})
            for s in getattr(self,"schueler",{}):
                if not s.get("status") in statusList:
                    continue
                if count > 3000:
                    ergText+= f"Limiterreicht - Maximale Anzahl {count}\n"
                    break

                referenzId = s.get("referenzId")
                nachname = s.get("nachname")
                vorname = s.get("vorname")
                klasse = self.get_klasse_von_schueler(s.get("id"))
                ids_lerngruppen = s.get("idsLerngruppen", [])

                teams_liste = []

                if ids_lerngruppen:
                    for lg_id in ids_lerngruppen:
                        lg = lookup_lg.get(lg_id,{})
                        if not lg:
                            ergText+=f"Lerngruppe mit {lg_id} nicht gefunden\n"
                            continue
                        bezeichnung = lg.get("teamBez")
                        teams_liste.append(bezeichnung)
                else:
                    ergText+=f"⚠️  {nachname}, {vorname} ({klasse}) hat keine Lerngruppe\n"

                kurse = "|".join(teams_liste)
                count += 1
                writer.writerow([referenzId, vorname, nachname, klasse, kurse])

        ergText+=(f"✅ CSV-Datei '{filename}' wurde mit {count} Einträgen erstellt.\n")
        return ergText

    def writeLuLCSV(self):
        pass

    def import_referenz_ids(self, master):
        """CSV wählen, Spalten für Schüler-ID und Referenz-ID wählen und zuweisen."""
        # CSV-Datei auswählen
        filepath = filedialog.askopenfilename(
            parent=master,
            title="CSV-Datei wählen",
            filetypes=[("CSV-Dateien", "*.csv"), ("Alle Dateien", "*.*")]
        )
        if not filepath:
            return "Kein File gewählt\n"

        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";", quotechar='"')
            rows = list(reader)
        if not rows or not reader.fieldnames:
            return "FEHLER: Enthält keine Daten\n"

        columns = reader.fieldnames

        # Toplevel für Spaltenauswahl
        win = tk.Toplevel(master)
        win.title("Spalten auswählen")

        tk.Label(win, text="Spalte mit Schüler-ID:").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        cb_sid = ttk.Combobox(win, values=columns, state="readonly")
        cb_sid.grid(row=0, column=1, padx=8, pady=6)

        tk.Label(win, text="Spalte mit Referenz-ID:").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        cb_ref = ttk.Combobox(win, values=columns, state="readonly")
        cb_ref.grid(row=1, column=1, padx=8, pady=6)

        result = {}

        def on_ok():
            sid_col = cb_sid.get()
            ref_col = cb_ref.get()
            if not sid_col or not ref_col:
                return
            mapping = {}
            for row in rows:
                sid = row.get(sid_col)
                ref = row.get(ref_col)
                if sid and ref:
                    try:
                        mapping[int(sid)] = ref
                    except ValueError:
                        continue
            result["mapping"] = mapping
            win.destroy()

        ttk.Button(win, text="OK", command=on_ok).grid(row=2, column=0, columnspan=2, pady=8)

        win.grab_set()
        win.wait_window()

        if "mapping" not in result:
            return "FEHLER: Es konnte keine Zuordnung erstellt werden\n"

        # Schülerobjekte aktualisieren
        count_ref = 0
        count_id = 0
        for schueler in getattr(self, "schueler", []):
            sid = schueler.get("id")
            if sid in result["mapping"]:
                schueler["referenzId"] = result["mapping"][sid]
                count_ref+=1
            else:
                schueler["referenzId"] = sid
                count_id+=1

        print(f"{len(result['mapping'])} Referenz-IDs zugewiesen.")
        return f"{count_ref} Referenz-IDs zugewisen - {count_id} mal die Schild-Id als Referenz\n"




if __name__=="__main__":
    g = Generator()
    

