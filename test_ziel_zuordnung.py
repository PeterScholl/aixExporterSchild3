"""Manueller Smoke-Test für Schritt 1 der Cloud-Gruppen-Zuordnung (siehe TODO.md).

Es geht um die Zielspalte/Zielkategorie einer Lerngruppe, also die Unterscheidung, ob sie beim
Export als Arbeitsgruppe, Cloud#Kurs oder Cloud#Gruppe behandelt wird (siehe README.md, Abschnitt
"CSV-Import-Format für MNSpro Cloud").

Kein pytest nötig - einfach ausführen:
    python test_ziel_zuordnung.py

Prüft get_ziel_fuer_lerngruppe() und fehlende_kursart_zuordnungen() ganz ohne
SVWS-Server-Verbindung, DB oder GUI - Generator() kann dafür offline instanziiert werden.
"""
from generator import Generator


def check(bezeichnung, tatsaechlich, erwartet):
    status = "OK" if tatsaechlich == erwartet else "FEHLER"
    print(f"[{status}] {bezeichnung}: erwartet={erwartet!r} erhalten={tatsaechlich!r}")
    assert tatsaechlich == erwartet, bezeichnung


def main():
    g = Generator()

    # Grundkonfiguration wie sie später über die geplanten Dialoge (Schritt 2 & 3) gepflegt würde
    g.kursart_zuordnung = {
        "GK": "kurs",
        "LK": "kurs",
        "AGGT": "arbeitsgruppe",
    }
    g.bezeichnung_muster = [
        {"pattern": r"^Fachschaft ", "ziel": "gruppe"},
    ]
    g.zuordnung_overrides = {
        999: "gruppe",
    }

    # 1. kursartKuerzel-Regel greift (unterste Priorität, aber einzige zutreffende Regel)
    lg_gk = {"id": 1, "bezeichnung": "Mathematik GK", "kursartKuerzel": "GK"}
    check("kursartKuerzel-Regel (GK -> kurs)", g.get_ziel_fuer_lerngruppe(lg_gk), "kurs")

    # 2. Bezeichnungs-Muster hat Vorrang vor kursartKuerzel
    lg_fs = {"id": 2, "bezeichnung": "Fachschaft Mathematik", "kursartKuerzel": "GK"}
    check("Muster vor kursartKuerzel (Fachschaft -> gruppe)", g.get_ziel_fuer_lerngruppe(lg_fs), "gruppe")

    # 3. Manueller Override hat Vorrang vor allem anderen
    lg_override = {"id": 999, "bezeichnung": "Fachschaft Mathematik", "kursartKuerzel": "GK"}
    check("Override vor Muster und kursartKuerzel", g.get_ziel_fuer_lerngruppe(lg_override), "gruppe")

    # 4. Arbeitsgruppe über kursartKuerzel
    lg_ag = {"id": 3, "bezeichnung": "Schach-AG", "kursartKuerzel": "AGGT"}
    check("kursartKuerzel-Regel (AGGT -> arbeitsgruppe)", g.get_ziel_fuer_lerngruppe(lg_ag), "arbeitsgruppe")

    # 5. Unbekanntes kursartKuerzel -> nicht klassifiziert (None)
    lg_unbekannt = {"id": 4, "bezeichnung": "Sonderkurs", "kursartKuerzel": "XYZ"}
    check("unbekanntes kursartKuerzel -> None", g.get_ziel_fuer_lerngruppe(lg_unbekannt), None)

    # 6. fehlende_kursart_zuordnungen findet unklassifizierte Kürzel
    g.lerngruppen = [lg_gk, lg_fs, lg_override, lg_ag, lg_unbekannt]
    fehlende = g.fehlende_kursart_zuordnungen()
    check("fehlende_kursart_zuordnungen findet XYZ", fehlende, ["XYZ"])

    print("\nAlle Prüfungen erfolgreich.")


if __name__ == "__main__":
    main()
