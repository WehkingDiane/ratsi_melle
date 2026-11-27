# Weboberfläche bedienen

[Dokumentation](../README.md)

- Die aktive Oberfläche ist Django unter `web/`, gestartet mit `python scripts/run_web.py` auf `127.0.0.1:8000`.
- Das Dashboard zeigt kommende und vergangene Termine aus den gespeicherten Indizes. Unter `/daten/` lassen sich Fetch-, SQLite- und Vektorjobs starten und deren Status prüfen. `/service/` bündelt Wartung und Einstellungen.
- Veröffentlichung ist aus dem Menü entfernt; die bestehende URL `/veroeffentlichung/` bleibt als Platzhalter erreichbar.
- Die Oberfläche bleibt eine lokale Entwicklungsoberfläche mit `DEBUG=True`. Alle Bereiche einschließlich RI-Datenpflege und Jobausgaben sind ohne Web-Anmeldung erreichbar; der Signaturschlüssel stammt aus `RATSI_WEB_SECRET_KEY` oder wird pro Serverstart zufällig erzeugt. Der Betrieb ist auf den lokalen Rechner ausgerichtet.

## Navigation

Die Hauptnavigation enthält Übersicht, Bürgerinformation, Ratsbereich, Landkreis,
Erweiterungen und Einstellungen. `/buergerinformation/` und `/landkreis/` bieten
quellengebundene Such- und Datenpflege-Einstiege; die bisherigen URLs bleiben
verfügbar. Der Ratsbereich unter `/ratsbereich/` enthält die [lokale Skriptsteuerung](../ri/oberflaeche.md) für Zugang, Download und Datenbankaufbau sowie eine eigene Jobhistorie. Sitzungsübersicht, TOP-Details und lokale PDF-Auslieferung sind angebunden; die Suchansicht bleibt ein Platzhalter. Die Bedienung beschreibt die [RI-Oberflächenanleitung](../ri/oberflaeche.md#sitzungen-und-dokumente).

Analyse ist unter [Erweiterungen](../analyse/README.md) erreichbar. Die [Sitzungsübersicht](sitzungen.md) bietet Gremienfilter. Einrichtung und Start stehen unter [Betrieb](../betrieb/einrichtung.md).
