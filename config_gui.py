# config_gui.py
import json, os, tkinter as tk
from tkinter import ttk, filedialog, messagebox

DEFAULTS = {
    "schema": "svwsdb",
    "host": "localhost",
    "username": "admin",
    "password": "pass",
    "jahr": 2025,
    "abschnitt": 1,
    "kursarten_ohne_klasse": ["AGGT"],
    "kursarten_nur_mit_jahrgang": ["GK","LK"]
}

CONFIG_PATH = "config.json"

def load_config(path: str = CONFIG_PATH) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        # Fallbacks ergänzen
        for k, v in DEFAULTS.items():
            cfg.setdefault(k, v)
        return cfg
    return DEFAULTS.copy()

def save_config(cfg: dict, path: str = CONFIG_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def show_config_gui(master, initial: dict | None = None) -> dict | None:
    if not initial:
        return None
    cfg = initial.copy()

    win = tk.Toplevel(master)
    win.title("SVWS – Konfiguration")
    win.transient(master)
    win.grab_set()                 # modal
    win.columnconfigure(1, weight=1)

    def add_row(r, lbl, widget):
        ttk.Label(win, text=lbl).grid(row=r, column=0, sticky="w", padx=8, pady=6)
        widget.grid(row=r, column=1, sticky="ew", padx=8, pady=6)

    e_schema = ttk.Entry(win); e_schema.insert(0, cfg["schema"])
    e_host   = ttk.Entry(win); e_host.insert(0, cfg["host"])
    e_user   = ttk.Entry(win); e_user.insert(0, cfg["username"])
    e_pass   = ttk.Entry(win, show="*"); e_pass.insert(0, cfg["password"])
    s_jahr = ttk.Spinbox(win, from_=2000, to=2100, width=8); s_jahr.set(cfg["jahr"])
    s_abs  = ttk.Spinbox(win, values=(1,2), width=8); s_abs.set(cfg["abschnitt"])

    e_kurse = ttk.Entry(win);    e_kurse.insert(0, ",".join(cfg.get("kursarten_ohne_klasse", [])))
    e_jgkurse = ttk.Entry(win);  e_jgkurse.insert(0, ",".join(cfg.get("kursarten_nur_mit_jahrgang", [])))

    add_row(0, "Schema", e_schema)
    add_row(1, "Host (ohne /db/...)", e_host)
    add_row(2, "Username", e_user)
    add_row(3, "Passwort", e_pass)
    add_row(4, "Jahr", s_jahr)
    add_row(5, "Abschnitt", s_abs)
    add_row(6, "Kursarten ohne Klasse (kommagetrennt)", e_kurse)
    add_row(7, "Kursarten nur mit Jahrgang (kommagetrennt)", e_jgkurse)

    btns = ttk.Frame(win); btns.grid(row=8, column=0, columnspan=2, sticky="e", padx=8, pady=8)

    result = {"value": None}  # wird auf cfg gesetzt, wenn gespeichert

    def on_save_close():
        try:
            kursarten  = [x.strip() for x in e_kurse.get().split(",") if x.strip()]
            jgkursarten = [x.strip() for x in e_jgkurse.get().split(",") if x.strip()]
            cfg.update({
                "schema": e_schema.get().strip(),
                "host": e_host.get().strip(),
                "username": e_user.get().strip(),
                "password": e_pass.get(),
                "jahr": int(s_jahr.get()),
                "abschnitt": int(s_abs.get()),
                "kursarten_ohne_klasse": kursarten,
                "kursarten_nur_mit_jahrgang": jgkursarten
            })
            cfg["base_url"] = f"https://{cfg['host']}/db/{cfg['schema']}"
            result["value"] = cfg
            win.destroy()
        except Exception as e:
            messagebox.showerror("Fehler", str(e), parent=win)

    def on_cancel():
        result["value"] = None
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", on_cancel)

    ttk.Button(btns, text="Abbrechen", command=on_cancel).pack(side="right", padx=6)
    ttk.Button(btns, text="Speichern & Schließen", command=on_save_close).pack(side="right")

    win.wait_window()  # blockiert nur bis Dialog geschlossen ist
    return result["value"]

def show_noteam_gui(master, initial: dict) -> list | None:
    if not initial or "alle" not in initial:
        return None

    alle     = set(initial.get("alle", []))
    noTeams   = set(initial.get("noTeams", []))
    verfuegbar = sorted(alle - noTeams)

    win = tk.Toplevel(master)
    win.title("Teams von Auswahl ausschließen")
    win.transient(master)
    win.grab_set()
    win.geometry("700x400")
    win.columnconfigure(1, weight=0)

    # Linke Liste
    frame_l = ttk.Frame(win); frame_l.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
    ttk.Label(frame_l, text="Verfügbar").pack()
    list_l = tk.Listbox(frame_l, selectmode=tk.EXTENDED, width=30, height=20)
    list_l.pack(fill="both", expand=True)
    for item in verfuegbar:
        list_l.insert(tk.END, item)

    # Rechte Liste
    frame_r = ttk.Frame(win); frame_r.grid(row=0, column=2, padx=10, pady=10, sticky="nsew")
    ttk.Label(frame_r, text="Nicht zu erstellende Teams").pack()
    list_r = tk.Listbox(frame_r, selectmode=tk.EXTENDED, width=30, height=20)
    list_r.pack(fill="both", expand=True)
    for item in sorted(noTeams):
        list_r.insert(tk.END, item)

    # Buttons in der Mitte
    frame_m = ttk.Frame(win); frame_m.grid(row=0, column=1, sticky="ns")
    def move(src, dst):
        auswahl = src.curselection()
        werte = [src.get(i) for i in auswahl]
        for w in werte:
            if w not in dst.get(0, tk.END):
                dst.insert(tk.END, w)
            src.delete(src.get(0, tk.END).index(w))

         # Ziel-Liste aktualisieren, d.h. insbesondere sortieren
        aktuelle = list(dst.get(0, tk.END))
        neue_liste = sorted(set(aktuelle + werte))

        dst.delete(0, tk.END)
        for item in neue_liste:
            dst.insert(tk.END, item)

    ttk.Button(frame_m, text="→", width=4, command=lambda: move(list_l, list_r)).pack(pady=10)
    ttk.Button(frame_m, text="←", width=4, command=lambda: move(list_r, list_l)).pack(pady=10)

    # Footer
    btns = ttk.Frame(win); btns.grid(row=1, column=0, columnspan=3, sticky="e", padx=8, pady=8)
    result = {"value": None}

    def on_save_close():
        result["value"] = list(list_r.get(0, tk.END))
        win.destroy()

    def on_cancel():
        win.destroy()

    ttk.Button(btns, text="Abbrechen", command=on_cancel).pack(side="right", padx=6)
    ttk.Button(btns, text="Speichern & Schließen", command=on_save_close).pack(side="right")

    win.protocol("WM_DELETE_WINDOW", on_cancel)
    win.wait_window()
    return result["value"]

# Beispielverwendung
if __name__ == "__main__":
    cfg = show_config_gui(tk.Tk(), load_config())
    save_config(cfg)
    messagebox.showinfo("Gespeichert", f"Konfiguration gespeichert nach {CONFIG_PATH}")
            
    print("Geladene Konfig:", json.dumps(cfg, ensure_ascii=False, indent=2))
