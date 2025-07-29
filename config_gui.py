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
    "kursarten_ohne_klasse": ["AGGT"]
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

def show_config_gui(initial: dict | None = None) -> dict:
    cfg = load_config() if initial is None else initial.copy()

    root = tk.Tk()
    root.title("SVWS – Konfiguration")

    # Helpers
    def add_row(r, lbl, widget):
        ttk.Label(root, text=lbl).grid(row=r, column=0, sticky="w", padx=8, pady=6)
        widget.grid(row=r, column=1, sticky="ew", padx=8, pady=6)

    root.columnconfigure(1, weight=1)

    e_schema = ttk.Entry(root); e_schema.insert(0, cfg["schema"])
    e_host   = ttk.Entry(root); e_host.insert(0, cfg["host"])
    e_user   = ttk.Entry(root); e_user.insert(0, cfg["username"])
    e_pass   = ttk.Entry(root, show="*"); e_pass.insert(0, cfg["password"])

    s_jahr = ttk.Spinbox(root, from_=2000, to=2100, width=8); s_jahr.set(cfg["jahr"])
    s_abs  = ttk.Spinbox(root, values=(1,2), width=8); s_abs.set(cfg["abschnitt"])

    e_kurse = ttk.Entry(root)
    e_kurse.insert(0, ",".join(cfg.get("kursarten_ohne_klasse", [])))

    add_row(0, "Schema", e_schema)
    add_row(1, "Host (ohne /db/...)", e_host)
    add_row(2, "Username", e_user)
    add_row(3, "Passwort", e_pass)
    add_row(4, "Jahr", s_jahr)
    add_row(5, "Abschnitt", s_abs)
    add_row(6, "Kursarten ohne Klasse (kommagetrennt)", e_kurse)

    btns = ttk.Frame(root); btns.grid(row=7, column=0, columnspan=2, sticky="e", padx=8, pady=8)
    def on_save_close():
        try:
            kursarten = [x.strip() for x in e_kurse.get().split(",") if x.strip()]
            cfg.update({
                "schema": e_schema.get().strip(),
                "host": e_host.get().strip(),
                "username": e_user.get().strip(),
                "password": e_pass.get(),
                "jahr": int(s_jahr.get()),
                "abschnitt": int(s_abs.get()),
                "kursarten_ohne_klasse": kursarten,
            })
            # base_url aus host+schema ableiten (auch in cfg ablegen, wenn du magst)
            cfg["base_url"] = f"https://{cfg['host']}/db/{cfg['schema']}"
            save_config(cfg)
            messagebox.showinfo("Gespeichert", f"Konfiguration gespeichert nach {CONFIG_PATH}")
            root.destroy()
        except Exception as e:
            messagebox.showerror("Fehler", str(e))

    def on_cancel():
        root.destroy()

    ttk.Button(btns, text="Abbrechen", command=on_cancel).pack(side="right", padx=6)
    ttk.Button(btns, text="Speichern & Schließen", command=on_save_close).pack(side="right")

    root.mainloop()
    return cfg

# Beispielverwendung
if __name__ == "__main__":
    cfg = show_config_gui()
    print("Geladene Konfig:", json.dumps(cfg, ensure_ascii=False, indent=2))
