# TODO

- [x] f-Strings finden, bei denen Anführungszeichen "doppelt" bzw. gleich sind (z.B. verschachtelte `f"...{x['y']}..."` mit gleichem Anführungszeichen-Typ innen und außen) – betraf `generator.py:406` und `generator.py:412` (Aufrufe mit `art="jahrgaenge"`/`art="klassen"` innerhalb eines f-Strings mit doppelten Anführungszeichen; vor Python 3.12 ein SyntaxError, z.B. auf Windows-Builds mit älterem Python). Behoben durch einfache Anführungszeichen innen.
- [ ] Umstellung auf neues Format mit `Arbeitsgruppen;Cloud#Kurse;Cloud#Gruppen`
- [ ] Ermittlung, welche Kurse eher Gruppen und welche eher Kurse sind – es fallen eigentlich nur AGs und die Jahrgangsteams raus, die manuell eingerichtet werden
