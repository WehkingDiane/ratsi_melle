# Softwareversionierung

Diese Datei beschreibt die Softwareversionierung des Projekts.

## Gewaehltes Schema

Das Projekt verwendet `Major.Minor.Patch` nach den Grundideen von Semantic Versioning.

Aktuelle Version:

- `0.1.0`

## Warum dieses Schema

- Das Projekt ist noch in einer fruehen Entwicklungsphase.
- Es gibt bereits mehrere Teilmodule und GUI-/CLI-Einstiegspunkte.
- Ein einfaches und bekanntes Schema erleichtert spaetere Releases, Changelogs und Deployment-Prozesse.

## Bedeutung waehrend der Entwicklungsphase

Solange das Projekt noch vor `1.0.0` liegt, gilt folgende Arbeitsregel:

- `0.x.0` fuer groessere Entwicklungsschritte oder inkompatible Aenderungen
- `0.x.y` fuer kleinere Erweiterungen, Bugfixes und inkrementelle Verbesserungen

Pragmatisch bedeutet das:

- `0.1.0` = erste klar definierte Entwicklungsbasis mit zentraler Versionierung
- `0.2.0` = naechster groesserer Meilenstein
- `0.1.1` = kleiner Bugfix oder kleine technische Verbesserung ohne neuen Meilenstein

## Single Source of Truth

Die kanonische Projektversion liegt in:

- `VERSION`

Python-Code greift zentral ueber `src/version.py` darauf zu.

## Verwendung im Projekt

- Python-Zugriff ueber `src.version.__version__`
- GUI-Anzeige im About-Dialog
- Dokumentation und spaetere Releases sollen sich an der Datei `VERSION` orientieren

## Versionspflege

Bei sichtbaren funktionalen Aenderungen, Meilensteinen oder Releases muss die Version bewusst angepasst werden.

Empfohlene Orientierung:

- Patch erhoehen:
  - Bugfixes
  - kleine interne Verbesserungen
  - kleinere UI-Korrekturen
- Minor erhoehen:
  - neue groessere Funktionen
  - neue Analysemodi
  - neue GUI-Bereiche
  - relevante Datenmodell- oder Workflow-Erweiterungen
- Major erhoehen:
  - erst ab `1.0.0` relevant
  - fuer klar inkompatible oder grundlegend geaenderte Releases
