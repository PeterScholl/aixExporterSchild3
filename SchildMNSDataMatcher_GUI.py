import json
import random
import os
import tkinter as tk
import generator as logic
import webbrowser

from tkinter import ttk, messagebox, filedialog



class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        widget.bind("<Enter>", self.show_tooltip)
        widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event):
        # Tooltip Fenster erstellen
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)  # Kein Fensterrahmen
        self.tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
        label = tk.Label(self.tooltip, text=self.text, background="lightgrey", relief="solid", borderwidth=1)
        label.pack()

    def hide_tooltip(self, event):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None
            
class ReportApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # Generator-Object
        self.generator = logic.Generator()
        
        # Hauptfenster konfigurieren
        self.title("Schild-MNS-Abgleich")
        self.geometry("800x600")
        
        # Menüleiste
        self.create_menu()
        
        
        # Textbox für den Report
        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Textbox
        self.report_text = tk.Text(frame, height=10, width=50, wrap="none")
        self.report_text.pack(side="left", fill="both", expand=True)

        # Scrollbar
        scrollbar = tk.Scrollbar(frame, orient="vertical", command=self.report_text.yview)
        scrollbar.pack(side="right", fill="y")

        # Verknüpfen
        self.report_text.config(yscrollcommand=scrollbar.set)

        
        # Frame für die Buttons
        button_frame = tk.Frame(self)
        button_frame.pack(pady=10)

        # Die Buttons im Grid
        button_texts = [
            "Verbindungseinstellung", "Abschnitts-ID holen", "Lerngruppen holen", "ErgänzeLehrerAusDB", 
            "generateLookupDicts", "idsSchuelerZuLerngruppen", "TeamBezErstellen", "Referenz-IDs aus File", 
            "ReferenzIDs aus SuS-Ids", "LehrerReferenzen aus File","L-ReferenzIDs aus kuerzel", "Jahrgangsteams",
            "idsLerngruppenZuLehrern","idsKlassenleitungenZuLehrern","Statistik anzeigen","TempHilfsfunktion",
            "schueler_csv", "sus_extern_csv", "lehrer_csv", "ClearScreen",
            "ListeTeamBez","b22","b23","b24"
        ]
        
        # Buttons in einem <x> times 4 Grid
        for i, text in enumerate(button_texts):
            button = tk.Button(button_frame, text=text, command=lambda t=text: self.button_clicked(t))
            button.grid(row=i//4, column=i%4, padx=5, pady=5)  # Grid positionierung
            
        # Einstellungen speichern
        self.sonderzeichenErsetzen = tk.BooleanVar(value=True) #Ersetzt Sonderzeichen aus der Charmap

        # Status.json prüfen ggf. anlegen
        if not os.path.exists("status.json"):
            self.save_state()

    def button_clicked(self, text):
        print(f"Button '{text}' clicked")
        match text:
            case "Verbindungseinstellung":
                self.generator.configValues(self)
                self.report_text.insert(tk.END, "Konfiguration durchgeführt - Menu speichern?\n")
            case "Abschnitts-ID holen":
                if (self.generator.initAbschnittsID()):
                    self.report_text.insert(tk.END,f"Abschnitts-ID: {self.generator.svws_abschnitts_id}\n")
                else:
                    self.report_text.insert(tk.END,f"⚠️Nicht erfolgreich - evtl. Authentifizierung fehlerhaft (siehe Console)\n")
            case "Lerngruppen holen":
                self.generator.lerngruppenHolen()
                self.report_text.insert(tk.END,f"Lerngruppen geholt\n")
            case "ErgänzeLehrerAusDB":
                self.report_text.insert(tk.END,self.generator.ergaenzeLehrer())
            case "Statistik anzeigen":
                self.show_statistik()
            case "generateLookupDicts":
                self.generator.generateLookups()
                ergtext = "Erstellte Lookup-Dictionaries:\n"
                for key, value in self.generator.lookupDict.items():
                    ergtext+=f"Einträge für den key {key}: {len(value)}\n"
                self.report_text.insert(tk.END,ergtext)
            case "idsKlassenleitungenZuLehrern":
                anz = self.generator.addKlassenleitungsIdsZuLuL()
                self.report_text.insert(tk.END,f"Es wurden {anz} Verknüpfungen erstellt\n")
            case "idsLerngruppenZuLehrern":
                anz = self.generator.addLerngruppenIdsZuLuL()
                self.report_text.insert(tk.END,f"Es wurden {anz} Verknüpfungen erstellt\n")
            case "idsSchuelerZuLerngruppen":
                anz = self.generator.addSuSIdsZuLerngruppen()
                self.report_text.insert(tk.END,f"Es wurden {anz} Verknüpfungen erstellt\n")
            case "TeamBezErstellen":
                self.report_text.insert(tk.END, self.generator.addTeamBezZuLerngruppen())
            case "TempHilfsfunktion":
                self.tempHIlfsfunktion()
            case "ReferenzIDs aus SuS-Ids":
                count = 0
                for lehrer in getattr(self.generator, "schueler", {}):
                    if "id" in lehrer:
                        count+=1
                        lehrer["referenzId"]=lehrer.get("id")
                self.report_text.insert(tk.END,f'Bei {count} von {len(getattr(self.generator, "schueler", {}))} Schülern die ReferenzId-gesetzt\n')
            case "Referenz-IDs aus File":
                self.report_text.insert(tk.END,self.generator.import_referenz_ids(self))     
            case "LehrerReferenzen aus File":
                self.report_text.insert(tk.END,self.generator.import_referenz_ids(self,art="lehrer",idBez="kuerzel"))     
            case "L-ReferenzIDs aus kuerzel":
                count = 0
                for lehrer in getattr(self.generator, "lehrer", {}):
                    if "kuerzel" in lehrer:
                        count+=1
                        lehrer["referenzId"]=lehrer.get("kuerzel")
                self.report_text.insert(tk.END,f'Bei {count} von {len(getattr(self.generator, "lehrer", {}))} Lehrern die ReferenzId-gesetzt\n')
            case "schueler_csv":
                self.report_text.insert(tk.END, self.generator.writeSuSCSV())
            case "sus_extern_csv":
                self.report_text.insert(tk.END, "Externe Schüler mit Status 6:\n")
                self.report_text.insert(tk.END, self.generator.writeSuSCSV(statusList=[6], filename="StudentExternal.csv"))
            case "lehrer_csv":
                self.report_text.insert(tk.END, self.generator.writeLuLCSV())
            case "Jahrgangsteams":
                self.generator.edit_jahrgangsteams(self)
            case "ClearScreen":
                self.report_text.delete(1.0, tk.END)
            case "ListeTeamBez":
                teambez = sorted(collect_values(getattr(self.generator,"lerngruppen",[]),"teamBez"))
                ergtext = f"Es gibt {len(teambez)} Lerngruppen in alphabetischer Sortierung:\n"
                ergtext += "\n".join(teambez)
                ergtext += "\n"
                self.report_text.insert(tk.END,ergtext)
            case _:
                print("Ubekannter Button")


    def save_object_to_json(self, obj, filename):
        """Speichert ein Objekt in eine JSON-Datei."""
        with open(filename, 'w') as json_file:
            json.dump(obj.__dict__, json_file, indent=4)

    def save_state(self):
        print(f"Speichere Generator: {self.generator}")

        # lookupDict sichern und entfernen
        tmp = getattr(self.generator, "lookupDict", None)
        if hasattr(self.generator, "lookupDict"):
            delattr(self.generator, "lookupDict")

        # Speichern
        self.save_object_to_json(self.generator, "status.json")
        self.report_text.insert(tk.END, "Konfiguration gespeichert!\n")

        # lookupDict zurücksetzen
        if tmp is not None:
            self.generator.lookupDict = tmp


    def load_state(self):
        self.generator = self.load_object_from_json(logic.Generator, "status.json")
        print(f"username {self.generator.username}")
        logic.sv.setConfig(self.generator.base_url,(self.generator.username, self.generator.password))
        self.report_text.insert(tk.END,"Konfiguration geladen!\nGeneriere Lookup Dictionaries ...")
        self.generator.generateLookups()
        self.report_text.insert(tk.END," DONE\n")
        
    def load_object_from_json(self, cls, filename):
        """Lädt ein Objekt einer bestimmten Klasse von einer JSON-Datei."""
        try:
            with open(filename, 'r') as json_file:
                data = json.load(json_file)
            obj = cls()  # Erstelle ein leeres Objekt der angegebenen Klasse
            obj.__dict__.update(data)  # Fülle das Objekt mit den Daten aus der JSON-Datei
            return obj
        except Exception as ex:
            print(f"File {filename} konnte nicht geladen werden: {ex}")
        return None
        
        
    def adjust_size(self, new_window):
        # Let Tkinter calculate the required size
        new_window.update_idletasks()
        new_window.geometry("")  # Reset geometry to fit the content

        # Get actual window position
        window_x = new_window.winfo_x()
        window_y = new_window.winfo_y()

        # Resize window to fit content, but keep its position
        #new_size = f"{new_window.winfo_width()}x{new_window.winfo_height()}+{window_x}+{window_y}"
        new_size = f"+{window_x}+{window_y}"
        #print(f"new size: {new_size}")
        new_window.geometry(new_size)


    def create_menu(self):
        # Menüleiste erstellen
        menubar = tk.Menu(self)
        
        # Menü "Datei"
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Einstellungen", command=self.open_settings_window)
        file_menu.add_command(label="Info/Hilfe", command=self.open_help_window)
        file_menu.add_separator()
        file_menu.add_command(label="Save state", command=self.save_state)
        file_menu.add_command(label="Load state", command=self.load_state)
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self.quit)
        menubar.add_cascade(label="Datei", menu=file_menu)
        
        # Menüleiste konfigurieren
        self.config(menu=menubar)
    
    def create_file_choosing_boxes(self):
        # Frame für Status-Labels
        status_frame = tk.Frame(self)
        status_frame.pack(pady=10)
        
        # Info Label links vom Dateilabel
        self.schild_info_label = tk.Label(status_frame, text="Schild:", relief=tk.SUNKEN, width=20)
        self.schild_info_label.grid(row=0, column=0, padx=5, pady=5)  # In Spalte 0 positioniert
        # Dateianzeige Label mit Klick-Funktion
        initial_file = os.path.dirname(self.selected_schild_file) if self.selected_schild_file and os.path.exists(self.selected_schild_file) else os.getcwd()
        self.schild_file_label = tk.Label(status_frame, text=initial_file, relief=tk.SUNKEN, width=100, fg="blue", cursor="hand2")
        self.schild_file_label.grid(row=0, column=1, columnspan=2, padx=5, pady=5)
        self.schild_file_label.bind("<Button-1>", lambda x : self.schild_file_label.config(text = self.select_schild_file(x)))  # Klickbare Funktion

        # Info Label links vom Dateilabel
        self.jamf_info_label = tk.Label(status_frame, text="Jamf:", relief=tk.SUNKEN, width=20)
        self.jamf_info_label.grid(row=1, column=0, padx=5, pady=5)  # In Spalte 0 positioniert
        # Dateianzeige Label mit Klick-Funktion
        initial_file = os.path.dirname(self.selected_jamf_file) if self.selected_jamf_file and os.path.exists(self.selected_jamf_file) else os.getcwd()
        self.jamf_file_label = tk.Label(status_frame, text=initial_file, relief=tk.SUNKEN, width=100, fg="blue", cursor="hand2")
        self.jamf_file_label.grid(row=1, column=1, columnspan=2, padx=5, pady=5)
        self.jamf_file_label.bind("<Button-1>", lambda x : self.jamf_file_label.config(text = self.select_jamf_file(x)))  # Klickbare Funktion
    
    def open_help_window(self):
        # Fenster für die Hilfe
        help_window = tk.Toplevel(self)
        help_window.title("Hilfe")
        #help_window.geometry("300x150")
        
        # Info-Label
        info_label = tk.Label(help_window, text="Anleitung\n\n"+
            "Aktuell gibt es nur das README.md - kann auch auf github gelesen werden ...")
        info_label.pack(pady=10)
        
        # Link-Label
        link = tk.Label(help_window, text="Github-Projekt-Website", fg="blue", cursor="hand2")
        link.pack()

        # Funktion zum Öffnen des Links
        link.bind("<Button-1>", lambda e: webbrowser.open_new("https://github.com/PeterScholl/aixExporterSchild3"))

        # Schließen-Button
        close_button = tk.Button(help_window, text="Schließen", command=help_window.destroy)
        close_button.pack(pady=10)
        help_window.after(80, lambda: self.adjust_size(help_window))
    
    def open_settings_window(self):
        # Fenster für Einstellungen
        settings_window = tk.Toplevel(self)
        settings_window.title("Einstellungen")
        #Geometry soll später dem Inhalt angepasst werden
        #settings_window.geometry("200x320")
        
        ckButtonSonderzeichen = tk.Checkbutton(settings_window, text="Sonderzeichen ersetzen", variable=self.generator.replaceSpecialChars)
        ckButtonSonderzeichen.pack(anchor="w", padx=10, pady=5)
        ToolTip(ckButtonSonderzeichen, "Ersetzt einige Sonderzeichen nach einer festgelegten Tabelle")

        # Combobox für Verify
        tk.Label(settings_window, text="Verify:").pack(anchor="w", padx=10, pady=(10,0))

        #self.verify_var = tk.StringVar(value=str(self.cfg.get("verify", True)))
        self.verify_var = tk.StringVar(value=str(logic.sv.verify))
        cb_verify = ttk.Combobox(settings_window, textvariable=self.verify_var, state="readonly")
        cb_verify["values"] = ("True", "False", "server.pem")
        cb_verify.pack(fill="x", padx=10, pady=5)

        ToolTip(cb_verify, "Legt fest, ob und wie SSL-Zertifikate geprüft werden")

        # Schließen-Button
        def on_close():
            val = self.verify_var.get()
            if val == "True":
                logic.sv.verify = True
            elif val == "False":
                logic.sv.verify = False
            else:
                if os.path.exists("server.pem"):
                    logic.sv.verify = "server.pem"
                else: 
                    logic.sv.verify = logic.sv.download_server_cert()
            settings_window.destroy()

        tk.Button(settings_window, text="Schließen", command=on_close).pack(pady=10)        
        # Let Tkinter calculate the required size
        settings_window.after(80, lambda: self.adjust_size(settings_window))

    def show_statistik(self):
        report = "Anzahlen der Einträge in den verschiedenen Keys:\n"
        for key in ["jahrgaenge","klassen","lehrer","faecher","lerngruppen", "schueler"]:
            report += f"{key}: {len(getattr(self.generator,key,[]))}\n"
        
        # Zufällige Elemente aus den wichtigsten listen anzeigen
        for listenname in ["schueler","lerngruppen","lehrer"]:
            report += f'\nZufälliges Element aus "{listenname}" anzeigen:\n'
            akt_liste = getattr(self.generator, listenname, [])
            if akt_liste:
                s = random.choice(akt_liste)
                # als schön formatierten JSON-String
                report += json.dumps(s, indent=2, ensure_ascii=False)
                report += "\n"

        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def tempHIlfsfunktion(self):
        res = collect_values(getattr(self.generator,"lerngruppen",[]),"kursartKuerzel")
        self.report_text.insert(tk.END,f"Es gibt folgende kursartKuerzel: {res}\n")
        res = collect_values(getattr(self.generator,"schueler",[]),"status")
        self.report_text.insert(tk.END,f"Es gibt folgende Status-Werte bei den SuS: {res}\n")
        lg_pro_jahrgang = count_lerngruppen_pro_jahrgang(getattr(self.generator, "lerngruppen", []))
        self.report_text.insert(tk.END,f"Es gibt folgende Anzahl Lerngruppen in jedem Jahrgang:\n{lg_pro_jahrgang}\n")
        # Klassen der Schüler einer zufälligen Lerngruppe ausgeben
        rnd_lg = random.choice(getattr(self.generator, "lerngruppen", [-1]))
        rnd_lg_bez = rnd_lg.get("teamBez", rnd_lg.get("bezeichnung", "---"))
        ergText = f"In der Lergruppe {rnd_lg_bez} sind die folgenden Klassen {self.generator.get_kl_jg_zu_schuelerIDListe(rnd_lg.get("idsSchueler",[]))}\n"
        ergText += f"bzw. die folgenden Jahrgänge {self.generator.get_kl_jg_zu_schuelerIDListe(rnd_lg.get("idsSchueler",[]), art="jahrgaenge")}\n"
        self.report_text.insert(tk.END, ergText)



def collect_values(objs, key, unique=True):
    """Gibt alle vorkommenden Werte zu einem Key aus einer Liste von Dicts zurück."""
    if unique:
        return list({obj.get(key) for obj in objs if key in obj})
    else: 
        return [obj.get(key) for obj in objs if key in obj]


def count_lerngruppen_pro_jahrgang(lerngruppen):
    counts = {}

    for lg in lerngruppen:
        jg = lg.get("jahrgang")
        if not jg:        # None oder fehlt
            jg = "ohne"
        counts[jg] = counts.get(jg, 0) + 1 #Wenn nicht vorhanden auf 0 setzen

    return counts



# Anwendung starten
if __name__ == "__main__":
    app = ReportApp()
    app.mainloop()
