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



if __name__=="__main__":
    g = Generator()
    g.configValues()

