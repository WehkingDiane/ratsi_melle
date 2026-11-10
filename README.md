# Ratsi Melle

Die Anwendung sammelt öffentliche Sitzungs- und Dokumentdaten aus dem Bürgerinformationssystem der Stadt Melle (`/bi/`) und Veröffentlichungen des Landkreises Osnabrück. Sie erstellt lokale SQLite-Indizes und bietet semantische Suche sowie eine Django-Oberfläche für Datenpflege und Analyse.

Der geschützte Ratsbereich (`/ri/`) befindet sich im Ausbau. Lokale Token-Datei und manuelle Anmeldetests sind vorhanden (siehe [RI-Zugang](docs/ri/zugang.md)); RI-Dokumentabruf, Index und geschützter Webzugang sind noch nicht aktiviert.

## Schnellstart

In einer aktivierten Python-Umgebung aus dem Repository-Stamm:

```bash
pip install -r requirements.txt
python scripts/run_web.py
```

Die lokale Entwicklungsoberfläche ist unter `http://127.0.0.1:8000/` erreichbar und besitzt keine Benutzeranmeldung. Voraussetzungen und Hinweise für Windows/WSL stehen unter [Einrichtung](docs/betrieb/einrichtung.md).

## Dokumentation

Der [Dokumentationswegweiser](docs/README.md) erschließt alle Fachbereiche.

- [Daten abrufen](docs/datenabruf/README.md)
- [Suchindizes aufbauen](docs/suche/indizes.md)
- [Weboberfläche bedienen](docs/oberflaeche/README.md)
- [Analysen durchführen](docs/analyse/README.md)
- [RI-Zugang einrichten und prüfen](docs/ri/zugang.md)
- [Tests gezielt ausführen](docs/entwicklung/tests.md)

[Ist-Stand](docs/ist_stand.md), [RI-Plan](docs/plans/ri_ratsbereich_plan.md), [aktuelle Aufgaben](docs/plans/project_tasks.md) und [Changelog](CHANGELOG.md) beschreiben Umfang und Entwicklung. Verbindliche Arbeitsregeln stehen in [AGENTS.md](AGENTS.md).
