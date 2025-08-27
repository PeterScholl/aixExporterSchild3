import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import csv
import sys
import os
from collections import Counter
from config_gui import load_config, show_config_gui
import fetch
import svwsapi as sv
import config_gui


# Define a mapping for special characters
# TODO in mnspro Namen dürfen keine ' oder ` oder ? ...  vorkommen, diese sollten erstezt werden Unicode-Zeichen sind i.O.
my_char_map = {
    'ć': 'c',
    'ç': 'c',
    'Ç': 'C',
    'é': 'e',
    'è': 'e',
    'ê': 'e',
    'ñ': 'n',
    '\'': '',
    '´': '',
    '?': '',
    '.':''
    # Add more mappings as needed
}

class Generator():
    def __init__(self):
        self.host = "nightly.svws-nrw.de"
        self.schema="GymAbiLite"
        self.base_url=f'https://{self.host}/db/{self.schema}'
        self.username = "admin"
        self.password = ""
        self.jahr = 2018
        self.abschnitt = 1
        self.svws_abschnitts_id = None
        self.kursarten_ohne_klasse = []
        self.lookupDict = {} # Dictionaries, die zur jeweiligen ID einen Verweis auf das zugehörige Objekt liefern
        self.jahrgangsteams = {"Lehrer": ["*"]} #Sicherstellen, dass dieses Attribut existiert
        self.replaceSpecialChars = True # Sonderzeichen in Gruppen oder Namen ersetzen
        sv.setConfig(self.base_url, (self.username, self.password))
        if os.path.exists("server.pem"):
            sv.verify="server.pem"

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
        cfg["schema"] = self.schema if self.schema else "GymAbiLite"
        cfg["host"]= self.host if self.host else "nightly.svws-nrw.de"
        cfg["username"] = self.username if self.username else "admin"
        cfg["password"] = self.password if self.password else ""
        cfg["jahr"] = self.jahr if self.jahr else 2018
        cfg["abschnitt"] = self.abschnitt if self.abschnitt else 1
        cfg["kursarten_ohne_klasse"] = self.kursarten_ohne_klasse if self.kursarten_ohne_klasse else ["AGGT","EGS1","FOGT"]
        cfg["kursarten_nur_mit_jahrgang"] = getattr(self,"kursarten_nur_mit_jahrgang", ["LK","GK","WPII","PUT"])

       
        result = show_config_gui(root, cfg)
       
        if (result):
            print(f"Result: {result}")
            for key, value in result.items():
                print(f"Key {key} erhält Value: {value}")
                setattr(self, key, value)
            sv.setConfig(self.base_url, (self.username, self.password))

    def lerngruppenHolen(self, keys = ["jahrgaenge","klassen","lehrer","faecher","lerngruppen", "schueler"]):
        self.initAbschnittsID()
        #sv.setConfig(self.base_url, (self.username, self.password))
        lerngruppen_export = sv.gibLerngruppen(self.svws_abschnitts_id,1)
        for key, value in lerngruppen_export.items():
            if key in keys:
                print(f"Key von Lerngruppen wird übertragen: {key}")
                setattr(self, key, value)

    def ergaenzeLehrer(self):
        """ ergänzt möglicherweise fehlende Lehrer aus der Datenbank """
        ergText = ""
        lehrer_export = sv.gibLehrerListe()
        lehrer_lookup = {obj["id"]: obj for obj in lehrer_export}
        ergText += f"Es gibt {len(lehrer_lookup)} Lehrer in der Datenbank\n"

        # sicherstellen, dass Strukturen existieren
        if not hasattr(self, "lehrer"):
            ergText += "Die Lehrerdaten waren noch gar nicht vorhanden\n"
            self.lehrer = []
        if "lehrer" not in self.lookupDict:
            ergText += "LookupDicts müssen noch erstellt werden\n"
            self.generateLookups()

        # alle Lerngruppen durchgehen
        for lg in getattr(self, "lerngruppen", []):
            for lid in lg.get("idsLehrer", []):
                if lid in self.lookupDict["lehrer"]:
                    continue
                if lid in lehrer_lookup:
                    ergText+=f'Lehrer {lehrer_lookup[lid].get("kuerzel","?")} mit id {lid} wird übernommen\n'
                    lehrer_obj = lehrer_lookup[lid]
                    # in LookupDict übernehmen
                    self.lookupDict["lehrer"][lid] = lehrer_obj
                    # in Liste anhängen
                    self.lehrer.append(lehrer_obj)
                else:
                    print(f"Achtung: Lehrer-ID {lid} nicht im Export gefunden.")
        return ergText


    def generateLookups(self):
        for key in ["jahrgaenge","klassen","lehrer","faecher","lerngruppen", "schueler"]:
            self.lookupDict[key] = {obj["id"]: obj for obj in getattr(self, key, [])}

    def addKlassenleitungsIdsZuLuL(self):
        # Zähler als Rückmeldung der Tätigkeit
        count = 0

        # sicherstellen, dass das lookupDict existiert
        if len(getattr(self.lookupDict,"lehrer",{}))==0 or len(self.lookupDicts.get("klassen",{})) == 0:
            self.generateLookups()

        # sicherstellen, dass jedes LehrerObjekt ein Feld idsKlassenleitung hat
        for l in self.lookupDict.get("lehrer", {}).values():
            l.setdefault("idsKlassenleitung", [])

        # alle klassen durchgehen
        for klasse in getattr(self, "klassen", []):
            klassen_id = klasse["id"]
            for lul_id in klasse.get("idsKlassenlehrer", []):
                if lul_id in self.lookupDict["lehrer"]:
                    ids = self.lookupDict["lehrer"][lul_id]["idsKlassenleitung"]
                    if klassen_id not in ids:   # doppelte vermeiden
                        ids.append(klassen_id)
                        count+=1

        return count
    
    def addLerngruppenIdsZuLuL(self):
        # Zähler als Rückmeldung der Tätigkeit
        count = 0

        # sicherstellen, dass das lookupDict existiert
        if len(getattr(self.lookupDict,"lehrer",{}))==0 or len(self.lookupDicts.get("lerngruppen",{})) == 0:
            self.generateLookups()

        # sicherstellen, dass jedes LehrerObjekt ein Feld idsLerngruppen hat
        for l in self.lookupDict.get("lehrer", {}).values():
            l.setdefault("idsLerngruppen", [])

        # alle lerngruppen durchgehen
        for lg in getattr(self, "lerngruppen", []):
            lg_id = lg["id"]
            for lul_id in lg.get("idsLehrer", []):
                if lul_id in self.lookupDict["lehrer"]:
                    ids = self.lookupDict["lehrer"][lul_id]["idsLerngruppen"]
                    if lg_id not in ids:   # doppelte vermeiden
                        ids.append(lg_id)
                        count+=1

        return count
    
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
        """Jeder Lerngruppe wird aufgrund der zugeordneten Schülermenge eine Bezeichnug mit Klasse, Jahrgang oder ohne
        prefix zugeordnet. Zudem erhält die Lerngruppe auf einen Jahrgang"""
        resultText = "" #Ergebnistext
        count=0 #Zähler für das Ergebnis
        countlg=0 # Zähler insgesamt
        countjg=0 # Zähler für nur Jahrgang als Prefix
        countno=0 # Zähler für kein Prefix

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
                        countno +=1
                        lg["teamBez"] = lgbezeichnung
                        lg["jahrgang"] = None
                    else: # Jetzt muss entweder Jahrgang oder Klasse vorangestellt werden
                        idsSchueler = lg.get("idsSchueler", [])
                        if (len(idsSchueler) > 0):
                            if kursartKuerzel in getattr(self, "kursarten_nur_mit_jahrgang", []):
                                #Jahrgang eines Schuelers holen
                                countjg+=1
                                prefix = self.get_jahrgang_von_schueler(idsSchueler[0])
                                if (len(self.get_kl_jg_zu_schuelerIDListe(idsSchueler, art="jahrgaenge"))!=1):
                                    resultText+=f"WARNUNG: Lerngruppe {prefix} - {lgbezeichnung} mit ID {lg.get("id","?")} hat als Jahrgangsteam Schüler mehrerer Jahrgänge\n"
                                jahrgang = prefix
                            else:
                                #Klasse eines Schuelers holen
                                prefix = self.get_klasse_von_schueler(idsSchueler[0])
                                if (len(self.get_kl_jg_zu_schuelerIDListe(idsSchueler))!=1):
                                    resultText+=f"WARNUNG: Lerngruppe {prefix} - {lgbezeichnung} mit ID {lg.get("id","?")} hat als Klassenteam Schüler mehrerer Klassen\n"
                                jahrgang = self.get_jahrgang_von_schueler(idsSchueler[0])
                            if prefix:
                                count+=1
                                lg["teamBez"] = prefix+" - "+lgbezeichnung
                                lg["jahrgang"] = jahrgang
                            else:
                                resultText+=f'FEHLER: Klasse oder Jahrgang zu {lg} kann nicht gefunden werden\n'
                        else:
                            resultText+=f'FEHLER: Lerngruppe {lg} hat keine Schüler\n'
                        
                else: #Diese Lerngruppe hat keine Bezeichnung
                    resultText+= f'Keine Bezeichnung bei {lg.get("id",lg)}\n'
            else: #kursartkuerzel gibt es nicht
                resultText+= f'Kein Kursartkuerzel bei {lg.get("id",lg)} - Wert {kursartKuerzel}\n'

        resultText+=f'Es wurden {count} Teambezeichnungen bei insgesamt {countlg} Lerngruppen zugeordnet\n' 
        resultText+=f'Davon bekamen {countjg} nur den Jahrgang als Prefix und {countno} kein Prefix\n'
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
    
    def get_kl_jg_zu_schuelerIDListe(self, schuelerIDs: list, art: str = "klassen", unique: bool = True) -> list:
        """
        Gibt eine Liste der Klassen/Jahrgangs-Kürzel zu den angegebenen Schüler-IDs zurück.
        - unique=True: doppelte Kürzel werden entfernt
        """
        result = []
        schueler_lookup = self.lookupDict.get("schueler", {})
        kl_jg_lookup = self.lookupDict.get(art, {})

        for sid in schuelerIDs:
            schueler = schueler_lookup.get(sid)
            if not schueler:
                print(f"Schüler mit ID {sid} nicht gefunden")
                continue
            kjid = schueler.get("idKlasse") if art=="klassen" else schueler.get("idJahrgang")
            if not kjid:
                print(f"Schüler {sid} hat keine {art}-ID")
                continue
            kl_jg = kl_jg_lookup.get(kjid)
            if not kl_jg:
                print(f"Klasse/Jahrgang mit ID {sid} nicht gefunden")
                continue
            kuerzel = kl_jg.get("kuerzelAnzeige")
            if kuerzel and (not unique or kuerzel not in result):
                    result.append(kuerzel)

        return result


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
            if (statusList != [2]):
                writer.writerow(["ReferenzId", "Vorname", "Nachname", "Klassen", "Gruppen"])  # Kopfzeile
            else:
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
                jahrgang = self.get_jahrgang_von_schueler(s.get("id")) # für Jahrgangsteams
                ids_lerngruppen = s.get("idsLerngruppen", [])

                # TeamsListe wird mit der Jahrgansliste Initialisiert
                teams_liste = list(self.jahrgangsteams.get(jahrgang, []))

                if ids_lerngruppen:
                    for lg_id in ids_lerngruppen:
                        lg = lookup_lg.get(lg_id,{})
                        if not lg:
                            ergText+=f"Lerngruppe mit {lg_id} nicht gefunden\n"
                            continue
                        bezeichnung = lg.get("teamBez")
                        if (self.replaceSpecialChars):
                            bezeichnung = replace_chars(bezeichnung, my_char_map)
                        teams_liste.append(bezeichnung)
                else:
                    ergText+=f"⚠️  {nachname}, {vorname} ({klasse}) hat keine Lerngruppe\n"

                kurse = "|".join(teams_liste)
                count += 1
                if (self.replaceSpecialChars):
                    nachname = replace_chars(nachname, my_char_map)
                    vorname = replace_chars(vorname, my_char_map)
                writer.writerow([referenzId, vorname, nachname, klasse, kurse])

        ergText+=(f"✅ CSV-Datei '{filename}' wurde mit {count} Einträgen erstellt.\n")
        return ergText

    def writeLuLCSV(self):
        ergText = ""
        # Voraussetzungen prüfen (ReferenzID vorhanden, TeamsBez in den Lerngruppen)
        if not all("referenzId" in lehrer for lehrer in getattr(self,"lehrer",{})):
            return "Keine Lehrer vorhanden oder nicht alle haben eine referenzId\n"
        if not all("teamBez" in lerngruppe for lerngruppe in getattr(self,"lerngruppen",{})):
            return "Nicht alle Lerngruppen haben eine Teams-Bezeichnung (key: teamBez)\n"
        with open("Teacher.csv", mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile, delimiter=";")
            # Original Kopfzeile: ReferenzId;Vorname;Nachname;Klassen;Gruppen
            writer.writerow(["ReferenzId", "Vorname", "Nachname", "Klassen", "Gruppen"])  # Kopfzeile

            count = 0
            lookup_lg = self.lookupDict.get("lerngruppen",{})
            lookup_klassen = self.lookupDict.get("klassen",{})

            for l in getattr(self,"lehrer",{}):
                referenzId = l.get("referenzId")
                nachname = l.get("nachname")
                vorname = l.get("vorname")
                ids_lerngruppen = l.get("idsLerngruppen", [])
                ids_klassen = l.get("idsKlassenleitung", [])

                klassen_liste=[]

                if ids_klassen:
                    for klassen_id in ids_klassen:
                        klasse = lookup_klassen.get(klassen_id,{})
                        if not klasse:
                            ergText+=f"Klasse mit {klassen_id} nicht gefunden\n"
                            continue
                        bezeichnung = "^"+klasse.get("kuerzelAnzeige")
                        klassen_liste.append(bezeichnung)
                else:
                    ergText+=f"⚠️  {nachname}, {vorname} hat keine Klassenleitungen\n"

                klassen = "|".join(klassen_liste)

                # TeamsListe wird mit der Jahrgansliste "Lehrer" Initialisiert
                teams_liste = list(self.jahrgangsteams.get("Lehrer", []))

                if ids_lerngruppen:
                    for klassen_id in ids_lerngruppen:
                        klasse = lookup_lg.get(klassen_id,{})
                        if not klasse:
                            ergText+=f"Lerngruppe mit {klassen_id} nicht gefunden\n"
                            continue
                        bezeichnung = klasse.get("teamBez")
                        if (self.replaceSpecialChars):
                            bezeichnung = replace_chars(bezeichnung, my_char_map)

                        teams_liste.append(bezeichnung)
                else:
                    ergText+=f"⚠️  {nachname}, {vorname} hat keine Lerngruppe\n"

                kurse = "|".join(teams_liste)
                count += 1
                if (self.replaceSpecialChars):
                    nachname = replace_chars(nachname, my_char_map)
                    vorname = replace_chars(vorname, my_char_map)
                writer.writerow([referenzId, vorname, nachname, klassen, kurse])

        ergText+=(f"✅ CSV-Datei 'Teacher.csv' wurde mit {count} Einträgen erstellt.\n")
        return ergText

    def import_referenz_ids(self, master, art="schueler", idBez="id"):
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

        tk.Label(win, text=f"Spalte mit ID ({idBez}):").grid(row=0, column=0, sticky="w", padx=8, pady=6)
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
                        mapping[sid] = ref
                        continue
            result["mapping"] = mapping
            win.destroy()

        ttk.Button(win, text="OK", command=on_ok).grid(row=2, column=0, columnspan=2, pady=8)

        win.grab_set()
        win.wait_window()

        if "mapping" not in result:
            return "FEHLER: Es konnte keine Zuordnung erstellt werden\n"
        
        print(result["mapping"])

        # Objekte aktualisieren
        count_ref = 0
        count_id = 0
        for obj in getattr(self, art, []):
            objid = obj.get(idBez)
            print(objid)
            if objid in result["mapping"]:
                obj["referenzId"] = result["mapping"][objid]
                count_ref+=1
            else:
                obj["referenzId"] = objid
                count_id+=1

        print(f"{len(result['mapping'])} Referenz-IDs zugewiesen.")
        return f"{count_ref} Referenz-IDs zugewisen - {count_id} mal die {idBez} als Referenz\n"

    def edit_jahrgangsteams(self, master):
        # sicherstellen, dass das Attribut existiert
        if not hasattr(self, "jahrgangsteams") or self.jahrgangsteams is None:
            self.jahrgangsteams = {}

        win = tk.Toplevel(master)
        win.title("Jahrgangsteams bearbeiten")
        win.transient(master)
        win.grab_set()
        win.columnconfigure(1, weight=1)
        # größere Startgröße
        win.geometry("400x300")

        # Widgets
        ttk.Label(win, text="Jahrgang (z. B. 09, EF):").grid(row=0, column=0, sticky="w", padx=8, pady=(10,4))
        e_key = ttk.Entry(win, width=10)
        e_key.grid(row=0, column=1, sticky="w", padx=8, pady=(10,4))

        ttk.Label(win, text="Teams (kommagetrennt):").grid(row=1, column=0, sticky="nw", padx=8, pady=4)
        e_vals = ttk.Entry(win)
        e_vals.grid(row=1, column=1, sticky="ew", padx=8, pady=4)

        # Liste vorhandener Jahrgänge
        ttk.Label(win, text="Vorhandene Jahrgänge:").grid(row=2, column=0, sticky="nw", padx=8, pady=4)
        lb = tk.Listbox(win, height=8, exportselection=False)
        lb.grid(row=2, column=1, sticky="nsew", padx=8, pady=4)
        win.rowconfigure(2, weight=1)

        # Buttons
        btns = ttk.Frame(win)
        btns.grid(row=3, column=0, columnspan=2, sticky="e", padx=8, pady=8)
        b_add    = ttk.Button(btns, text="Neu/Übernehmen")
        b_delete = ttk.Button(btns, text="Löschen")
        b_close  = ttk.Button(btns, text="Schließen")
        b_add.grid(row=0, column=0, padx=4)
        b_delete.grid(row=0, column=1, padx=4)
        b_close.grid(row=0, column=2, padx=4)

        # Helper
        def normalize_values(text: str) -> list[str]:
            vals = [v.strip() for v in text.split(",") if v.strip()]
            # optional Duplikate entfernen, Reihenfolge bewahren:
            seen, out = set(), []
            for v in vals:
                if v not in seen:
                    seen.add(v); out.append(v)
            return out

        def refresh_listbox(select_key: str | None = None):
            lb.delete(0, tk.END)
            for k in sorted(self.jahrgangsteams.keys()):
                lb.insert(tk.END, k)
            if select_key and select_key in self.jahrgangsteams:
                idx = sorted(self.jahrgangsteams.keys()).index(select_key)
                lb.selection_clear(0, tk.END)
                lb.selection_set(idx)
                lb.see(idx)

        def load_from_selection(_evt=None):
            sel = lb.curselection()
            if not sel:
                return
            key = sorted(self.jahrgangsteams.keys())[sel[0]]
            e_key.delete(0, tk.END); e_key.insert(0, key)
            vals = self.jahrgangsteams.get(key, [])
            e_vals.delete(0, tk.END); e_vals.insert(0, ", ".join(vals))

        def add_or_update():
            key = e_key.get().strip()
            if not key:
                messagebox.showwarning("Hinweis", "Bitte Jahrgang eingeben.", parent=win)
                return
            vals = normalize_values(e_vals.get())
            self.jahrgangsteams[key] = vals
            refresh_listbox(select_key=key)

        def delete_selected():
            sel = lb.curselection()
            key = e_key.get().strip()
            # Bevorzugt: selektierten Key löschen; sonst Feld-Key
            if sel:
                key = sorted(self.jahrgangsteams.keys())[sel[0]]
            if not key or key not in self.jahrgangsteams:
                return
            if messagebox.askyesno("Löschen", f"Jahrgang '{key}' wirklich löschen?", parent=win):
                del self.jahrgangsteams[key]
                e_key.delete(0, tk.END)
                e_vals.delete(0, tk.END)
                refresh_listbox()

        # Bindings
        lb.bind("<<ListboxSelect>>", load_from_selection)
        b_add.configure(command=add_or_update)
        b_delete.configure(command=delete_selected)
        b_close.configure(command=win.destroy)
        win.protocol("WM_DELETE_WINDOW", win.destroy)

        # initial füllen
        refresh_listbox()
        win.wait_window()

def replace_chars(text: str, char_map: dict[str, str]) -> str:
    for old, new in char_map.items():
        text = text.replace(old, new)
    return text


if __name__=="__main__":
    g = Generator()
    

