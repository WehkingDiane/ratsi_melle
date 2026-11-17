# Plan: Geschützter Ratsbereich für SessionNet `/ri/`

Stand: 17.11.2026. Dieser Plan beschreibt die noch offenen Arbeiten. Der aktuelle
Funktionsumfang steht in der [RI-Übersicht](../ri/README.md), die Bedienung in der
[CLI-Anleitung](../ri/datenablauf.md). Historische Versionsangaben und frühere
Teilpakete sind im [Changelog](../../CHANGELOG.md) dokumentiert.

## Fortschritt

- [x] Öffentliche BI-/RI-Skriptnamen und vorbereitete Webnavigation einschließlich RI-Platzhaltern umgesetzt (PR #89 und #90).
- [x] Token-Datei und temporäre Proton-CLI-Sitzungen ohne Betriebssystem-Keyring umgesetzt (0.6.0).
- [x] RI-Anmeldung, Onlineindex, Dokumentabruf und lokaler Index praktisch im Testbereich erprobt und als reguläres CLI-Paket übernommen (0.7.0).
- [x] Getrennte RI-Datenwurzel `data/ri/`, Dokument-ID und Öffentlichkeitskennzeichnung sowie gezielte Offline-Tests umgesetzt.
- [ ] Verwaltungsausschuss, feinere Dokumentartauswahl und weitere Betriebsverträge abnehmen.
- [ ] Regeln für Sitzungszeitraum, Nachlauf und Aufbewahrung entscheiden; kontrollierte Bestandsbereinigung umsetzen.
- [x] Lokale Webformulare ohne Anmeldung für RI-Skripte, separate Jobablage und Jobausgaben umgesetzt (0.8.0).
- [ ] Geschützte Sitzungs-/Dateiansichten ergänzen und deren Web-/Exporttrennung abnehmen.

RI-Volltext-/Vektorindexierung und RI-Suche bleiben für die erste Ausbaustufe
zurückgestellt. Der komplette Vorhaben-Branch ist mit dem CLI-Paket noch nicht fertig.

## Ziel und Grenzen

BI bleibt der öffentliche Bestand. RI dient als separater lokaler Arbeitsbestand
zur Sitzungsvorbereitung. Eine spätere automatische Beschränkung auf heutige und
künftige Sitzungen ist noch keine implementierte Regel. Aktuell begrenzt die
Konfiguration den frühesten Sitzungsmonat auf November 2026.

RI-Dateien bleiben unabhängig von ihrer Öffentlichkeitskennzeichnung unter der
RI-Wurzel. Weder Sitzungsschluss noch ein erfolgreicher BI-Abgleich verschieben
Dateien oder Metadaten automatisch in öffentliche Indizes. Die Analysefunktionen
sind nicht Teil dieser Ausbaustufe.

### Bewertung und offene Regeln des temporären Arbeitsbestands

Vor regelmäßigem oder unbeaufsichtigtem Betrieb entscheiden:

- **Sitzungszeitraum:** Heutige/laufende Sitzungen, Zeitzone `Europe/Berlin`, fehlende Uhrzeiten sowie abgesagte und verschobene Termine berücksichtigen.
- **Nachlieferungen:** Nachlauf für spät veröffentlichte Anlagen oder Ergänzungen bestimmen; wiederholte Aktualisierung jüngerer Sitzungen berücksichtigen.
- **Aufbewahrung:** Löschfristen einschließlich Dokumenten, Datenbanken, Vorschaudaten, Exporten und Sicherungen festlegen. Vor Bereinigung den Umfang als Vorschau anzeigen.
- **RI-Zusätze:** Nicht davon ausgehen, dass alle RI-Dateien später im BI nachgeliefert werden. Bedarf und Aufbewahrung ausschließlich intern verfügbarer Unterlagen prüfen.
- **Betrieb:** Einzelbenutzer-/Mehrbenutzerbetrieb, Dateirechte, Sicherung und Wiederherstellung abnehmen. Getrennte Ordner allein ersetzen keine Zugriffssperre.

Nach einigen Monaten Nutzung kann längerfristige Aufbewahrung neu bewertet werden.
Eine neue Volltext- oder Vektorsuche wäre gesondert zu entscheiden.

## 1. Navigation und Skriptnamen

Die regulären CLI-Namen unterscheiden BI und RI. Seit 0.8.0 sind die RI-Einstiege für Zugang, Download, Build und Datenstatus direkt mit den Skripten verbunden. Der lokale Einzelplatzbetrieb verwendet keine Web-Anmeldung. Sitzungs- und Suchansichten bleiben Platzhalter.

## 2. Vorprüfung und verbindliche Entscheidungen

Die bisherigen Stichproben belegen wiederverwendbare SessionNet-Tabellenstrukturen
und zusätzliche RI-Dokumente bei einzelnen öffentlichen TOPs. Der CLI-Abruf wurde
am realen Bestand erprobt. Eine allgemeine Parsergleichheit oder Vollständigkeit
aller Gremien wird daraus nicht abgeleitet; der Verwaltungsausschuss bleibt die
priorisierte fehlende Bedarfsstichprobe.

Der Nutzer hat die Kennzeichnungsregel festgelegt: im BI verlinkte Dokument-IDs
sind `öffentlich`, alle anderen `nicht öffentlich`. Bei fehlgeschlagenem BI-Abgleich
gilt ebenfalls `nicht öffentlich`. Die Implementierung beschreibt damit Sichtbarkeit,
keine inhaltliche oder rechtliche Bewertung.

Der aktuelle Abruf übernimmt die verlinkten Sitzungs- und TOP-Dokumente einschließlich
Einladungen. Eine feinere Auswahl nach Dokumentart, Sammelunterlagen und Dubletten
bleibt offen. Die frühere Annahme eines bereits festgelegten Einladungsausschlusses
beschreibt den aktuellen CLI-Ablauf nicht.

## 3. Getrennte Datenhaltung und Build

Seit 0.7.0 liegen RI-Rohdaten, Onlineindex und lokaler Dokumentindex ausschließlich
unter `data/ri/`, Protokolle unter `logs/ri/`. Der gesamte RI-Bestand ist von Git
ausgeschlossen. Öffentliche Builder verwenden weiterhin ihre eigenen Wurzeln.
Die separate Onlinedatenbank enthält Portalmetadaten und ist kein Nachweis lokal
vorhandener Dateien. Der lokale Index beschreibt vorhandene, nicht leere Dateien.
Pfade, Dateiverträge und Aktualisierung stehen in der [CLI-Anleitung](../ri/datenablauf.md).

Für die spätere Bereinigung muss der Datenbankabgleich auch vollständig entfernte
Sitzungsordner berücksichtigen; der jetzige lokale Build behandelt geänderte Metadaten
und fehlende Dokumente innerhalb noch vorhandener Sitzungsordner. Eine automatische
Bereinigung wird damit nicht vorweggenommen. Kennzeichnungen sind Metadaten und
keine Erlaubnis zum Verschieben in BI.

## 4. RI-Fetcher mit Anmeldung

Die Proton-Anbindung über `.env/ri_token.txt`, temporäre Dateisitzungen, erlaubte
HTTPS-Ziele und automatische RI-/Proton-Abmeldung ist mit dem regulären Fetcher
verbunden. Zugangsdaten werden nicht als CLI-Argument übergeben. Anwendungscode
ändert keine Tresore, Einträge oder Tokenrechte. Der dokumentierte
Windows-Proton-Abmeldehinweis und zurückgestellte Neustart-/Ablaufprüfungen bleiben
offen; ein einzelner erfolgreicher Login ist keine Abnahme unbeaufsichtigten Betriebs.

Der prototypische Abruf ist real geprüft; die Projektübernahme wurde offline
validiert und der lokale Index am neuen Ort neu aufgebaut. Ein frischer Live-Abruf
mit den regulären Skripten wurde dabei nicht gestartet. Weitere reale Prüfungen
bleiben begrenzte, bewusst gestartete Nutzerläufe; reguläre Tests verwenden
synthetische Antworten und keine produktiven Geheimnisse.

## 5. Separate Suche (zurückgestellt)

Für die erste Ausbaustufe wird kein RI-Volltext-/Vektorindex und keine RI-Suche
aufgebaut. Öffentliche Suche und öffentliche Analyseauswahl erhalten keine RI-Daten.

## 6. Geschützte Oberfläche

Die [Navigationsübersicht](navigation.md) beschreibt den ursprünglichen Entwurf. Die [Web-Skriptsteuerung](../ri/oberflaeche.md) ohne Anmeldung und mit getrennten RI-Jobs ist umgesetzt. Als Nächstes sind Sitzungsansichten und Dateiauslieferung mit Pfadprüfung zu implementieren. Kalender, Dashboard, Exporte und öffentliche
Jobmeldungen dürfen keine unberechtigten RI-Metadaten anzeigen.
Für eine spätere Netzwerkbereitstellung sind Debug-Modus, stabiler Secret-Key, HTTPS und Sitzungsverhalten gesondert abzustimmen; die aktuelle Konfiguration bleibt lokal. Kennzeichnung und Herkunft bleiben auf den RI-Seiten sichtbar.

## Wiederverwendung zwischen BI und RI

Der erste RI-Webstand wird als funktionsfähiger Prototyp übernommen. Danach werden
Frontend und Backend beider Bereiche auf fachlich identische Abläufe und Strukturen
geprüft. Geeignete Teile sollen gemeinsame Objekte, Funktionen, Module oder Skripte
verwenden. Dazu gehören insbesondere Formulare, Seiten-/Ausgabebausteine,
Befehlsaufbau sowie Abruf-, Build- und Joblogik. Bereichsabhängige Konfiguration und
Verhalten bleiben ausdrücklich erhalten. Die konkreten offenen Arbeiten stehen
verbindlich in der [Aufgabenliste](project_tasks.md).

## Nächste Schritte und Abnahme

Die [Aufgabenliste](project_tasks.md) enthält ausschließlich die offenen Arbeitspakete.
Der Vorhaben-Branch ist abgeschlossen, wenn gezielter Abruf, lokaler Dokumentbestand
und freigegebene Bereinigung im geschützten Ratsbereich funktionieren, Trennungs-
und Berechtigungstests bestehen und der Betrieb einschließlich Sicherung und
Wiederherstellung dokumentiert und abgenommen ist.

Agenten führen nur gezielte schnelle Tests aus. Den vollständigen PR-Testlauf
übernimmt der Nutzer gemäß [Testdokumentation](../entwicklung/tests.md).
