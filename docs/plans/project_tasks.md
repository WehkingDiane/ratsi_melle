# Aktuelle Projektaufgabe

Stand: 27.10.2026. Die einzige aktuell geplante Erweiterung ist der geschützte Ratsbereich für SessionNet `/ri/`. Der [detaillierte Umsetzungsplan](ri_ratsbereich_plan.md) enthält Schutzgrenzen, Abnahmen und die vorgesehene Aufteilung in Teilbranches. Der vorhandene Funktionsumfang steht im [Ist-Stand](../ist_stand.md).

## Kontext

Zugangsdaten für `/ri/` liegen noch nicht vor. Gleichheit der RI-Seitenstruktur mit dem öffentlichen `/bi/`-Bereich ist eine Annahme, die erst nach Anmeldung geprüft werden kann. Öffentliche Daten bleiben weiterhin im bisherigen Ablauf verfügbar. RI-Daten werden zunächst vollständig als intern behandelt.

## RI-Vorhaben

#### Konkrete Aufgaben

- [ ] Daten- und Zugriffskontrakt für den lokalen Ratsbereich festlegen; Betriebsmodell, Speicherort und Suchindex-Zugriff nach Erhalt der Zugangsdaten prüfen.
- [ ] Eigenen authentifizierten RI-Fetcher für Sitzungsübersicht, Details und Dokumente umsetzen; öffentliche Parserfunktionen nur nach Strukturprüfung wiederverwenden.
- [ ] Getrennte RI-Rohdatenwurzel und RI-SQLite-Indizes aufbauen; Herkunft und Kennzeichnung pro Dokument speichern.
- [ ] RI-Dokumente in einem eigenen, zugriffsgeschützten Suchindex indexieren und getrennt durchsuchen.
- [ ] Abruf, Datenbankaufbau und Suche in einen geschützten Ratsbereich der Django-Oberfläche integrieren.
- [ ] Den [Navigationsentwurf](navigation.md) in der Oberflächenphase umsetzen: Sitzungen direkt erreichbar machen, Analyse unter Erweiterungen bündeln und Veröffentlichung aus der Navigation entfernen.
- [ ] Trennung zwischen öffentlichem und internem Bestand mit Tests und einer kleinen lokalen RI-Stichprobe abnehmen; Betriebsdokumentation aktualisieren.
