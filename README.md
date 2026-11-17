# Ratsi Melle

Die Anwendung sammelt öffentliche Sitzungs- und Dokumentdaten aus dem Bürgerinformationssystem der Stadt Melle (`/bi/`) und Veröffentlichungen des Landkreises Osnabrück. Sie erstellt lokale SQLite-Indizes und bietet semantische Suche sowie eine Django-Oberfläche für Datenpflege und Analyse.

Für den Ratsbereich (`/ri/`) sind Anmeldung, Onlineindex, Dokumentabruf und lokaler Dokumentindex per CLI verfügbar. Die [RI-Anleitung](docs/ri/datenablauf.md) beschreibt den getrennten Bestand unter `data/ri/`. Die [geschützte RI-Datenpflege](docs/ri/oberflaeche.md) bindet diese Skripte in die Oberfläche ein; Sitzungsansichten und Bestandsbereinigung bleiben im Ausbau.

## Schnellstart

In einer aktivierten Python-Umgebung aus dem Repository-Stamm:

```bash
pip install -r requirements.txt
python scripts/run_web.py
```

Die lokale Entwicklungsoberfläche ist unter `http://127.0.0.1:8000/` erreichbar. Die RI-Datenpflege erfordert ein lokales Webkonto; öffentliche Bereiche bleiben ohne Anmeldung erreichbar. Voraussetzungen und Hinweise für Windows/WSL stehen unter [Einrichtung](docs/betrieb/einrichtung.md).

## Dokumentation

Der [Dokumentationswegweiser](docs/README.md) erschließt alle Fachbereiche.

- [Daten abrufen](docs/datenabruf/README.md)
- [Suchindizes aufbauen](docs/suche/indizes.md)
- [Weboberfläche bedienen](docs/oberflaeche/README.md)
- [Analysen durchführen](docs/analyse/README.md)
- [RI-Zugang einrichten und prüfen](docs/ri/zugang.md)
- [RI-Dokumente abrufen und lokal indexieren](docs/ri/datenablauf.md)
- [Tests gezielt ausführen](docs/entwicklung/tests.md)

[Ist-Stand](docs/ist_stand.md), [RI-Plan](docs/plans/ri_ratsbereich_plan.md), [aktuelle Aufgaben](docs/plans/project_tasks.md) und [Changelog](CHANGELOG.md) beschreiben Umfang und Entwicklung. Verbindliche Arbeitsregeln stehen in [AGENTS.md](AGENTS.md).
