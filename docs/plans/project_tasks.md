# Aktuelle Projektaufgabe

Stand: 10.11.2026. Das aktuelle Vorhaben ist der geschützte Ratsbereich für SessionNet `/ri/`, einschließlich der vorgezogenen Vorbereitung von Navigation und Seitenaufbau ohne RI-Zugang. Der [detaillierte Umsetzungsplan](ri_ratsbereich_plan.md) enthält Schutzgrenzen, Abnahmen und die vorgesehene Aufteilung in Teilbranches. Der vorhandene Funktionsumfang steht im [Ist-Stand](../ist_stand.md).

## Kontext

Der gezielte lokale Abruf der RI-Zugangsdaten aus Proton Pass sowie RI-Anmeldung und RI-Abmeldung sind unter WSL und Windows bestätigt; Zugangswerte liegen weder im Repository noch im Chat. Eine erste HTML-/Metadatenstichprobe und ein RI-/BI-Vergleich sind durchgeführt; gemeinsame Tabellenstrukturen und unterschiedliche Dokumentzusammenstellungen sind belegt. Vertrauliche Einzelheiten bleiben unter dem ignorierten Ordner `tmp/`. Eine allgemeine Parsergleichheit und der Bedarf beim Verwaltungsausschuss sind noch nicht geprüft. Schritt 1a ist umgesetzt und über PR #90 in den Vorhaben-Branch übernommen: Bereichsnavigation, quellengebundene öffentliche Einstiege, informative RI-Platzhalter und ein vertikales Seitenlayout sind vorhanden. Öffentliche Daten bleiben weiterhin im bisherigen Ablauf verfügbar. RI-Daten werden zunächst vollständig als intern behandelt.

Bereits erledigt (Statuskontext; die Aufgabenliste darunter enthält nur offene Arbeiten):

- **Erledigt:** BI-/RI-Skriptnamen einschließlich Aufrufern, Tests und Dokumentation geordnet; über PR #89 übernommen.
- **Erledigt:** Navigation, öffentliche Einstiege, RI-Platzhalter und vertikalen Seitenaufbau einschließlich dokumentierter Tests und Browserabnahme umgesetzt; über PR #90 übernommen.
- **Erledigt:** [Proton-Einrichtung und manueller RI-Zugriffstest](ri_ratsbereich_plan.md#4-ri-fetcher-mit-anmeldung) auf `codex/feature/ri-proton-pass-zugang` abgeschlossen (0.5.76). CLI 2.7.0, getrennte geschützte Tokenablage, feste RI-Eintragsbindung und ausschließlich lesender Zugangsdienst sind unter Windows und WSL eingerichtet. Gezielter Zugangsfeldabruf, RI-Anmeldung, RI-Abmeldung und erneute Zugangssperre sind auf beiden Systemen real bestätigt. 47 gezielte Tests je System, sechs betroffene Integrationstests und 690 reguläre Tests bestehen. Hilfsskripte und Bedienung sind dokumentiert. Der Nutzer stellt Neustart-/Ablaufprüfungen, unbeaufsichtigten Betrieb und die Untersuchung des Windows-Proton-Abmeldehinweises zurück; diese Punkte sind nicht als geprüft abgenommen. Die Fetcher-Anbindung bleibt ein späterer Schritt des RI-Hauptplans.

Seit 0.6.0 ist der Zugang auf eine lokale Token-Datei und temporäre CLI-Dateisitzungen ohne separate Eintragsbindung umgestellt. Synthetische Checks bestehen; Nutzerläufe unter Windows und begrenzte Erkundungsläufe unter WSL bestätigen den neuen Zugang. Unter Windows bleibt die entfernte Proton-Abmeldung unbestätigt. Die genannten realen Abnahmen bis 0.5.76 gelten für den vorherigen Ablauf. Die aktuelle Bedienung steht in der [RI-Zugangsanleitung](../ri/zugang.md).

Die vorläufige Richtung ist BI als Archiv vergangener Sitzungen und RI als temporärer Arbeitsbestand kommender Sitzungen. RI erhält zunächst nur eine Datenbank tatsächlich lokal vorhandener Dokumente und keine Volltext-/Vektorindexierung. Zeitgrenze, Nachlauf, Bereinigung und spätere Bedarfsprüfung sind im [Hauptplan](ri_ratsbereich_plan.md#bewertung-und-offene-regeln-des-temporären-arbeitsbestands) erläutert; diese Regeln sind noch nicht implementiert.

## RI-Vorhaben

#### Konkrete Aufgaben

- [ ] Sobald Unterlagen vorliegen, den Verwaltungsausschuss als priorisierte Stichprobe anhand von HTML-Struktur und Dokumentmetadaten erkunden; die erste Erkundung anderer Sitzungen ersetzt diesen Bedarfstest nicht.
- [ ] Vor Downloadimplementierung festlegen, welche RI-Dokumentarten benötigt, optional oder nicht benötigt sind; Auswahlregeln und Umgang mit Sammelunterlagen/Anlagen/Dubletten im [Hauptplan](ri_ratsbereich_plan.md#2-vorprüfung-und-verbindliche-entscheidungen) dokumentieren. Kein pauschaler Gesamtdownload; Einladungen (`EI`) sind für RI nicht benötigt.
- [ ] Zeitgrenze BI/RI einschließlich heutiger und verschobener Sitzungen, Nachlauf für Ergänzungen sowie Aufbewahrungs-/Bereinigungskonzept vor Umsetzung verbindlich festlegen.
- [ ] Daten- und Zugriffskontrakt für den lokalen RI-Arbeitsbestand festlegen; Betriebsmodell, Speicherort und Schutzrechte vor der Datenanbindung prüfen.
- [ ] Bei Umsetzung des RI-Fetchers den geprüften Proton-Zugangsdienst einbinden; die abgeschlossene Einrichtung ist im [Hauptplan](ri_ratsbereich_plan.md#4-ri-fetcher-mit-anmeldung) dokumentiert. Zurückgestellte Betriebsprüfungen bei einem späteren erweiterten Betriebsumfang berücksichtigen.
- [ ] Eigenen authentifizierten RI-Fetcher für Sitzungsübersicht, Details und Dokumente umsetzen; öffentliche Parserfunktionen nur nach Strukturprüfung wiederverwenden.
- [ ] Isolierte RI-Dateiwurzel und eine kleine lokale Dokumentdatenbank aufbauen; nur vorhandene Dateien mit Herkunft, Sitzung und Kennzeichnung erfassen.
- [ ] Kontrollierte regelmäßige RI-Bereinigung mit Vorschau und konsistentem Datenbankabgleich umsetzen; keine BI-Dateien einbeziehen.
- [ ] Gezielten Abruf, lokalen Dokumentbestand und freigegebene Bereinigung in den geschützten Ratsbereich der Django-Oberfläche integrieren.
- [ ] Trennung zwischen öffentlichem und internem Bestand mit Tests und einer kleinen lokalen RI-Stichprobe abnehmen; Betriebsdokumentation aktualisieren.
