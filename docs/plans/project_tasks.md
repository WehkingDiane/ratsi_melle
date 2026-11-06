# Aktuelle Projektaufgabe

Stand: 06.11.2026. Das aktuelle Vorhaben ist der geschützte Ratsbereich für SessionNet `/ri/`, einschließlich der vorgezogenen Vorbereitung von Navigation und Seitenaufbau ohne RI-Zugang. Der [detaillierte Umsetzungsplan](ri_ratsbereich_plan.md) enthält Schutzgrenzen, Abnahmen und die vorgesehene Aufteilung in Teilbranches. Der vorhandene Funktionsumfang steht im [Ist-Stand](../ist_stand.md).

## Kontext

Der gezielte lokale Abruf der RI-Zugangsdaten aus Proton Pass sowie RI-Anmeldung und RI-Abmeldung sind unter WSL und Windows bestätigt; Zugangswerte liegen weder im Repository noch im Chat. Gleichheit der RI-Sitzungsstruktur mit dem öffentlichen `/bi/`-Bereich bleibt eine ungeprüfte Annahme; eine vertrauliche Beispiel-Sitzung wurde noch nicht untersucht. Schritt 1a ist umgesetzt und über PR #90 in den Vorhaben-Branch übernommen: Bereichsnavigation, quellengebundene öffentliche Einstiege, informative RI-Platzhalter und ein vertikales Seitenlayout sind vorhanden. Öffentliche Daten bleiben weiterhin im bisherigen Ablauf verfügbar. RI-Daten werden zunächst vollständig als intern behandelt.

Bereits erledigt (Statuskontext; die Aufgabenliste darunter enthält nur offene Arbeiten):

- **Erledigt:** BI-/RI-Skriptnamen einschließlich Aufrufern, Tests und Dokumentation geordnet; über PR #89 übernommen.
- **Erledigt:** Navigation, öffentliche Einstiege, RI-Platzhalter und vertikalen Seitenaufbau einschließlich dokumentierter Tests und Browserabnahme umgesetzt; über PR #90 übernommen.
- **Erledigt:** [Proton-Einrichtung und manueller RI-Zugriffstest](ri_ratsbereich_plan.md#4-ri-fetcher-mit-anmeldung) auf `codex/feature/ri-proton-pass-zugang` abgeschlossen (0.5.76). CLI 2.7.0, getrennte geschützte Tokenablage, feste RI-Eintragsbindung und ausschließlich lesender Zugangsdienst sind unter Windows und WSL eingerichtet. Gezielter Zugangsfeldabruf, RI-Anmeldung, RI-Abmeldung und erneute Zugangssperre sind auf beiden Systemen real bestätigt. 47 gezielte Tests je System, sechs betroffene Integrationstests und 690 reguläre Tests bestehen. Hilfsskripte und Bedienung sind dokumentiert. Der Nutzer stellt Neustart-/Ablaufprüfungen, unbeaufsichtigten Betrieb und die Untersuchung des Windows-Proton-Abmeldehinweises zurück; diese Punkte sind nicht als geprüft abgenommen. Die Fetcher-Anbindung bleibt ein späterer Schritt des RI-Hauptplans.

## RI-Vorhaben

#### Konkrete Aufgaben

- [ ] Als nächsten fachlichen Schritt den RI-Bereich erkunden: tatsächlichen Aufbau und Unterschiede zu BI feststellen, zunächst nur anhand von Seitenstruktur und Dokumentmetadaten. Auf Nutzerwunsch jetzt noch nicht durchführen.
- [ ] Vor Downloadimplementierung festlegen, welche RI-Dokumentarten benötigt, optional oder nicht benötigt sind; Auswahlregeln und Umgang mit Sammelunterlagen/Anlagen/Dubletten im [Hauptplan](ri_ratsbereich_plan.md#2-vorprüfung-und-verbindliche-entscheidungen) dokumentieren. Kein pauschaler Gesamtdownload.
- [ ] Daten- und Zugriffskontrakt für den lokalen Ratsbereich festlegen; Betriebsmodell, Speicherort und Suchindex-Zugriff vor der Datenanbindung prüfen.
- [ ] Bei Umsetzung des RI-Fetchers den geprüften Proton-Zugangsdienst einbinden; die abgeschlossene Einrichtung ist im [Hauptplan](ri_ratsbereich_plan.md#4-ri-fetcher-mit-anmeldung) dokumentiert. Zurückgestellte Betriebsprüfungen bei einem späteren erweiterten Betriebsumfang berücksichtigen.
- [ ] Eigenen authentifizierten RI-Fetcher für Sitzungsübersicht, Details und Dokumente umsetzen; öffentliche Parserfunktionen nur nach Strukturprüfung wiederverwenden.
- [ ] Getrennte RI-Rohdatenwurzel und RI-SQLite-Indizes aufbauen; Herkunft und Kennzeichnung pro Dokument speichern.
- [ ] RI-Dokumente in einem eigenen, zugriffsgeschützten Suchindex indexieren und getrennt durchsuchen.
- [ ] Abruf, Datenbankaufbau und Suche in einen geschützten Ratsbereich der Django-Oberfläche integrieren.
- [ ] Trennung zwischen öffentlichem und internem Bestand mit Tests und einer kleinen lokalen RI-Stichprobe abnehmen; Betriebsdokumentation aktualisieren.
