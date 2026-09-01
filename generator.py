import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import csv
import re
import sys
import os
from collections import Counter
from enum import Enum
from config_gui import load_config, show_config_gui, show_noteam_gui
from ui_widgets import ToolTip
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

# Pseudo-kursartKuerzel für Lerngruppen ohne kursartKuerzel (None/leer/fehlend) - typischerweise
# die "normalen" Fachkurse, die in Schild kein besonderes Kürzel bekommen (im Gegensatz zu z.B.
# AGs oder Förderkursen). Wird als eigener Schlüssel in self.kursart_zuordnung geführt, damit
# diese Lerngruppen nicht unsichtbar durch die Zuordnung fallen (siehe get_ziel_fuer_lerngruppe,
# fehlende_kursart_zuordnungen, edit_kursart_zuordnung).
KEIN_KURSARTKUERZEL = "(ohne kursartKuerzel)"

# Startvorschlag für die Kursart-Zuordnung (welches kursartKuerzel gehört zu welcher
# Zielkategorie Arbeitsgruppe/Kurs/Gruppe, siehe Generator.ziel_spalten). Nur eine Vorbelegung
# für den Dialog edit_kursart_zuordnung(), basierend auf den bislang bekannten Kürzeln aus
# status.json bzw. den Fallback-Listen in config_gui.py/generator.py - keine feste Regel und wird
# nicht automatisch übernommen, sondern muss im Dialog bestätigt/angepasst und gespeichert werden.
KURSART_ZUORDNUNG_VORSCHLAG = {
    "AGGT": "arbeitsgruppe",
    "EGS1": "arbeitsgruppe",
    "FOGT": "arbeitsgruppe",
    "GK": "kurs",
    "LK": "kurs",
    "PUT": "kurs",
    "WPII": "kurs",
    KEIN_KURSARTKUERZEL: "kurs",  # normale Fachkurse ohne kursartKuerzel -> Standard "Kurs"
}


def _all_have(objs, key):
    """True, wenn objs nicht leer ist und jedes Element den key besitzt."""
    return bool(objs) and all(key in o for o in objs)


def _teambez_ok(lg):
    """True, wenn die Lerngruppe eine teamBez hat, oder das Fehlen ausschließlich daran liegt,
    dass ihr (noch) keine Schüler zugeordnet sind - z.B. Kurse ohne Kurswahl am Schuljahresanfang.
    Andere Ursachen (fehlende Bezeichnung/Kursartkürzel) deuten auf echte Datenprobleme hin und
    gelten weiterhin als nicht erledigt."""
    if "teamBez" in lg:
        return True
    return "kursartKuerzel" in lg and lg.get("bezeichnung") is not None and not lg.get("idsSchueler")


class WorkflowStep(Enum):
    """Benannte Zustände des Pflicht-Workflows (in der vorgesehenen Reihenfolge)."""
    ABSCHNITT_VERBUNDEN = "Abschnitts-ID geholt"
    LERNGRUPPEN_GEHOLT = "Lerngruppen geholt"
    LOOKUPS_ERSTELLT = "Lookup-Dictionaries erstellt"
    SCHUELER_ZU_LERNGRUPPEN = "Schüler-IDs zu Lerngruppen zugewiesen"
    TEAMBEZ_ERSTELLT = "Team-Bezeichnungen erstellt"
    KURSART_ZUORDNUNG = "Kursart-Zuordnung (Arbeitsgruppe/Kurs/Gruppe) vollständig"
    REFERENZ_IDS_SCHUELER = "Referenz-IDs für Schüler zugewiesen"
    LERNGRUPPEN_ZU_LEHRERN = "Lerngruppen-IDs zu Lehrern zugewiesen"
    KLASSENLEITUNG_ZU_LEHRERN = "Klassenleitungs-IDs zu Lehrern zugewiesen"
    REFERENZ_IDS_LEHRER = "Referenz-IDs für Lehrer zugewiesen"
    SCHUELER_CSV = "Schüler-CSV exportiert"
    SUS_EXTERN_CSV = "Externe-Schüler-CSV exportiert"
    LEHRER_CSV = "Lehrer-CSV exportiert"


class OptionalStep(Enum):
    """Benannte Zustände für sinnvolle, aber nicht zwingend nötige Schritte."""
    SCHUELER_AUS_DB = "Fehlende Schüler ergänzt"
    LEHRER_AUS_DB = "Fehlende Lehrer ergänzt"
    JAHRGANGSTEAMS = "Jahrgangsteams konfiguriert"
    TEAMS_NICHT_ERSTELLEN = "Teams vom Export ausgeschlossen"


class Generator():
    # Pflichtkette für die Button-Führung: (Zustand, alternative Buttons dafür, ist-erledigt-Prüfung)
    REQUIRED_CHAIN = [
        (WorkflowStep.ABSCHNITT_VERBUNDEN, ["Abschnitts-ID holen"],
            lambda g: getattr(g, "svws_abschnitts_id", None) is not None),
        (WorkflowStep.LERNGRUPPEN_GEHOLT, ["Lerngruppen holen"],
            lambda g: bool(getattr(g, "lerngruppen", []))),
        (WorkflowStep.LOOKUPS_ERSTELLT, ["generateLookupDicts"],
            lambda g: {"jahrgaenge", "klassen", "lehrer", "faecher", "lerngruppen", "schueler"}.issubset(g.lookupDict.keys())),
        (WorkflowStep.SCHUELER_ZU_LERNGRUPPEN, ["idsSchuelerZuLerngruppen"],
            lambda g: _all_have(getattr(g, "lerngruppen", []), "idsSchueler")),
        (WorkflowStep.TEAMBEZ_ERSTELLT, ["TeamBezErstellen"],
            lambda g: bool(getattr(g, "lerngruppen", [])) and all(_teambez_ok(lg) for lg in g.lerngruppen)),
        (WorkflowStep.KURSART_ZUORDNUNG, ["KursartZuordnung"],
            lambda g: bool(getattr(g, "lerngruppen", [])) and not g.fehlende_kursart_zuordnungen()),
        (WorkflowStep.REFERENZ_IDS_SCHUELER, ["Referenz-IDs aus File", "ReferenzIDs aus SuS-Ids"],
            lambda g: _all_have(getattr(g, "schueler", []), "referenzId")),
        (WorkflowStep.LERNGRUPPEN_ZU_LEHRERN, ["idsLerngruppenZuLehrern"],
            lambda g: _all_have(getattr(g, "lehrer", []), "idsLerngruppen")),
        (WorkflowStep.KLASSENLEITUNG_ZU_LEHRERN, ["idsKlassenleitungenZuLehrern"],
            lambda g: _all_have(getattr(g, "lehrer", []), "idsKlassenleitung")),
        (WorkflowStep.REFERENZ_IDS_LEHRER, ["LehrerReferenzen aus File", "L-ReferenzIDs aus kuerzel"],
            lambda g: _all_have(getattr(g, "lehrer", []), "referenzId")),
        (WorkflowStep.SCHUELER_CSV, ["schueler_csv"],
            lambda g: g.exportedFlags.get("schueler_csv", False)),
        (WorkflowStep.SUS_EXTERN_CSV, ["sus_extern_csv"],
            lambda g: g.exportedFlags.get("sus_extern_csv", False)),
        (WorkflowStep.LEHRER_CSV, ["lehrer_csv"],
            lambda g: g.exportedFlags.get("lehrer_csv", False)),
    ]

    # Optionale Schritte: (Zustand, Buttons, ist-sinnvoll-Prüfung, ist-erledigt-Prüfung oder None)
    OPTIONAL_STEPS = [
        (OptionalStep.SCHUELER_AUS_DB, ["ErgänzeSchülerAusDB"],
            lambda g: bool(getattr(g, "lerngruppen", [])), None),
        (OptionalStep.LEHRER_AUS_DB, ["ErgänzeLehrerAusDB"],
            lambda g: bool(getattr(g, "lerngruppen", [])), None),
        (OptionalStep.JAHRGANGSTEAMS, ["Jahrgangsteams"],
            lambda g: bool(getattr(g, "lerngruppen", [])), None),
        (OptionalStep.TEAMS_NICHT_ERSTELLEN, ["Teams nicht erstellen"],
            lambda g: _all_have(getattr(g, "lerngruppen", []), "teamBez"), None),
    ]

    def get_button_states(self) -> dict[str, str]:
        """Liefert für die Buttons der Führungs-Logik einen Status:
        'next' (nächster Pflichtschritt), 'done' (bereits erledigt) oder 'optional' (sinnvoll, aber nicht zwingend).
        Buttons ohne Eintrag sind entweder noch nicht dran oder nicht Teil der Führung."""
        states = {}

        # Pflichtkette: der erste noch nicht erledigte Schritt (inkl. aller alternativen Buttons dafür) wird 'next'
        current_step_assigned = False
        for _step, buttons, done_fn in self.REQUIRED_CHAIN:
            if done_fn(self):
                for b in buttons:
                    states[b] = "done"
            elif not current_step_assigned:
                for b in buttons:
                    states[b] = "next"
                current_step_assigned = True
            # weiter in der Zukunft liegende Schritte bleiben unmarkiert

        # Optionale Schritte
        for _step, buttons, relevant_fn, done_fn in self.OPTIONAL_STEPS:
            if not relevant_fn(self):
                continue
            is_done = done_fn(self) if done_fn else False
            for b in buttons:
                states[b] = "done" if is_done else "optional"

        return states

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
        # {jahrgang: {"arbeitsgruppe": [...], "kurs": [...], "gruppe": [...]}} - je Zielkategorie
        # (siehe self.ziel_spalten) eine Liste zusätzlicher Team-Namen für diesen Jahrgang.
        # "*" ist laut MNSpro-Doku der Platzhalter für bereits vorhandene Arbeitsgruppen, daher
        # unter "arbeitsgruppe" beim Sonderfall "Lehrer" (gilt für alle Lehrkräfte).
        self.jahrgangsteams = {"Lehrer": {"arbeitsgruppe": ["*"], "kurs": [], "gruppe": []}}
        self.noTeams = [] #Liste von Teambezeichnungen, die nicht erstellt werden sollen
        self.replaceSpecialChars = True # Sonderzeichen in Gruppen oder Namen ersetzen
        self.exportedFlags = {} # merkt sich für die Button-Führung, welche CSV-Exporte bereits erfolgreich liefen

        # Zuordnung Lerngruppe -> Zielkategorie fürs neue MNSpro-Cloud-Format (siehe TODO.md).
        # "Zielspalte"/"Zielkategorie" meint hier immer die Unterscheidung zwischen den drei
        # CSV-Spalten Arbeitsgruppen, Cloud#Kurs und Cloud#Gruppe (siehe README.md, Abschnitt
        # "CSV-Import-Format für MNSpro Cloud"). Zentrale Stelle Ziel-Schlüssel -> CSV-Spaltenname,
        # damit z.B. ein Wegfall von "Arbeitsgruppen" in MNSpro nur hier angepasst werden muss.
        self.ziel_spalten = {"arbeitsgruppe": "Arbeitsgruppen", "kurs": "Cloud#Kurs", "gruppe": "Cloud#Gruppe"}
        self.kursart_zuordnung = {}       # {kursartKuerzel: Ziel-Schlüssel}
        self.bezeichnung_muster = []      # [{"pattern": regex-str, "ziel": Ziel-Schlüssel}, ...], erstes Match gewinnt
        self.teambez_rewrite = []         # [{"pattern": regex-str, "replace": str}, ...], sed-artig
                                           # sequenziell (nicht "erstes Match gewinnt") auf teamBez
                                           # angewandt, siehe addTeamBezZuLerngruppen()
        self.zuordnung_overrides = {}     # {lerngruppen_id: Ziel-Schlüssel}, höchste Priorität
        self.besitzer_markieren = True    # Kursleiter (idsLehrer) beim Export als Besitzer ("^") markieren
        self.lehrer_ohne_kurs_exportieren = False
        # {Jahrgang: {Ziel-Schlüssel: Wert}} für den Button "Schüler aufräumen" (siehe
        # edit_schueler_aufraeumen()): pro Jahrgang ein fester Wert je Zielspalte. Wird NUR beim
        # eigenen Export-Button "Schüler.csv erstellen" in jenem Dialog angewandt (writeSuSCSV mit
        # jahrgangs_override) - der normale schueler_csv-Export ignoriert diese Werte komplett.
        # "*" = MNSpro-Cloud-Konvention: beim Import bleibt die bestehende Zuordnung erhalten;
        # "" = Spalte für alle Schüler dieses Jahrgangs leeren; alles andere wird wörtlich
        # eingetragen. Jeder vorkommende Jahrgang bekommt beim Öffnen des Dialogs automatisch
        # einen Eintrag (Standard: alle drei Spalten leer).
        self.schueler_aufraeumen_werte = {}
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

    def configNoTeams(self, root):
        initial = {}
        # Liste aller Teambezeichnungen aus den lerngruppen extrahieren
        initial["alle"] = sorted(collect_values(getattr(self,"lerngruppen",[]),"teamBez")) 
        initial["noTeams"] = self.noTeams

        result = show_noteam_gui(root, initial)

        if (result):
            print(f"Result: {result}")
            if (result != self.noTeams):
                print(f"Update self.noTeams to {result}")
                self.noTeams = result

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
        lerngruppen_export = sv.gibLerngruppen(self.svws_abschnitts_id,1) # Lerngruppe ID 1 ist lms.logineo
        for key, value in lerngruppen_export.items():
            if key in keys:
                print(f"Key von Lerngruppen wird übertragen: {key}")
                setattr(self, key, value)
        return lerngruppen_export

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

    def ergaenzeSchueler(self, statusList=[2, 6]):
        """ ergänzt fehlende Schüler aus der Datenbank (z.B. Schuljahresanfang, noch keiner Lerngruppe zugeordnet)
        statusList schränkt ein, welche Schüler-Status übernommen werden (2 - aktiv, 6 - extern) """
        ergText = ""

        # sicherstellen, dass eine Abschnitts-ID vorhanden ist
        if not self.svws_abschnitts_id:
            ergText += "Abschnitts-ID war noch nicht vorhanden, wird geholt\n"
            self.initAbschnittsID()
        if not self.svws_abschnitts_id:
            ergText += "⚠️ FEHLER: Es konnte keine Abschnitts-ID ermittelt werden\n"
            return ergText

        schueler_export = sv.gibSchuelerListe(self.svws_abschnitts_id)
        ergText += f"Es gibt {len(schueler_export)} Schüler in der Datenbank für den Abschnitt\n"

        # sicherstellen, dass Strukturen existieren
        if not hasattr(self, "schueler"):
            ergText += "Die Schülerdaten waren noch gar nicht vorhanden\n"
            self.schueler = []
        if "schueler" not in self.lookupDict:
            ergText += "LookupDicts müssen noch erstellt werden\n"
            self.generateLookups()

        # alle Schüler aus der Datenbank durchgehen (auch die ohne Lerngruppe)
        count = 0
        countStatus = 0
        for s in schueler_export:
            sid = s.get("id")
            if sid in self.lookupDict["schueler"]:
                continue
            if s.get("status") not in statusList:
                countStatus += 1
                continue
            ergText += f'Schüler {s.get("nachname","?")}, {s.get("vorname","?")} mit id {sid} wird übernommen\n'
            self.lookupDict["schueler"][sid] = s
            self.schueler.append(s)
            count += 1

        ergText += f"✅ Es wurden {count} zusätzliche Schüler geladen (Status {statusList})\n"
        if count > 0:
            ergText += ("⚠️ ACHTUNG: Diese Schüler wurden direkt aus der Datenbank ergänzt und NICHT über den\n"
                        "⚠️ Lernplattform-Export der Lerngruppen geholt. Dabei wird NICHT geprüft, ob eine Zustimmung\n"
                        "⚠️ zum Export in die Lernplattform vorliegt! Bitte vor dem Export unbedingt in Schild3 prüfen,\n"
                        "⚠️ welche der ergänzten Schüler exportiert werden dürfen, und ggf. nicht zustimmende Schüler\n"
                        "⚠️ wieder entfernen.\n")
        if countStatus > 0:
            ergText += f"ℹ️ {countStatus} Schüler wurden wegen ihres Status übersprungen\n"
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

    def pruefe_ids_in_lerngruppen(self) -> str:
        """Prüft für jede Lerngruppe, ob alle in idsLehrer/idsSchueler referenzierten IDs
        tatsächlich zu einem existierenden Lehrer bzw. Schüler gehören (self.lookupDict) - z.B.
        um Karteileichen durch gelöschte/verschobene Personen in der Schild-DB zu finden. Andere
        ID-Verweise (idsLerngruppen bei Schülern/Lehrern, idsKlassenleitung, ...) werden hier
        bewusst nicht geprüft, weil sie an anderer Stelle (z.B. beim CSV-Export) ohnehin auffallen
        würden. Gibt für jede betroffene Lerngruppe eine Zeile im Format
        "Lerngruppe {id} mit teamBez {...}: Lehrer mit ID ... fehlt, Schüler mit IDs ... fehlen"
        zurück, oder eine Erfolgsmeldung, wenn keine fehlenden IDs gefunden wurden."""
        if not self.lookupDict.get("lehrer") or not self.lookupDict.get("schueler"):
            self.generateLookups()
        lookup_lehrer = self.lookupDict.get("lehrer", {})
        lookup_schueler = self.lookupDict.get("schueler", {})

        def teil(ids: list, bezeichnung: str) -> str | None:
            if not ids:
                return None
            ids_str = ", ".join(str(i) for i in ids)
            if len(ids) == 1:
                return f"{bezeichnung} mit ID {ids_str} fehlt"
            return f"{bezeichnung} mit IDs {ids_str} fehlen"

        ergText = ""
        anzahl_betroffen = 0
        for lg in getattr(self, "lerngruppen", []):
            fehlende_lehrer = [lid for lid in lg.get("idsLehrer", []) if lid not in lookup_lehrer]
            fehlende_schueler = [sid for sid in lg.get("idsSchueler", []) if sid not in lookup_schueler]
            teile = [t for t in (teil(fehlende_lehrer, "Lehrer"), teil(fehlende_schueler, "Schüler")) if t]
            if teile:
                anzahl_betroffen += 1
                bez = lg.get("teamBez") or lg.get("bezeichnung") or "?"
                ergText += f"⚠️ Lerngruppe {lg.get('id', '?')} mit teamBez {bez}: {', '.join(teile)}\n"

        if anzahl_betroffen:
            ergText += f"❌ {anzahl_betroffen} von {len(getattr(self, 'lerngruppen', []))} Lerngruppen haben fehlende ID-Referenzen\n"
        else:
            ergText += f"✅ Alle ID-Referenzen (idsLehrer/idsSchueler) in {len(getattr(self, 'lerngruppen', []))} Lerngruppen sind gültig\n"
        return ergText

    def loescheLeereLerngruppen(self, master=None) -> str:
        """Entfernt alle Lerngruppen ohne Schüler (idsSchueler leer oder fehlend) aus den Daten und
        bereinigt dabei alle Verweise auf ihre ID in anderen Elementen:
        - self.lookupDict["lerngruppen"]
        - self.lehrer[*]["idsLerngruppen"]
        - self.schueler[*]["idsLerngruppen"]
        - self.zuordnung_overrides (manuelle Kursart-Overrides, siehe TODO.md Schritt 2)

        Voraussetzung: idsSchuelerZuLerngruppen wurde bereits ausgeführt - sonst hätte noch keine
        Lerngruppe ein idsSchueler-Feld und es würde fälschlich alles als "leer" gelten.

        master: Elternfenster für die Sicherheitsabfrage vor dem Löschen (messagebox); ohne master
        wird ohne Rückfrage gelöscht (z.B. für Tests/Konsolennutzung)."""
        alle_lerngruppen = getattr(self, "lerngruppen", [])
        if not alle_lerngruppen:
            return "Keine Lerngruppen vorhanden.\n"
        if not any("idsSchueler" in lg for lg in alle_lerngruppen):
            return "FEHLER: Noch keine Lerngruppe hat ein Feld idsSchueler - bitte zuerst idsSchuelerZuLerngruppen ausführen.\n"

        leere = [lg for lg in alle_lerngruppen if not lg.get("idsSchueler")]
        if not leere:
            return "Keine leeren Lerngruppen gefunden.\n"

        namen = sorted(lg.get("teamBez") or lg.get("bezeichnung") or str(lg.get("id")) for lg in leere)
        if master is not None:
            vorschau = "\n".join(namen[:15]) + (f"\n... und {len(namen)-15} weitere" if len(namen) > 15 else "")
            if not messagebox.askyesno("Leere Lerngruppen löschen",
                    f"{len(leere)} Lerngruppen ohne Schüler gefunden:\n\n{vorschau}\n\nWirklich löschen?", parent=master):
                return "Abgebrochen - keine Lerngruppen gelöscht.\n"

        leere_ids = {lg.get("id") for lg in leere}

        # aus der Hauptliste entfernen
        self.lerngruppen = [lg for lg in alle_lerngruppen if lg.get("id") not in leere_ids]

        # aus dem Lookup-Dict entfernen (falls vorhanden)
        lookup_lg = getattr(self, "lookupDict", {}).get("lerngruppen")
        if lookup_lg:
            for lg_id in leere_ids:
                lookup_lg.pop(lg_id, None)

        # Verweise bei Lehrern bereinigen
        anz_lehrer_verweise = 0
        for lehrer in getattr(self, "lehrer", []):
            ids = lehrer.get("idsLerngruppen")
            if ids:
                neu = [i for i in ids if i not in leere_ids]
                anz_lehrer_verweise += len(ids) - len(neu)
                lehrer["idsLerngruppen"] = neu

        # Verweise bei Schülern bereinigen
        anz_schueler_verweise = 0
        for schueler in getattr(self, "schueler", []):
            ids = schueler.get("idsLerngruppen")
            if ids:
                neu = [i for i in ids if i not in leere_ids]
                anz_schueler_verweise += len(ids) - len(neu)
                schueler["idsLerngruppen"] = neu

        # verwaiste manuelle Kursart-Overrides bereinigen (Schritt 2, siehe TODO.md)
        anz_overrides = 0
        for lg_id in list(self.zuordnung_overrides.keys()):
            if lg_id in leere_ids:
                del self.zuordnung_overrides[lg_id]
                anz_overrides += 1

        beispiele = ", ".join(namen[:10]) + (f", ... und {len(namen)-10} weitere" if len(namen) > 10 else "")
        resultText = f"🗑️ {len(leere)} leere Lerngruppen gelöscht: {beispiele}\n"
        resultText += f"Bereinigte Verweise: {anz_lehrer_verweise} bei Lehrern, {anz_schueler_verweise} bei Schülern"
        if anz_overrides:
            resultText += f", {anz_overrides} verwaiste Kursart-Overrides entfernt"
        resultText += "\n"
        return resultText

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
                                    resultText+=f"WARNUNG: Lerngruppe {prefix} - {lgbezeichnung} mit ID {lg.get('id','?')} hat als Jahrgangsteam Schüler mehrerer Jahrgänge: {self.get_kl_jg_zu_schuelerIDListe(idsSchueler, art='jahrgaenge')}\n"
                                jahrgang = prefix
                            else:
                                #Klasse eines Schuelers holen
                                prefix = self.get_klasse_von_schueler(idsSchueler[0])
                                if (len(self.get_kl_jg_zu_schuelerIDListe(idsSchueler, art="klassen"))!=1):
                                    resultText+=f"WARNUNG: Lerngruppe {prefix} - {lgbezeichnung} mit ID {lg.get('id','?')} hat als Klassenteam Schüler mehrerer Klassen: {self.get_kl_jg_zu_schuelerIDListe(idsSchueler, art='klassen')}\n"
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

        resultText += self._wende_teambez_rewrite_auf_lerngruppen_an()
        return resultText

    def wende_teambez_rewrite_an(self, text: str) -> tuple[str, list[int]]:
        """Wendet self.teambez_rewrite sed-artig sequenziell auf `text` an: jede Regel wird der
        Reihe nach auf das (ggf. schon von einer vorherigen Regel veränderte) Ergebnis angewandt -
        anders als bei self.bezeichnung_muster gewinnt hier NICHT nur die erste passende Regel,
        sondern es können mehrere Regeln nacheinander greifen. Gibt den (ggf. unveränderten) Text
        sowie die Indizes der Regeln zurück, die tatsächlich etwas ersetzt haben (für Statistik)."""
        getroffen = []
        for i, regel in enumerate(self.teambez_rewrite):
            pattern = regel.get("pattern", "")
            replace = regel.get("replace", "")
            if not pattern:
                continue
            try:
                neu, anzahl = re.subn(pattern, replace, text)
            except re.error:
                continue  # ungültiges Muster wird ignoriert statt das Programm abzubrechen
            if anzahl:
                text = neu
                getroffen.append(i)
        return text, getroffen

    def _wende_teambez_rewrite_auf_lerngruppen_an(self) -> str:
        """Wendet self.teambez_rewrite auf lg["teamBez"] aller Lerngruppen an (im Anschluss an
        addTeamBezZuLerngruppen aufgerufen) und liefert einen Ergebnistext mit der Trefferanzahl
        je Regel, z.B. um zu prüfen, ob eine Regel überhaupt gegriffen hat."""
        if not self.teambez_rewrite:
            return ""
        treffer_je_regel = Counter()
        for lg in getattr(self, "lerngruppen", []):
            teamBez = lg.get("teamBez")
            if not teamBez:
                continue
            neu, getroffen = self.wende_teambez_rewrite_an(teamBez)
            if getroffen:
                lg["teamBez"] = neu
                for i in getroffen:
                    treffer_je_regel[i] += 1

        resultText = "TeamBez-Rewrite-Regeln angewandt:\n"
        for i, regel in enumerate(self.teambez_rewrite):
            resultText += (f'  {regel.get("pattern","")!r} → {regel.get("replace","")!r}: '
                            f'{treffer_je_regel.get(i, 0)}x\n')
        return resultText

    def get_ziel_fuer_lerngruppe(self, lg: dict) -> str | None:
        """Ermittelt die Zielkategorie (Schlüssel aus self.ziel_spalten, z.B. "kurs") für eine
        Lerngruppe, für das neue MNSpro-Cloud-Exportformat. "Zielkategorie" meint die
        Unterscheidung zwischen den drei CSV-Spalten Arbeitsgruppen / Cloud#Kurs / Cloud#Gruppe.

        Prioritätsreihenfolge:
        1. manueller Einzel-Override über die Lerngruppen-ID (self.zuordnung_overrides)
        2. Bezeichnungs-Muster (Regex gegen teamBez, ersatzweise bezeichnung falls TeamBez noch
           nicht erstellt wurde; in Reihenfolge geprüft, erstes Match gewinnt)
        3. kursartKuerzel-Zuordnungstabelle (self.kursart_zuordnung) - Lerngruppen ohne
           kursartKuerzel (None/leer/fehlend, typischerweise normale Fachkurse) werden dabei unter
           dem Pseudo-Kürzel KEIN_KURSARTKUERZEL geführt, damit sie nicht unsichtbar durchfallen.

        Liefert None, wenn keine der drei Stufen zutrifft (= noch nicht klassifiziert).
        """
        lg_id = lg.get("id")
        if lg_id is not None and lg_id in self.zuordnung_overrides:
            return self.zuordnung_overrides[lg_id]

        bezeichnung = lg.get("teamBez") or lg.get("bezeichnung") or ""
        for regel in self.bezeichnung_muster:
            pattern = regel.get("pattern", "")
            if not pattern:
                continue
            try:
                if re.search(pattern, bezeichnung):
                    return regel.get("ziel")
            except re.error:
                continue  # ungültiges Muster wird ignoriert statt das Programm abzubrechen

        kursartKuerzel = lg.get("kursartKuerzel") or KEIN_KURSARTKUERZEL
        if kursartKuerzel in self.kursart_zuordnung:
            return self.kursart_zuordnung[kursartKuerzel]

        return None

    def fehlende_kursart_zuordnungen(self) -> list:
        """Liefert alle in self.lerngruppen vorkommenden kursartKuerzel (sortiert), für die noch
        keine Zielkategorie (Arbeitsgruppe/Kurs/Gruppe, siehe self.ziel_spalten) in
        self.kursart_zuordnung hinterlegt ist. Lerngruppen ohne kursartKuerzel (None/leer/fehlend -
        typischerweise normale Fachkurse) zählen dabei unter dem Pseudo-Kürzel
        KEIN_KURSARTKUERZEL mit, damit sie nicht unsichtbar durchfallen. Grundlage für den
        Pflicht-Dialog zur Kursart-Zuordnung (edit_kursart_zuordnung)."""
        vorhandene = {lg.get("kursartKuerzel") or KEIN_KURSARTKUERZEL for lg in getattr(self, "lerngruppen", [])}
        return sorted(vorhandene - set(self.kursart_zuordnung.keys()))

    def zuordnung_uebersicht(self) -> str:
        """Kontroll-/Vorschau-Report (Schritt 4, siehe TODO.md): zeigt je Zielkategorie
        (Arbeitsgruppe/Cloud#Kurs/Cloud#Gruppe, siehe self.ziel_spalten) die betroffenen
        Lerngruppen - Grundlage ist get_ziel_fuer_lerngruppe() für jede einzelne Lerngruppe.
        Warnt außerdem vor
        - Lerngruppen, die (noch) keiner Zielkategorie zugeordnet werden können, und
        - Team-Bezeichnungen, die in mehreren Zielkategorien gleichzeitig auftauchen (die drei
          Zielkategorien sind getrennte Namensräume in MNSpro - das kann dort zu Verwechslungen
          führen).
        Gedacht als letzter Kontrollschritt vor dem eigentlichen CSV-Export."""
        lerngruppen = getattr(self, "lerngruppen", [])
        if not lerngruppen:
            return "Keine Lerngruppen vorhanden.\n"

        je_ziel = {ziel: [] for ziel in self.ziel_spalten}
        nicht_klassifiziert = []
        name_zu_zielen = {}  # Team-Bezeichnung -> Menge der Zielkategorien, in denen sie auftaucht

        for lg in lerngruppen:
            name = lg.get("teamBez") or lg.get("bezeichnung") or f'ID {lg.get("id")}'
            lg_id = lg.get("id")
            ziel = self.get_ziel_fuer_lerngruppe(lg)
            if ziel is None:
                nicht_klassifiziert.append(lg)
                continue
            je_ziel.setdefault(ziel, []).append((name, lg_id))
            name_zu_zielen.setdefault(name, set()).add(ziel)

        resultText = f"Zuordnungs-Übersicht ({len(lerngruppen)} Lerngruppen gesamt):\n\n"

        for ziel, spalte in self.ziel_spalten.items():
            eintraege = sorted(je_ziel.get(ziel, []))
            resultText += f"=== {spalte} ({ziel}) - {len(eintraege)} Lerngruppen ===\n"
            for name, lg_id in eintraege:
                resultText += f"  {name} (id: {lg_id})\n"
            resultText += "\n"

        if nicht_klassifiziert:
            resultText += f"⚠️ {len(nicht_klassifiziert)} Lerngruppen sind NICHT klassifiziert:\n"
            for lg in sorted(nicht_klassifiziert, key=lambda lg: lg.get("bezeichnung") or ""):
                name = lg.get("teamBez") or lg.get("bezeichnung") or f'ID {lg.get("id")}'
                kuerzel = lg.get("kursartKuerzel") or KEIN_KURSARTKUERZEL
                resultText += f"  {name} (id: {lg.get('id')}) (kursartKuerzel: {kuerzel})\n"
            resultText += "\n"
        else:
            resultText += "✅ Alle Lerngruppen sind klassifiziert.\n\n"

        doppelte = {name: ziele for name, ziele in name_zu_zielen.items() if len(ziele) > 1}
        if doppelte:
            resultText += (f"⚠️ {len(doppelte)} Team-Bezeichnungen tauchen in mehreren Zielkategorien auf "
                            "(getrennte Namensräume - kann in MNSpro zu Verwechslungen führen):\n")
            for name, ziele in sorted(doppelte.items()):
                spalten = ", ".join(self.ziel_spalten.get(z, z) for z in sorted(ziele))
                resultText += f"  {name}: {spalten}\n"
            resultText += "\n"

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
    
    def writeSuSCSV(self, statusList = [2], filename="Student.csv", jahrgangs_override: dict | None = None):
        # Status 2 - aktiv, 6 - extern
        # jahrgangs_override: {Jahrgang: {Ziel-Schlüssel: Wert}}, siehe edit_schueler_aufraeumen() -
        # wird NUR gesetzt, wenn diese Methode über den Button "Schüler.csv erstellen" in jenem
        # Dialog aufgerufen wird. Der normale schueler_csv-Export ruft writeSuSCSV() ohne diesen
        # Parameter auf und bleibt dadurch komplett unbeeinflusst von self.schueler_aufraeumen_werte.
        # Ist er gesetzt, entfällt die Lerngruppen-Berechnung komplett: für jeden Schüler wird je
        # Zielspalte WÖRTLICH der für seinen Jahrgang hinterlegte Wert geschrieben ("*" = MNSpro-
        # Cloud-Konvention "bestehende Zuordnung beim Import beibehalten", "" = Spalte leeren).
        ergText = ""
        countNoTeams = 0
        countNichtKlassifiziert = 0
        nicht_klassifiziert_beispiele = set()
        # Voraussetzungen prüfen (ReferenzID vorhanden, TeamsBez in den Lerngruppen)
        if not all("referenzId" in schueler for schueler in getattr(self,"schueler",{})):
            return "Keine Schüler vorhanden oder nicht alle haben eine referenzId\n"
        if not all("teamBez" in lerngruppe for lerngruppe in getattr(self,"lerngruppen",{})):
            return "Nicht alle Lerngruppen haben eine Teams-Bezeichnung (key: teamBez)\n"
        self.normalisiere_jahrgangsteams()
        with open(filename, mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile, delimiter=";")
            # Neues MNSpro-Cloud-Format (siehe README.md, Abschnitt "CSV-Import-Format für MNSpro
            # Cloud"): statt einer Gruppen-Spalte je eine Spalte pro Zielkategorie (self.ziel_spalten)
            if (statusList != [2]):
                writer.writerow(["ReferenzId", "Vorname", "Nachname", "Klassen"] + list(self.ziel_spalten.values()))  # Kopfzeile
            else:
                writer.writerow(["ReferenzId", "Vorname", "Nachname", "Klasse"] + list(self.ziel_spalten.values()))  # Kopfzeile

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

                if jahrgangs_override is not None:
                    # Schüler aufräumen: keine Lerngruppen-Berechnung, wörtlich der für den
                    # Jahrgang hinterlegte Wert (fehlt der Jahrgang im Override, z.B. weil er dem
                    # Schüler nicht zugeordnet ist, wird sicherheitshalber geleert statt normal
                    # berechnet - siehe Docstring von edit_schueler_aufraeumen).
                    jahrgang = self.get_jahrgang_von_schueler(s.get("id"))
                    eintrag = jahrgangs_override.get(jahrgang, {})
                    zielspalten_werte = [eintrag.get(ziel, "") for ziel in self.ziel_spalten]
                else:
                    jahrgang = self.get_jahrgang_von_schueler(s.get("id")) # für Jahrgangsteams
                    ids_lerngruppen = s.get("idsLerngruppen", [])

                    # Team-Listen je Zielkategorie, mit den Jahrgangsteams vorbelegt
                    jahrgangs_eintrag = self.jahrgangsteams.get(jahrgang, {})
                    teams_je_ziel = {ziel: list(jahrgangs_eintrag.get(ziel, [])) for ziel in self.ziel_spalten}

                    if ids_lerngruppen:
                        for lg_id in ids_lerngruppen:
                            lg = lookup_lg.get(lg_id,{})
                            if not lg:
                                ergText+=f"Lerngruppe mit {lg_id} nicht gefunden\n"
                                continue
                            bezeichnung = lg.get("teamBez")
                            if (bezeichnung not in self.noTeams):
                                ziel = self.get_ziel_fuer_lerngruppe(lg)
                                if ziel is None:
                                    countNichtKlassifiziert += 1
                                    nicht_klassifiziert_beispiele.add(bezeichnung)
                                    continue
                                if (self.replaceSpecialChars):
                                    bezeichnung = replace_chars(bezeichnung, my_char_map)
                                teams_je_ziel.setdefault(ziel, []).append(bezeichnung)
                            else:
                                countNoTeams+=1
                    else:
                        ergText+=f"⚠️  {nachname}, {vorname} ({klasse}) hat keine Lerngruppe\n"

                    zielspalten_werte = ["|".join(teams_je_ziel.get(ziel, [])) for ziel in self.ziel_spalten]
                count += 1
                if (self.replaceSpecialChars):
                    nachname = replace_chars(nachname, my_char_map)
                    vorname = replace_chars(vorname, my_char_map)
                writer.writerow([referenzId, vorname, nachname, klasse] + zielspalten_werte)
        if jahrgangs_override is not None:
            ergText += "ℹ️ Schüler aufräumen: Spaltenwerte wurden wörtlich je Jahrgang eingetragen, keine Lerngruppen-Berechnung:\n"
            for jahrgang in sorted(jahrgangs_override):
                eintrag = jahrgangs_override.get(jahrgang, {})
                teile = []
                for ziel, spaltenname in self.ziel_spalten.items():
                    wert = eintrag.get(ziel, "")
                    if wert == "":
                        teile.append(f"{spaltenname}=geleert")
                    elif wert == "*":
                        teile.append(f"{spaltenname}='*' (bestehende Zuordnung bleibt beim Import erhalten)")
                    else:
                        teile.append(f"{spaltenname}={wert!r}")
                ergText += f"   Jahrgang '{jahrgang}': {', '.join(teile)}\n"
        if countNoTeams > 0: ergText+=(f"ℹ️ Es wurden {countNoTeams} Verknüpfungen wegen nicht zu erstellender Teams verhindert\n")
        if countNichtKlassifiziert > 0:
            beispiele = ", ".join(sorted(nicht_klassifiziert_beispiele)[:10])
            ergText += (f"⚠️ {countNichtKlassifiziert} Verknüpfungen wegen nicht klassifizierter Lerngruppen "
                        f"übersprungen (z.B. {beispiele}) - siehe ZuordnungUebersicht/KursartZuordnung\n")
        ergText+=(f"✅ CSV-Datei '{filename}' wurde mit {count} Einträgen erstellt.\n")
        self.exportedFlags["sus_extern_csv" if filename == "StudentExternal.csv" else "schueler_csv"] = True
        return ergText

    def edit_schueler_aufraeumen(self, master) -> str:
        """Dialog zur Pflege von self.schueler_aufraeumen_werte UND (über den eigenen Button
        "Schüler.csv erstellen") zum Export einer davon komplett unabhängigen Sonder-Schüler-CSV:
        pro Jahrgang, der aktuell unter den Schülern vorkommt, ein fester Wert je Zielkategorie
        (Arbeitsgruppe/Cloud#Kurs/Cloud#Gruppe, siehe self.ziel_spalten) - analog zu
        edit_kursart_zuordnung eine Zeile je vorkommendem Schlüssel (hier: Jahrgang statt
        kursartKuerzel), Standardwert "" (leer). "*" landet dabei buchstäblich in der Spalte -
        das ist eine MNSpro-Cloud-Konvention: beim Import bedeutet "*" dort "bestehende Zuordnung
        beibehalten"; leer löscht die Spalte für alle Schüler dieses Jahrgangs; alles andere wird
        wörtlich eingetragen (z.B. eine feste Lizenzgruppe).
        WICHTIG: Der normale "schueler_csv"/"sus_extern_csv"-Export (writeSuSCSV ohne
        jahrgangs_override) nimmt auf diese Werte KEINE Rücksicht - die hier gepflegte CSV ist ein
        bewusst getrennter Vorgang, ausgelöst über zwei eigene Buttons in diesem Dialog: "Schüler.csv
        erstellen (aktiv)" (Status 2, Datei Student_clean.csv) und "... (extern)" (Status 6, Datei
        StudentExternal_clean.csv) - eigene Dateinamen ("_clean"-Suffix), damit sie sich von den
        Dateien der normalen Export-Buttons unterscheiden. Da JEDER
        vorkommende Jahrgang einen Eintrag bekommt (Standard "leer"), wird beim Erstellen für
        wirklich jeden Schüler eine der drei Regeln angewandt - es gibt keinen impliziten
        Rückfall auf die Lerngruppen-Berechnung. Die Zeilenbeschriftung zeigt "aktiv/extern" an,
        sofern für diesen Jahrgang externe Schüler vorkommen, sonst die Gesamtanzahl.
        Mit "Speichern & Schließen" werden die Werte nur gemerkt (landen dann auch in status.json,
        da self.schueler_aufraeumen_werte Teil von self.__dict__ ist), ohne CSV zu erzeugen.
        Gibt bei "Schüler.csv erstellen (...)" den Exportbericht von writeSuSCSV() zurück, sonst ""."""
        if not hasattr(self, "schueler_aufraeumen_werte") or self.schueler_aufraeumen_werte is None:
            self.schueler_aufraeumen_werte = {}

        schueler = getattr(self, "schueler", [])
        if not schueler:
            messagebox.showinfo("Schüler aufräumen",
                "Keine Schüler vorhanden - bitte zuerst Lerngruppen/Schüler holen.", parent=master)
            return ""

        alle_jahrgaenge = sorted({j for j in (self.get_jahrgang_von_schueler(s.get("id")) for s in schueler) if j})
        jahrgaenge_je_schueler = {s.get("id"): self.get_jahrgang_von_schueler(s.get("id")) for s in schueler}
        anzahl_aktiv = Counter(jahrgaenge_je_schueler[s.get("id")] for s in schueler if s.get("status") == 2)
        anzahl_extern = Counter(jahrgaenge_je_schueler[s.get("id")] for s in schueler if s.get("status") == 6)
        anzahl_gesamt = Counter(jahrgaenge_je_schueler.values())
        # Für jeden vorkommenden Jahrgang einen Eintrag sicherstellen (Standard: alle drei Spalten leer)
        for jahrgang in alle_jahrgaenge:
            eintrag = self.schueler_aufraeumen_werte.setdefault(jahrgang, {})
            for ziel in self.ziel_spalten:
                eintrag.setdefault(ziel, "")

        win = tk.Toplevel(master)
        win.title("Schüler aufräumen - feste Spaltenwerte je Jahrgang")
        win.transient(master)
        win.grab_set()
        win.columnconfigure(tuple(range(len(self.ziel_spalten) + 1)), weight=1)

        ttk.Label(win, text="Jahrgang").grid(row=0, column=0, sticky="w", padx=8, pady=(10, 2))
        for c, spaltenname in enumerate(self.ziel_spalten.values(), start=1):
            ttk.Label(win, text=spaltenname).grid(row=0, column=c, sticky="w", padx=8, pady=(10, 2))
        info = ttk.Label(win, foreground="#555555", wraplength=460, justify="left",
                          text='leer = Spalte für alle Schüler dieses Jahrgangs löschen   •   '
                               '* = bestehende Zuordnung bleibt beim MNSpro-Import erhalten   •   '
                               'sonst: dieser Text wird wörtlich eingetragen')
        info.grid(row=1, column=0, columnspan=len(self.ziel_spalten) + 1, sticky="w", padx=8, pady=(0, 8))

        entries = {}  # Jahrgang -> {Ziel-Schlüssel: Entry-Widget}
        for i, jahrgang in enumerate(alle_jahrgaenge, start=2):
            if anzahl_extern[jahrgang] > 0:
                beschriftung = f"{jahrgang} (aktiv: {anzahl_aktiv[jahrgang]} / extern: {anzahl_extern[jahrgang]})"
            else:
                beschriftung = f"{jahrgang} ({anzahl_gesamt[jahrgang]} Schüler)"
            ttk.Label(win, text=beschriftung).grid(row=i, column=0, sticky="w", padx=8, pady=2)
            entries[jahrgang] = {}
            for c, ziel in enumerate(self.ziel_spalten, start=1):
                e = ttk.Entry(win, width=14)
                e.insert(0, self.schueler_aufraeumen_werte[jahrgang].get(ziel, ""))
                e.grid(row=i, column=c, sticky="ew", padx=8, pady=2)
                entries[jahrgang][ziel] = e

        def werte_uebernehmen():
            for jahrgang, e_kategorien in entries.items():
                self.schueler_aufraeumen_werte[jahrgang] = {ziel: e.get() for ziel, e in e_kategorien.items()}

        ergebnis = {"text": ""}

        def abbrechen():
            win.destroy()

        def speichern_schliessen():
            werte_uebernehmen()
            win.destroy()

        def erstellen(statusList, filename):
            werte_uebernehmen()
            win.destroy()
            ergebnis["text"] = self.writeSuSCSV(statusList=statusList, filename=filename,
                                                 jahrgangs_override=dict(self.schueler_aufraeumen_werte))

        btns = ttk.Frame(win)
        btns.grid(row=len(alle_jahrgaenge) + 2, column=0, columnspan=len(self.ziel_spalten) + 1,
                  sticky="e", padx=8, pady=8)
        ttk.Button(btns, text="Abbrechen", command=abbrechen).pack(side="right", padx=6)
        ttk.Button(btns, text="Speichern & Schließen", command=speichern_schliessen).pack(side="right", padx=6)
        ttk.Button(btns, text="Schüler.csv erstellen (extern)",
                   command=lambda: erstellen([6], "StudentExternal_clean.csv")).pack(side="right", padx=(12, 6))
        ttk.Button(btns, text="Schüler.csv erstellen (aktiv)",
                   command=lambda: erstellen([2], "Student_clean.csv")).pack(side="right")
        win.protocol("WM_DELETE_WINDOW", abbrechen)
        win.wait_window()

        return ergebnis["text"]

    def writeLuLCSV(self):
        ergText = ""
        countNoTeams = 0
        countNichtKlassifiziert = 0
        nicht_klassifiziert_beispiele = set()
        # Voraussetzungen prüfen (ReferenzID vorhanden, TeamsBez in den Lerngruppen)
        if not all("referenzId" in lehrer for lehrer in getattr(self,"lehrer",{})):
            return "Keine Lehrer vorhanden oder nicht alle haben eine referenzId\n"
        if not all("teamBez" in lerngruppe for lerngruppe in getattr(self,"lerngruppen",{})):
            return "Nicht alle Lerngruppen haben eine Teams-Bezeichnung (key: teamBez)\n"
        self.normalisiere_jahrgangsteams()
        with open("Teacher.csv", mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile, delimiter=";")
            # Neues MNSpro-Cloud-Format (siehe README.md, Abschnitt "CSV-Import-Format für MNSpro
            # Cloud"): statt einer Gruppen-Spalte je eine Spalte pro Zielkategorie (self.ziel_spalten)
            writer.writerow(["ReferenzId", "Vorname", "Nachname", "Klassen"] + list(self.ziel_spalten.values()))  # Kopfzeile

            count = 0
            countBesitzer = 0
            countNichtExportiert = 0
            besitzer_je_team = Counter()  # Team-Bezeichnung -> Anzahl mit "^" markierter Lehrkräfte (100er-Grenze, siehe MNSpro-Doku)
            lookup_lg = self.lookupDict.get("lerngruppen",{})
            lookup_klassen = self.lookupDict.get("klassen",{})
            jahrgangs_eintrag_lehrer = self.jahrgangsteams.get("Lehrer", {})

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

                # Team-Listen je Zielkategorie, mit den Jahrgangsteams "Lehrer" vorbelegt
                teams_je_ziel = {ziel: list(jahrgangs_eintrag_lehrer.get(ziel, [])) for ziel in self.ziel_spalten}

                if ids_lerngruppen:
                    for lg_id in ids_lerngruppen:
                        lg = lookup_lg.get(lg_id,{})
                        if not lg:
                            ergText+=f"Lerngruppe mit {lg_id} nicht gefunden\n"
                            continue
                        bezeichnung = lg.get("teamBez")
                        if (bezeichnung not in self.noTeams):
                            ziel = self.get_ziel_fuer_lerngruppe(lg)
                            if ziel is None:
                                countNichtKlassifiziert += 1
                                nicht_klassifiziert_beispiele.add(bezeichnung)
                                continue

                            if (self.replaceSpecialChars):
                                bezeichnung = replace_chars(bezeichnung, my_char_map)

                            # Besitzer-Markierung ("^"): Lehrkraft ist laut idsLehrer Kursleiter
                            # dieser Lerngruppe - analog zur Klassenleitung oben. Über die
                            # Einstellung "Besitzer markieren" (Datei > Einstellungen) abschaltbar.
                            if self.besitzer_markieren and l.get("id") in lg.get("idsLehrer", []):
                                besitzer_je_team[bezeichnung] += 1
                                bezeichnung = "^" + bezeichnung
                                countBesitzer += 1

                            teams_je_ziel.setdefault(ziel, []).append(bezeichnung)
                        else:
                            countNoTeams += 1
                else:
                    ergText+=f"⚠️  {nachname}, {vorname} hat keine Lerngruppe\n"

                zielspalten_werte = ["|".join(teams_je_ziel.get(ziel, [])) for ziel in self.ziel_spalten]
                count += 1
                if (self.replaceSpecialChars):
                    nachname = replace_chars(nachname, my_char_map)
                    vorname = replace_chars(vorname, my_char_map)
                if (self.lehrer_ohne_kurs_exportieren or ids_lerngruppen):  
                    writer.writerow([referenzId, vorname, nachname, klassen] + zielspalten_werte)
                else:
                    countNichtExportiert += 1

        if countNoTeams > 0: ergText+=(f"ℹ️ Es wurden {countNoTeams} Verknüpfungen wegen nicht zu erstellender Teams verhindert\n")
        if countNichtKlassifiziert > 0:
            beispiele = ", ".join(sorted(nicht_klassifiziert_beispiele)[:10])
            ergText += (f"⚠️ {countNichtKlassifiziert} Verknüpfungen wegen nicht klassifizierter Lerngruppen "
                        f"übersprungen (z.B. {beispiele}) - siehe ZuordnungUebersicht/KursartZuordnung\n")
        if countNichtExportiert > 0:
            ergText += f"ℹ {countNichtExportiert} Lehrpersonen wurden wegen fehlender Kurse nicht exportiert"
        if self.besitzer_markieren:
            ergText += f"ℹ️ {countBesitzer} Lehrkraft-Lerngruppen-Zuordnungen wurden als Besitzer (\"^\") markiert.\n"
            # MNSpro-Doku: pro Kurs/Gruppe maximal 100 Besitzer, überzählige werden automatisch zu Mitgliedern
            zu_viele_besitzer = {name: anz for name, anz in besitzer_je_team.items() if anz > 100}
            if zu_viele_besitzer:
                ergText += f"⚠️ {len(zu_viele_besitzer)} Team(s) haben mehr als 100 als Besitzer markierte Lehrkräfte (MNSpro-Grenze, überzählige werden automatisch zu Mitgliedern):\n"
                for name, anz in sorted(zu_viele_besitzer.items()):
                    ergText += f"  {name}: {anz} Besitzer\n"
        ergText+=(f"✅ CSV-Datei 'Teacher.csv' wurde mit {count} Einträgen erstellt.\n")
        self.exportedFlags["lehrer_csv"] = True
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
                print(f"ACHTUNG: {objid} erhält keine Referenz-ID")
                count_id+=1

        print(f"{len(result['mapping'])} Referenz-IDs zugewiesen.")
        return f"{count_ref} Referenz-IDs zugewisen - {count_id} mal die {idBez} als Referenz\n"

    def normalisiere_jahrgangsteams(self) -> str:
        """Migriert self.jahrgangsteams vom alten Format ({jahrgang: [Namen]}) auf das neue
        Format ({jahrgang: {"arbeitsgruppe": [...], "kurs": [...], "gruppe": [...]}}, siehe
        self.ziel_spalten). "*" (Platzhalter für bereits vorhandene Arbeitsgruppen laut
        MNSpro-Doku) landet dabei in "arbeitsgruppe", alle anderen Einträge (übliche Team-Namen
        wie "Abi28") in "kurs". Idempotent - kann gefahrlos mehrfach aufgerufen werden, z.B. nach
        jedem Laden einer alten status.json. Gibt einen Hinweistext zurück, wenn tatsächlich
        migriert wurde, sonst "" (Schritt 6, siehe TODO.md)."""
        migriert = []
        for jahrgang, wert in list(self.jahrgangsteams.items()):
            if isinstance(wert, list):
                self.jahrgangsteams[jahrgang] = {
                    "arbeitsgruppe": [x for x in wert if x == "*"],
                    "kurs": [x for x in wert if x != "*"],
                    "gruppe": [],
                }
                migriert.append(jahrgang)
        if migriert:
            return f"ℹ️ Jahrgangsteams für {', '.join(sorted(migriert))} auf das neue Format (Arbeitsgruppe/Kurs/Gruppe) migriert.\n"
        return ""

    def edit_jahrgangsteams(self, master):
        """Dialog zur Pflege von self.jahrgangsteams: pro Jahrgang (und dem Sonderfall "Lehrer",
        der allen Lehrkräften zugeordnet wird) werden zusätzliche Team-Namen für jede
        Zielkategorie (Arbeitsgruppe/Cloud#Kurs/Cloud#Gruppe, siehe self.ziel_spalten) gepflegt -
        z.B. für die EF ein Cloud#Kurs "Abi28". Migriert dabei automatisch noch nicht umgestellte,
        alte flache Listen (Schritt 6, siehe TODO.md)."""
        # sicherstellen, dass das Attribut existiert und im neuen Format vorliegt
        if not hasattr(self, "jahrgangsteams") or self.jahrgangsteams is None:
            self.jahrgangsteams = {}
        self.normalisiere_jahrgangsteams()

        win = tk.Toplevel(master)
        win.title("Jahrgangsteams bearbeiten")
        win.transient(master)
        win.grab_set()
        win.columnconfigure(1, weight=1)
        # größere Startgröße
        win.geometry("440x460")

        # Widgets
        ttk.Label(win, text="Jahrgang (z. B. 09, EF):").grid(row=0, column=0, sticky="w", padx=8, pady=(10,4))
        e_key = ttk.Entry(win, width=10)
        e_key.grid(row=0, column=1, sticky="w", padx=8, pady=(10,4))

        # Ein Eingabefeld je Zielkategorie (dynamisch aus self.ziel_spalten, damit sich der Dialog
        # automatisch anpasst, falls sich die Zielkategorien künftig ändern sollten)
        e_kategorien = {}  # Ziel-Schlüssel -> Entry-Widget
        row = 1
        for ziel, spalte in self.ziel_spalten.items():
            ttk.Label(win, text=f"{spalte} (kommagetrennt):").grid(row=row, column=0, sticky="nw", padx=8, pady=4)
            e = ttk.Entry(win)
            e.grid(row=row, column=1, sticky="ew", padx=8, pady=4)
            e_kategorien[ziel] = e
            row += 1

        # Liste vorhandener Jahrgänge
        ttk.Label(win, text="Vorhandene Jahrgänge:").grid(row=row, column=0, sticky="nw", padx=8, pady=4)
        lb = tk.Listbox(win, height=8, exportselection=False)
        lb.grid(row=row, column=1, sticky="nsew", padx=8, pady=4)
        win.rowconfigure(row, weight=1)
        row += 1

        # Buttons
        btns = ttk.Frame(win)
        btns.grid(row=row, column=0, columnspan=2, sticky="e", padx=8, pady=8)
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

        def zusammenfassung(key: str) -> str:
            eintrag = self.jahrgangsteams.get(key, {})
            teile = [f"{ziel}: {', '.join(eintrag.get(ziel, []))}" for ziel in self.ziel_spalten if eintrag.get(ziel)]
            return key + (f"  ({'; '.join(teile)})" if teile else "")

        def refresh_listbox(select_key: str | None = None):
            lb.delete(0, tk.END)
            for k in sorted(self.jahrgangsteams.keys()):
                lb.insert(tk.END, zusammenfassung(k))
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
            eintrag = self.jahrgangsteams.get(key, {})
            for ziel, e in e_kategorien.items():
                e.delete(0, tk.END)
                e.insert(0, ", ".join(eintrag.get(ziel, [])))

        def add_or_update():
            key = e_key.get().strip()
            if not key:
                messagebox.showwarning("Hinweis", "Bitte Jahrgang eingeben.", parent=win)
                return
            self.jahrgangsteams[key] = {ziel: normalize_values(e.get()) for ziel, e in e_kategorien.items()}
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
                for e in e_kategorien.values():
                    e.delete(0, tk.END)
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

    def _teambez_beispiele_je_kursart(self, kuerzel: str, max_anzahl: int = 25) -> list:
        """Team-Bezeichnungen (ersatzweise Bezeichnung, falls teamBez noch fehlt) aller
        Lerngruppen mit diesem kursartKuerzel (bzw. KEIN_KURSARTKUERZEL für Lerngruppen ohne
        kursartKuerzel) - als Grundlage für den Hover-Tooltip im Kursart-Zuordnungs-Dialog, damit
        z.B. klar wird, wofür ein Kürzel wie "FOGT" steht."""
        werte = sorted({
            lg.get("teamBez") or lg.get("bezeichnung")
            for lg in getattr(self, "lerngruppen", [])
            if (lg.get("kursartKuerzel") or KEIN_KURSARTKUERZEL) == kuerzel and (lg.get("teamBez") or lg.get("bezeichnung"))
        })
        if len(werte) > max_anzahl:
            return werte[:max_anzahl] + [f"… und {len(werte) - max_anzahl} weitere"]
        return werte

    def edit_kursart_zuordnung(self, master):
        """Dialog zur Pflege von self.kursart_zuordnung: legt für jedes in den Lerngruppen
        vorkommende kursartKuerzel die Zielkategorie fest - also die Unterscheidung, ob Lerngruppen
        mit diesem Kürzel beim Export als Arbeitsgruppe, Cloud#Kurs oder Cloud#Gruppe behandelt
        werden (siehe self.ziel_spalten und README.md, Abschnitt "CSV-Import-Format für MNSpro
        Cloud"). Lerngruppen ohne kursartKuerzel (None/leer/fehlend - typischerweise normale
        Fachkurse) laufen dabei unter dem Pseudo-Kürzel KEIN_KURSARTKUERZEL mit, damit sie nicht
        unsichtbar durchfallen. Als Startvorschlag dient KURSART_ZUORDNUNG_VORSCHLAG, sofern für
        ein Kürzel noch keine Zuordnung gespeichert ist - übernommen wird das aber erst mit
        "Speichern & Schließen"."""
        NICHT_KLASSIFIZIERT = "– nicht klassifiziert –"

        lerngruppen = getattr(self, "lerngruppen", [])
        if not lerngruppen:
            messagebox.showinfo("Kursart-Zuordnung",
                "Keine Lerngruppen vorhanden - bitte zuerst Lerngruppen holen.", parent=master)
            return

        alle_kuerzel = sorted({lg.get("kursartKuerzel") or KEIN_KURSARTKUERZEL for lg in lerngruppen})
        anzahl = Counter(lg.get("kursartKuerzel") or KEIN_KURSARTKUERZEL for lg in lerngruppen)

        win = tk.Toplevel(master)
        win.title("Kursart-Zuordnung (Arbeitsgruppe / Kurs / Gruppe)")
        win.transient(master)
        win.grab_set()
        win.columnconfigure(1, weight=1)

        ttk.Label(win, text="kursartKuerzel").grid(row=0, column=0, sticky="w", padx=8, pady=(10, 4))
        ttk.Label(win, text="Zielkategorie").grid(row=0, column=1, sticky="w", padx=8, pady=(10, 4))

        ziel_werte = list(self.ziel_spalten.keys()) + [NICHT_KLASSIFIZIERT]
        comboboxes = {}
        for i, kuerzel in enumerate(alle_kuerzel, start=1):
            label = ttk.Label(win, text=f"{kuerzel} ({anzahl[kuerzel]} Lerngruppen)")
            label.grid(row=i, column=0, sticky="w", padx=8, pady=2)
            beispiele = self._teambez_beispiele_je_kursart(kuerzel)
            if beispiele:
                ToolTip(label, "\n".join(beispiele))
            cb = ttk.Combobox(win, values=ziel_werte, state="readonly", width=20)
            vorbelegung = self.kursart_zuordnung.get(kuerzel) or KURSART_ZUORDNUNG_VORSCHLAG.get(kuerzel, NICHT_KLASSIFIZIERT)
            cb.set(vorbelegung)
            cb.grid(row=i, column=1, sticky="ew", padx=8, pady=2)
            comboboxes[kuerzel] = cb

        btns = ttk.Frame(win)
        btns.grid(row=len(alle_kuerzel) + 1, column=0, columnspan=2, sticky="e", padx=8, pady=8)

        def on_save_close():
            for kuerzel, cb in comboboxes.items():
                wert = cb.get()
                if wert and wert != NICHT_KLASSIFIZIERT:
                    self.kursart_zuordnung[kuerzel] = wert
                else:
                    self.kursart_zuordnung.pop(kuerzel, None)
            win.destroy()

        ttk.Button(btns, text="Abbrechen", command=win.destroy).pack(side="right", padx=6)
        ttk.Button(btns, text="Speichern & Schließen", command=on_save_close).pack(side="right")
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        win.wait_window()

    def edit_bezeichnung_muster(self, master):
        """Dialog zur Pflege von self.bezeichnung_muster: geordnete Liste von Regex-Mustern, die
        auf die Team-Bezeichnung (teamBez, ersatzweise bezeichnung, falls TeamBez noch nicht
        erstellt wurde) einer Lerngruppe geprüft werden und - VOR der kursartKuerzel-Regel,
        siehe get_ziel_fuer_lerngruppe() - über die Zielkategorie (Arbeitsgruppe/Cloud#Kurs/
        Cloud#Gruppe, self.ziel_spalten) entscheiden. Reihenfolge in der Liste = Priorität, das
        erste passende Muster gewinnt. Änderungen wirken sofort auf self.bezeichnung_muster
        (kein separates "Speichern" nötig, analog zu edit_jahrgangsteams)."""
        if not hasattr(self, "bezeichnung_muster") or self.bezeichnung_muster is None:
            self.bezeichnung_muster = []

        alle_bezeichnungen = [lg.get("teamBez") or lg.get("bezeichnung") or ""
                               for lg in getattr(self, "lerngruppen", [])]

        win = tk.Toplevel(master)
        win.title("Bezeichnungs-Muster bearbeiten (Regex)")
        win.transient(master)
        win.grab_set()
        win.geometry("560x460")
        win.columnconfigure(1, weight=1)

        ttk.Label(win, text="Reihenfolge = Priorität (von oben nach unten, erstes Match gewinnt):") \
            .grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(10, 2))

        lb = tk.Listbox(win, height=8, exportselection=False)
        lb.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=8, pady=4)
        win.rowconfigure(1, weight=1)

        ttk.Label(win, text="Regex-Muster (gegen Team-Bezeichnung):").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        e_pattern = ttk.Entry(win)
        e_pattern.grid(row=2, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(win, text="Zielkategorie:").grid(row=3, column=0, sticky="w", padx=8, pady=4)
        cb_ziel = ttk.Combobox(win, values=list(self.ziel_spalten.keys()), state="readonly")
        cb_ziel.grid(row=3, column=1, sticky="ew", padx=8, pady=4)

        lbl_treffer = ttk.Label(win, text="", foreground="#555555")
        lbl_treffer.grid(row=4, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 4))

        def aktualisiere_treffer(*_args):
            """Live-Vorschau: wie viele/welche aktuellen Lerngruppen würde dieses Muster treffen -
            zum direkten Ausprobieren im Programm, ohne extra Testskript."""
            pattern = e_pattern.get()
            if not pattern:
                lbl_treffer.config(text="")
                return
            try:
                treffer = sorted({b for b in alle_bezeichnungen if re.search(pattern, b)})
            except re.error as ex:
                lbl_treffer.config(text=f"⚠️ Ungültiges Muster: {ex}")
                return
            text = f"{len(treffer)} Treffer in aktuellen Lerngruppen"
            if treffer:
                text += f" (z.B. {', '.join(treffer[:5])})"
            lbl_treffer.config(text=text)

        e_pattern.bind("<KeyRelease>", aktualisiere_treffer)

        # Trefferanzahl je Listeneintrag (Index -> Liste der passenden Bezeichnungen), gefüllt
        # per "Testen"-Button; None = ungültiges Muster. Wird bei jeder Listenänderung verworfen,
        # damit keine veralteten Zahlen angezeigt werden.
        treffer_je_index = {}

        def refresh_listbox(select_index=None):
            treffer_je_index.clear()
            lb.delete(0, tk.END)
            for regel in self.bezeichnung_muster:
                lb.insert(tk.END, f'{regel.get("pattern", "")!r} → {regel.get("ziel", "")}')
            if select_index is not None and 0 <= select_index < lb.size():
                lb.selection_clear(0, tk.END)
                lb.selection_set(select_index)
                lb.see(select_index)

        def teste_alle_muster():
            """Berechnet für jedes Muster in der Liste die Trefferanzahl gegen die aktuellen
            Lerngruppen-Bezeichnungen und hängt sie in Klammern an den jeweiligen Eintrag an."""
            sel = lb.curselection()
            treffer_je_index.clear()
            for i, regel in enumerate(self.bezeichnung_muster):
                pattern = regel.get("pattern", "")
                basis = f'{pattern!r} → {regel.get("ziel", "")}'
                try:
                    treffer = sorted({b for b in alle_bezeichnungen if re.search(pattern, b)})
                except re.error as ex:
                    treffer_je_index[i] = None
                    lb.delete(i); lb.insert(i, f"{basis}  (⚠️ ungültig: {ex})")
                    continue
                treffer_je_index[i] = treffer
                lb.delete(i); lb.insert(i, f"{basis}  ({len(treffer)} Treffer)")
            if sel:
                lb.selection_set(sel[0])

        def load_from_selection(_evt=None):
            sel = lb.curselection()
            if not sel:
                return
            regel = self.bezeichnung_muster[sel[0]]
            e_pattern.delete(0, tk.END); e_pattern.insert(0, regel.get("pattern", ""))
            cb_ziel.set(regel.get("ziel", ""))
            aktualisiere_treffer()

        def gueltige_eingabe():
            pattern = e_pattern.get().strip()
            ziel = cb_ziel.get()
            if not pattern:
                messagebox.showwarning("Hinweis", "Bitte ein Muster eingeben.", parent=win)
                return None
            if not ziel:
                messagebox.showwarning("Hinweis", "Bitte eine Zielkategorie wählen.", parent=win)
                return None
            try:
                re.compile(pattern)
            except re.error as ex:
                messagebox.showwarning("Ungültiges Muster", str(ex), parent=win)
                return None
            return pattern, ziel

        def hinzufuegen():
            eingabe = gueltige_eingabe()
            if not eingabe:
                return
            pattern, ziel = eingabe
            self.bezeichnung_muster.append({"pattern": pattern, "ziel": ziel})
            refresh_listbox(select_index=len(self.bezeichnung_muster) - 1)

        def aktualisieren():
            sel = lb.curselection()
            if not sel:
                messagebox.showinfo("Hinweis", "Bitte zuerst einen Eintrag in der Liste auswählen.", parent=win)
                return
            eingabe = gueltige_eingabe()
            if not eingabe:
                return
            pattern, ziel = eingabe
            self.bezeichnung_muster[sel[0]] = {"pattern": pattern, "ziel": ziel}
            refresh_listbox(select_index=sel[0])

        def loeschen():
            sel = lb.curselection()
            if not sel:
                return
            del self.bezeichnung_muster[sel[0]]
            e_pattern.delete(0, tk.END)
            cb_ziel.set("")
            refresh_listbox()

        def verschieben(delta):
            sel = lb.curselection()
            if not sel:
                return
            i = sel[0]
            j = i + delta
            if 0 <= j < len(self.bezeichnung_muster):
                self.bezeichnung_muster[i], self.bezeichnung_muster[j] = self.bezeichnung_muster[j], self.bezeichnung_muster[i]
                refresh_listbox(select_index=j)

        btns1 = ttk.Frame(win)
        btns1.grid(row=5, column=0, columnspan=2, sticky="ew", padx=8, pady=4)
        ttk.Button(btns1, text="Hinzufügen", command=hinzufuegen).pack(side="left", padx=2)
        ttk.Button(btns1, text="Aktualisieren", command=aktualisieren).pack(side="left", padx=2)
        ttk.Button(btns1, text="Löschen", command=loeschen).pack(side="left", padx=2)
        ttk.Button(btns1, text="▲ nach oben", command=lambda: verschieben(-1)).pack(side="left", padx=2)
        ttk.Button(btns1, text="▼ nach unten", command=lambda: verschieben(1)).pack(side="left", padx=2)
        btn_testen = ttk.Button(btns1, text="Testen", command=teste_alle_muster)
        btn_testen.pack(side="left", padx=(12, 2))
        ToolTip(btn_testen, "Prüft jedes Muster gegen alle aktuellen Lerngruppen-Bezeichnungen\n"
                             "und zeigt die Trefferanzahl in Klammern hinter dem Eintrag an.\n"
                             "Zum Betrachten der einzelnen Treffer mit der Maus über einen\n"
                             "Eintrag fahren.")

        # Dynamisches Tooltip beim Überfahren einer Listbox-Zeile: zeigt die (bis zu 15)
        # passenden Bezeichnungen dieses Musters, sofern schon per "Testen" berechnet.
        hover = {"index": None, "after_id": None, "tip": None}

        def hover_verstecken():
            if hover["after_id"] is not None:
                win.after_cancel(hover["after_id"])
                hover["after_id"] = None
            if hover["tip"] is not None:
                hover["tip"].destroy()
                hover["tip"] = None
            hover["index"] = None

        def hover_anzeigen(index, x_root, y_root):
            treffer = treffer_je_index.get(index)
            if not treffer:
                return
            beispiele = treffer[:15]
            text = f"{len(treffer)} Treffer:\n" + "\n".join(beispiele)
            if len(treffer) > len(beispiele):
                text += "\n…"
            tip = tk.Toplevel(win)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{x_root + 12}+{y_root + 8}")
            tip.attributes("-topmost", True)  # sonst landet es u.U. hinter dem Dialogfenster
            tip.lift()
            tk.Label(tip, text=text, background="lightyellow", relief="solid", borderwidth=1,
                     justify="left").pack()
            hover["tip"] = tip

        def on_listbox_motion(evt):
            index = lb.nearest(evt.y)
            if index < 0 or index >= lb.size() or index not in treffer_je_index:
                hover_verstecken()
                return
            if index != hover["index"]:
                hover_verstecken()
                hover["index"] = index
                hover["after_id"] = win.after(400, lambda: hover_anzeigen(index, evt.x_root, evt.y_root))

        lb.bind("<Motion>", on_listbox_motion)
        lb.bind("<Leave>", lambda evt: hover_verstecken())

        btns2 = ttk.Frame(win)
        btns2.grid(row=6, column=0, columnspan=2, sticky="e", padx=8, pady=8)
        ttk.Button(btns2, text="Schließen", command=win.destroy).pack(side="right")

        lb.bind("<<ListboxSelect>>", load_from_selection)
        win.protocol("WM_DELETE_WINDOW", win.destroy)

        refresh_listbox()
        win.wait_window()

    def edit_teambez_rewrite(self, master):
        """Dialog zur Pflege von self.teambez_rewrite: geordnete Liste von sed-artigen
        Ersetzungs-Regeln (Regex-Suchmuster + Ersetzung, z.B. um "Q1"-Teams in "Abi28"
        umzubenennen), die im Anschluss an addTeamBezZuLerngruppen() sequenziell auf jede
        Team-Bezeichnung angewandt werden (anders als bei self.bezeichnung_muster gewinnt hier
        nicht nur die erste passende Regel - alle Regeln werden der Reihe nach angewandt, jede
        auf das Ergebnis der vorherigen). Reihenfolge in der Liste = Anwendungsreihenfolge.
        Änderungen wirken sofort auf self.teambez_rewrite (kein separates "Speichern" nötig,
        analog zu edit_jahrgangsteams/edit_bezeichnung_muster)."""
        if not hasattr(self, "teambez_rewrite") or self.teambez_rewrite is None:
            self.teambez_rewrite = []

        alle_bezeichnungen = [lg.get("teamBez") or lg.get("bezeichnung") or ""
                               for lg in getattr(self, "lerngruppen", [])]

        win = tk.Toplevel(master)
        win.title("TeamBez-Rewrite bearbeiten (Regex, sed-artig)")
        win.transient(master)
        win.grab_set()
        win.geometry("560x480")
        win.columnconfigure(1, weight=1)

        ttk.Label(win, text="Anwendungsreihenfolge (von oben nach unten, alle Regeln werden angewandt):") \
            .grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(10, 2))

        lb = tk.Listbox(win, height=8, exportselection=False)
        lb.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=8, pady=4)
        win.rowconfigure(1, weight=1)

        ttk.Label(win, text="Suchmuster (Regex):").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        e_pattern = ttk.Entry(win)
        e_pattern.grid(row=2, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(win, text="Ersetzung:").grid(row=3, column=0, sticky="w", padx=8, pady=4)
        e_replace = ttk.Entry(win)
        e_replace.grid(row=3, column=1, sticky="ew", padx=8, pady=4)
        ToolTip(e_replace, "Wie bei re.sub(): \\1, \\2, ... verweisen auf Klammer-Gruppen im\n"
                            "Suchmuster. Beispiel: Suchmuster '^Q1' + Ersetzung 'Abi28' macht aus\n"
                            "'Q1 - Deutsch GK' → 'Abi28 - Deutsch GK'.")

        lbl_treffer = ttk.Label(win, text="", foreground="#555555")
        lbl_treffer.grid(row=4, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 4))

        def aktualisiere_treffer(*_args):
            """Live-Vorschau: wie viele/welche aktuellen Team-Bezeichnungen dieses Muster träfe -
            zum direkten Ausprobieren im Programm, ohne extra Testskript."""
            pattern = e_pattern.get()
            replace = e_replace.get()
            if not pattern:
                lbl_treffer.config(text="")
                return
            try:
                treffer = [b for b in alle_bezeichnungen if re.search(pattern, b)]
                beispiele = sorted({f"{b} → {re.sub(pattern, replace, b)}" for b in treffer})
            except re.error as ex:
                lbl_treffer.config(text=f"⚠️ Ungültiges Muster: {ex}")
                return
            text = f"{len(treffer)} Treffer in aktuellen Team-Bezeichnungen"
            if beispiele:
                text += f" (z.B. {', '.join(beispiele[:3])})"
            lbl_treffer.config(text=text)

        e_pattern.bind("<KeyRelease>", aktualisiere_treffer)
        e_replace.bind("<KeyRelease>", aktualisiere_treffer)

        # Trefferanzahl/-beispiele je Listeneintrag (Index -> Liste "vorher → nachher"), gefüllt
        # per "Testen"-Button; None = ungültiges Muster. Wird bei jeder Listenänderung verworfen,
        # damit keine veralteten Zahlen angezeigt werden.
        treffer_je_index = {}

        def refresh_listbox(select_index=None):
            treffer_je_index.clear()
            lb.delete(0, tk.END)
            for regel in self.teambez_rewrite:
                lb.insert(tk.END, f'{regel.get("pattern", "")!r} → {regel.get("replace", "")!r}')
            if select_index is not None and 0 <= select_index < lb.size():
                lb.selection_clear(0, tk.END)
                lb.selection_set(select_index)
                lb.see(select_index)

        def teste_alle_regeln():
            """Berechnet für jede Regel in der Liste die Trefferanzahl gegen die aktuellen
            Team-Bezeichnungen (jede Regel für sich, unabhängig von den anderen) und hängt sie
            in Klammern an den jeweiligen Eintrag an."""
            sel = lb.curselection()
            treffer_je_index.clear()
            for i, regel in enumerate(self.teambez_rewrite):
                pattern = regel.get("pattern", "")
                replace = regel.get("replace", "")
                basis = f'{pattern!r} → {replace!r}'
                try:
                    treffer = [b for b in alle_bezeichnungen if re.search(pattern, b)]
                    beispiele = sorted({f"{b} → {re.sub(pattern, replace, b)}" for b in treffer})
                except re.error as ex:
                    treffer_je_index[i] = None
                    lb.delete(i); lb.insert(i, f"{basis}  (⚠️ ungültig: {ex})")
                    continue
                treffer_je_index[i] = beispiele
                lb.delete(i); lb.insert(i, f"{basis}  ({len(treffer)} Treffer)")
            if sel:
                lb.selection_set(sel[0])

        def load_from_selection(_evt=None):
            sel = lb.curselection()
            if not sel:
                return
            regel = self.teambez_rewrite[sel[0]]
            e_pattern.delete(0, tk.END); e_pattern.insert(0, regel.get("pattern", ""))
            e_replace.delete(0, tk.END); e_replace.insert(0, regel.get("replace", ""))
            aktualisiere_treffer()

        def gueltige_eingabe():
            pattern = e_pattern.get().strip()
            replace = e_replace.get()
            if not pattern:
                messagebox.showwarning("Hinweis", "Bitte ein Suchmuster eingeben.", parent=win)
                return None
            try:
                re.compile(pattern)
            except re.error as ex:
                messagebox.showwarning("Ungültiges Muster", str(ex), parent=win)
                return None
            return pattern, replace

        def hinzufuegen():
            eingabe = gueltige_eingabe()
            if not eingabe:
                return
            pattern, replace = eingabe
            self.teambez_rewrite.append({"pattern": pattern, "replace": replace})
            refresh_listbox(select_index=len(self.teambez_rewrite) - 1)

        def aktualisieren():
            sel = lb.curselection()
            if not sel:
                messagebox.showinfo("Hinweis", "Bitte zuerst einen Eintrag in der Liste auswählen.", parent=win)
                return
            eingabe = gueltige_eingabe()
            if not eingabe:
                return
            pattern, replace = eingabe
            self.teambez_rewrite[sel[0]] = {"pattern": pattern, "replace": replace}
            refresh_listbox(select_index=sel[0])

        def loeschen():
            sel = lb.curselection()
            if not sel:
                return
            del self.teambez_rewrite[sel[0]]
            e_pattern.delete(0, tk.END)
            e_replace.delete(0, tk.END)
            refresh_listbox()

        def verschieben(delta):
            sel = lb.curselection()
            if not sel:
                return
            i = sel[0]
            j = i + delta
            if 0 <= j < len(self.teambez_rewrite):
                self.teambez_rewrite[i], self.teambez_rewrite[j] = self.teambez_rewrite[j], self.teambez_rewrite[i]
                refresh_listbox(select_index=j)

        btns1 = ttk.Frame(win)
        btns1.grid(row=5, column=0, columnspan=2, sticky="ew", padx=8, pady=4)
        ttk.Button(btns1, text="Hinzufügen", command=hinzufuegen).pack(side="left", padx=2)
        ttk.Button(btns1, text="Aktualisieren", command=aktualisieren).pack(side="left", padx=2)
        ttk.Button(btns1, text="Löschen", command=loeschen).pack(side="left", padx=2)
        ttk.Button(btns1, text="▲ nach oben", command=lambda: verschieben(-1)).pack(side="left", padx=2)
        ttk.Button(btns1, text="▼ nach unten", command=lambda: verschieben(1)).pack(side="left", padx=2)
        btn_testen = ttk.Button(btns1, text="Testen", command=teste_alle_regeln)
        btn_testen.pack(side="left", padx=(12, 2))
        ToolTip(btn_testen, "Prüft jede Regel für sich gegen alle aktuellen Team-Bezeichnungen\n"
                             "und zeigt die Trefferanzahl in Klammern hinter dem Eintrag an.\n"
                             "Zum Betrachten der einzelnen Vorher/Nachher-Beispiele mit der Maus\n"
                             "über einen Eintrag fahren.")

        # Dynamisches Tooltip beim Überfahren einer Listbox-Zeile: zeigt (bis zu 15) "vorher →
        # nachher"-Beispiele dieser Regel, sofern schon per "Testen" berechnet.
        hover = {"index": None, "after_id": None, "tip": None}

        def hover_verstecken():
            if hover["after_id"] is not None:
                win.after_cancel(hover["after_id"])
                hover["after_id"] = None
            if hover["tip"] is not None:
                hover["tip"].destroy()
                hover["tip"] = None
            hover["index"] = None

        def hover_anzeigen(index, x_root, y_root):
            beispiele = treffer_je_index.get(index)
            if not beispiele:
                return
            gezeigt = beispiele[:15]
            text = f"{len(beispiele)} Treffer:\n" + "\n".join(gezeigt)
            if len(beispiele) > len(gezeigt):
                text += "\n…"
            tip = tk.Toplevel(win)
            tip.wm_overrideredirect(True)
            tip.wm_geometry(f"+{x_root + 12}+{y_root + 8}")
            tip.attributes("-topmost", True)  # sonst landet es u.U. hinter dem Dialogfenster
            tip.lift()
            tk.Label(tip, text=text, background="lightyellow", relief="solid", borderwidth=1,
                     justify="left").pack()
            hover["tip"] = tip

        def on_listbox_motion(evt):
            index = lb.nearest(evt.y)
            if index < 0 or index >= lb.size() or index not in treffer_je_index:
                hover_verstecken()
                return
            if index != hover["index"]:
                hover_verstecken()
                hover["index"] = index
                hover["after_id"] = win.after(400, lambda: hover_anzeigen(index, evt.x_root, evt.y_root))

        lb.bind("<Motion>", on_listbox_motion)
        lb.bind("<Leave>", lambda evt: hover_verstecken())

        btns2 = ttk.Frame(win)
        btns2.grid(row=6, column=0, columnspan=2, sticky="e", padx=8, pady=8)
        ttk.Button(btns2, text="Schließen", command=win.destroy).pack(side="right")

        lb.bind("<<ListboxSelect>>", load_from_selection)
        win.protocol("WM_DELETE_WINDOW", win.destroy)

        refresh_listbox()
        win.wait_window()

def replace_chars(text: str, char_map: dict[str, str]) -> str:
    for old, new in char_map.items():
        text = text.replace(old, new)
    return text

def collect_values(objs, key, unique=True):
    """Gibt alle vorkommenden Werte zu einem Key aus einer Liste von Dicts zurück."""
    if unique:
        return list({obj.get(key) for obj in objs if key in obj})
    else: 
        return [obj.get(key) for obj in objs if key in obj]


if __name__=="__main__":
    g = Generator()
    

