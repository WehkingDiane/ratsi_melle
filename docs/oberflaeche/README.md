# Weboberfläche bedienen

[Dokumentation](../README.md)

- Die aktive Oberfläche ist Django unter `web/`, gestartet mit `python scripts/run_web.py` auf `127.0.0.1:8000`.
- Das Dashboard zeigt kommende und vergangene Termine aus den gespeicherten Indizes. Unter `/daten/` lassen sich Fetch-, SQLite- und Vektorjobs starten und deren Status prüfen. `/service/` bündelt Wartung und Einstellungen.
- Veröffentlichung ist aus dem Menü entfernt; die bestehende URL `/veroeffentlichung/` bleibt als Platzhalter erreichbar.
- Die aktuelle Django-Konfiguration ist eine lokale Entwicklungsoberfläche mit `DEBUG=True`, festem Entwicklungsschlüssel und ohne Benutzeranmeldung. Sie ist noch keine Zugangskontrolle für interne Ratsunterlagen.

## Navigation

Die Hauptnavigation enthält Übersicht, Bürgerinformation, Ratsbereich, Landkreis,
Erweiterungen und Einstellungen. `/buergerinformation/` und `/landkreis/` bieten
quellengebundene Such- und Datenpflege-Einstiege; die bisherigen URLs bleiben
verfügbar. Der Ratsbereich unter `/ratsbereich/` enthält informative Platzhalter.
Sie akzeptieren nur GET/HEAD; unbekannte Sitzungsdetails liefern 404. Die echte
RI-Anbindung und Zugriffssicherung stehen weiterhin aus.

Analyse ist unter [Erweiterungen](../analyse/README.md) erreichbar. Die [Sitzungsübersicht](sitzungen.md) bietet Gremienfilter. Einrichtung und Start stehen unter [Betrieb](../betrieb/einrichtung.md).
