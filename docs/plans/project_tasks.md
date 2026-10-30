# Aktuelle Projektaufgabe

Stand: 30.10.2026. Das aktuelle Vorhaben ist der geschützte Ratsbereich für SessionNet `/ri/`, einschließlich der vorgezogenen Vorbereitung von Navigation und Seitenaufbau ohne RI-Zugang. Der [detaillierte Umsetzungsplan](ri_ratsbereich_plan.md) enthält Schutzgrenzen, Abnahmen und die vorgesehene Aufteilung in Teilbranches. Der vorhandene Funktionsumfang steht im [Ist-Stand](../ist_stand.md).

## Kontext

Zugangsdaten für `/ri/` liegen noch nicht vor. Gleichheit der RI-Seitenstruktur mit dem öffentlichen `/bi/`-Bereich ist eine Annahme, die erst nach Anmeldung geprüft werden kann. Schritt 1a ist auf dem Teilbranch umgesetzt: Bereichsnavigation, quellengebundene öffentliche Einstiege, informative RI-Platzhalter und ein vertikales Seitenlayout sind vorhanden. Öffentliche Daten bleiben weiterhin im bisherigen Ablauf verfügbar. RI-Daten werden zunächst vollständig als intern behandelt.

## RI-Vorhaben

#### Konkrete Aufgaben

- [ ] Daten- und Zugriffskontrakt für den lokalen Ratsbereich festlegen; Betriebsmodell, Speicherort und Suchindex-Zugriff nach Erhalt der Zugangsdaten prüfen.
- [ ] Eigenen authentifizierten RI-Fetcher für Sitzungsübersicht, Details und Dokumente umsetzen; öffentliche Parserfunktionen nur nach Strukturprüfung wiederverwenden.
- [ ] Getrennte RI-Rohdatenwurzel und RI-SQLite-Indizes aufbauen; Herkunft und Kennzeichnung pro Dokument speichern.
- [ ] RI-Dokumente in einem eigenen, zugriffsgeschützten Suchindex indexieren und getrennt durchsuchen.
- [ ] Abruf, Datenbankaufbau und Suche in einen geschützten Ratsbereich der Django-Oberfläche integrieren.
- [ ] Trennung zwischen öffentlichem und internem Bestand mit Tests und einer kleinen lokalen RI-Stichprobe abnehmen; Betriebsdokumentation aktualisieren.
