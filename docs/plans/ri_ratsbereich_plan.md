# Plan: Geschützter Ratsbereich für SessionNet `/ri/`

Stand: 27.11.2026. Dieser Plan beschreibt die noch offenen Arbeiten. Der aktuelle
Funktionsumfang steht in der [RI-Übersicht](../ri/README.md), die Bedienung in der
[CLI-Anleitung](../ri/datenablauf.md). Historische Versionsangaben und frühere
Teilpakete sind im [Changelog](../../CHANGELOG.md) dokumentiert.

## Fortschritt

- [x] Öffentliche BI-/RI-Skriptnamen und vorbereitete Webnavigation einschließlich RI-Platzhaltern umgesetzt (PR #89 und #90).
- [x] Token-Datei und temporäre Proton-CLI-Sitzungen ohne Betriebssystem-Keyring umgesetzt (0.6.0).
- [x] RI-Anmeldung, Onlineindex, Dokumentabruf und lokaler Index praktisch im Testbereich erprobt und als reguläres CLI-Paket übernommen (0.7.0).
- [x] Getrennte RI-Datenwurzel `data/ri/`, Dokument-ID und Öffentlichkeitskennzeichnung sowie gezielte Offline-Tests umgesetzt.
- [x] Verwaltungsausschuss 8178 anhand echter HTML-/Dokumentmetadaten und der UI-Kette geprüft (22.11.2026).
- [ ] Feinere Dokumentartauswahl und weitere Betriebsverträge abnehmen.
- [x] Lokale Webformulare ohne Anmeldung für RI-Skripte, separate Jobablage und Jobausgaben umgesetzt (0.8.0).
- [x] Lokale RI-Sitzungs-/Dateiansichten mit Pfadprüfung und Offline-Negativtests ergänzt (0.9.0).
- [x] Echte UI-Kette für 8178/8179 einschließlich PDF und BI-Endpunkttrennung geprüft; Hinweise dokumentiert.
- [x] Ursachenprüfung für 9516/8181 und den aktuellen Bestand von 8176 abgeschlossen und vom Nutzer als erledigt bestätigt (27.11.2026).
- [x] Lokalen Indexnachlauf für 8176 ausgeführt und 14/14 verfügbare Dokumente verifiziert (27.11.2026).
- [x] Kalenderstatus und geänderte Termine in Parser, Indizes und UI umgesetzt (0.10.0).
- [x] RI-Webdownload mit optionalem, zunächst aktiviertem lokalem Indexnachlauf und getrennten Phasenergebnissen umgesetzt (0.10.0).
- [ ] Export-/Betriebsabnahme abschließen.

RI-Volltext-/Vektorindexierung und RI-Suche bleiben für die erste Ausbaustufe
zurückgestellt. Der komplette Vorhaben-Branch ist mit dem CLI-Paket noch nicht fertig.

## Ziel und Grenzen

BI bleibt der öffentliche Bestand. RI dient als separater lokaler Arbeitsbestand
zur Sitzungsvorbereitung. Aufbewahrung und Dokumentlöschung verwaltet der Nutzer
manuell; automatische Altersgrenzen oder Bereinigung sind nicht vorgesehen.
Verbindlich ist die [Festlegung zur manuellen Verwaltung](../ri/datenablauf.md#aufbewahrung-und-manuelles-löschen).
Die bestehende Abrufkonfiguration begrenzt den frühesten Sitzungsmonat auf November 2026.

RI-Dateien bleiben unabhängig von ihrer Öffentlichkeitskennzeichnung unter der
RI-Wurzel. Weder Sitzungsschluss noch ein erfolgreicher BI-Abgleich verschieben
Dateien oder Metadaten automatisch in öffentliche Indizes. Die Analysefunktionen
sind nicht Teil dieser Ausbaustufe.

### Festgelegter Umfang und Betrieb

Die Aufbewahrungsentscheidung vom 27.11.2026 ist abgeschlossen. Weitere
Fristenbewertung, automatische Bereinigung und zeitgesteuerte Dateilöschung
gehören nicht zum Vorhaben. Die fachliche Erkennung verschobener/abgesagter
Termine und ein verlässlicher Indexnachlauf bleiben unabhängig davon erforderlich.

Offen bleibt die Betriebsabnahme für Dateirechte, Sicherung/Wiederherstellung
und erweiterten Betrieb. Eine neue Volltext- oder Vektorsuche wäre gesondert
zu entscheiden. RI-Dateien werden weiterhin nicht automatisch nach BI übernommen.

## 1. Navigation und Skriptnamen

Die regulären CLI-Namen unterscheiden BI und RI. Seit 0.8.0 sind die RI-Einstiege für Zugang, Download, Build und Datenstatus direkt mit den Skripten verbunden. Der lokale Einzelplatzbetrieb verwendet keine Web-Anmeldung. Seit 0.9.0 sind Sitzungslisten, Details und lokale PDFs angebunden; die Suchansicht bleibt ein Platzhalter.

## 2. Vorprüfung und verbindliche Entscheidungen

Die bisherigen Stichproben belegen wiederverwendbare SessionNet-Tabellenstrukturen
und zusätzliche RI-Dokumente bei einzelnen öffentlichen TOPs. Der CLI-Abruf wurde
am realen Bestand erprobt. Eine allgemeine Parsergleichheit oder Vollständigkeit
aller Gremien wird daraus nicht abgeleitet. Der Verwaltungsausschuss 8178 wurde
am 22.11.2026 als begrenzte reale Bedarfsstichprobe geprüft: 23 N-TOP-Einträge und
43 Dokumente mit konsistenten Metadaten und PDF-Auslieferung. Ergebnisse und
Grenzen stehen in der [UI-Abnahme](../ri/oberflaeche.md#reale-ui-abnahme-vom-22112026).

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

Der lokale Build behandelt geänderte Metadaten und fehlende Dokumente innerhalb
noch vorhandener Sitzungsordner. Grenzen nach manuellen Löschungen stehen im
[Datenablauf](../ri/datenablauf.md#aufbewahrung-und-manuelles-löschen).
Kennzeichnungen sind Metadaten und keine Erlaubnis zum Verschieben in BI.

## 4. RI-Fetcher mit Anmeldung

Die Proton-Anbindung über `.env/ri_token.txt`, temporäre Dateisitzungen, erlaubte
HTTPS-Ziele und automatische RI-/Proton-Abmeldung ist mit dem regulären Fetcher
verbunden. Zugangsdaten werden nicht als CLI-Argument übergeben. Anwendungscode
ändert keine Tresore, Einträge oder Tokenrechte. Der dokumentierte
Windows-Proton-Abmeldehinweis und zurückgestellte Neustart-/Ablaufprüfungen bleiben
offen; ein einzelner erfolgreicher Login ist keine Abnahme unbeaufsichtigten Betriebs.

Der prototypische Abruf ist real geprüft; die Projektübernahme wurde offline
validiert und der lokale Index am neuen Ort neu aufgebaut. Ein frischer Live-Abruf
mit den regulären Skripten wurde bei dieser früheren Übernahme nicht gestartet.
Am 22.11.2026 folgte ein ausdrücklich beauftragter realer Dezember-Abruf über das
Webformular mit anschließendem lokalem Build und PDF-Prüfung für 8178/8179.
Weitere reale Prüfungen bleiben begrenzte, bewusst gestartete Läufe; reguläre
Tests verwenden synthetische Antworten und keine produktiven Geheimnisse.

## 5. Separate Suche (zurückgestellt)

Für die erste Ausbaustufe wird kein RI-Volltext-/Vektorindex und keine RI-Suche
aufgebaut. Öffentliche Suche und öffentliche Analyseauswahl erhalten keine RI-Daten.

## 6. Geschützte Oberfläche

Die [Navigationsübersicht](navigation.md) beschreibt den ursprünglichen Entwurf. Die [Web-Skriptsteuerung](../ri/oberflaeche.md) ohne Anmeldung und mit getrennten RI-Jobs ist umgesetzt. Seit 0.9.0 sind lokale Sitzungsansichten und PDF-Auslieferung mit Pfadprüfung implementiert; Listen-/Detailtemplates und Filterlogik werden mit BI geteilt. Die lokale Startseite führt seit 0.9.1 BI-/RI-Termine mit getrennten Direktlinks zusammen und wird ohne Zwischenspeicherung ausgeliefert. Öffentliche Indizes, Suche, Exporte und öffentliche
Jobmeldungen erhalten weiterhin keine RI-Metadaten.
Für eine spätere Netzwerkbereitstellung sind Debug-Modus, stabiler Secret-Key, HTTPS und Sitzungsverhalten gesondert abzustimmen; die aktuelle Konfiguration bleibt lokal. Kennzeichnung und Herkunft bleiben auf den RI-Seiten sichtbar.

## Wiederverwendung zwischen BI und RI

Der erste RI-Webstand wird als funktionsfähiger Prototyp übernommen. Die UI-Prüfung
ist seit 0.9.3 umgesetzt: Sitzungsansichten und Filter, Formular-/Feldrenderer,
Statuspanelrahmen sowie Auftragspanel und Live-Aktualisierung werden gemeinsam
verwendet. Die [UI-Regeln](../entwicklung/ui_guidelines.md#wiederverwendung-zwischen-bi-und-ri)
führen Bausteine und erhaltene Unterschiede auf. Weitere Wiederverwendung im
Backend betrifft Befehlsaufbau sowie Abruf-, Build- und Joblogik. Bereichsabhängige Konfiguration und
Verhalten bleiben ausdrücklich erhalten. Die konkreten offenen Arbeiten stehen
verbindlich in der [Aufgabenliste](project_tasks.md).

## Umgesetzter Kalenderstatus und Indexnachlauf

Kalenderstatus und Indexnachlauf sind seit 0.10.0 umgesetzt. Die folgende
Beschreibung hält Datenvertrag, Ablauf und gezielte Prüfungen fest. Aufbewahrung und
manuelle Dateilöschung werden davon nicht geändert.

### 1. Verschobene und abgesagte Termine

Die umgesetzte Kalenderstatus-Verarbeitung umfasst:

Die gemeinsame Implementierung liegt in `src/fetching/calendar_status.py` und
`src/indexing/calendar_metadata.py`. Der verbindliche Datenvertrag steht unter
[Kalenderstatus](../ri/datenablauf.md#kalenderstatus), die Anzeige in der
[Sitzungsübersicht](../oberflaeche/sitzungen.md#geänderte-termine).

Die Prüfungen verwenden synthetische Kalender mit Jahreswechsel (9516), einem
expliziten Ersatzverweis (8181/9514), Absagen (7168/7169), unbekannten Hinweisen
und unveränderten regulären Terminen. Teilabsagen und verneinte Hinweise werden
nicht als bestätigte Gesamtabsage behandelt. Fremde Ersatzlinks und Weiterleitungen
auf andere Sitzungs-IDs werden nicht übernommen. Statusänderungen erhalten
vorhandene Dokumente; neue Kalenderfelder ergänzen alte Datenbanken additiv.

### 2. Download mit lokalem Indexnachlauf

Der RI-Webauftrag führt zwei feste Phasen unter demselben Auftragsschutz aus:

1. Das Downloadformular erhält „Lokalen Index anschließend aktualisieren“, standardmäßig aktiviert. Das Abschalten erhält den bisherigen reinen Download; der manuelle lokale Build bleibt verfügbar.
2. Ein Auftrag reserviert den bestehenden RI-Slot bis zum Ende beider Phasen. Zuerst läuft das vorhandene Downloadskript, danach der vorhandene lokale Builder. Keine neue Online-Anmeldung für den lokalen Schritt und keine Vermischung mit BI-Jobs.
3. Nach Download-Exitcode 0 oder 2 startet der inkrementelle lokale Builder. Er erkennt neue/geänderte Metadaten und Dateien bereits über `source_state`; ein pauschales Neuerstellen aller unveränderten Sitzungen ist nicht nötig. Nach einem harten Download-Abbruch keinen automatischen Erfolg melden; den nicht ausgeführten Indexnachlauf explizit anzeigen.
4. Phase, getrennte Exitcodes und phasenbezogene Ausgabe werden gespeichert und angezeigt. Download 0 + Index 0 ergibt Erfolg; Download 2 + Index 0 bleibt ein Warnabschluss; ein fehlgeschlagener Index ergibt einen Fehler mit dem Hinweis, dass heruntergeladene Dateien erhalten sind. Ein erfolgreicher Indexlauf hebt Download-/Abmeldewarnungen nicht auf.
5. Bei einem Indexfehler den lokalen Aufbau separat wiederholen können, ohne erneut herunterzuladen. Nach Abschluss Sitzungsansicht und Datenstatus aus der aktuellen lokalen Datenbank lesen.

Die Verkettung gehört in den Serverauftrag. Ein automatischer zweiter Browser-POST
wäre von der geöffneten Seite abhängig und könnte zwischen den Phasen mit einem
anderen Auftrag konkurrieren. Ein Aktualisieren erst beim Öffnen der Sitzungsseite
würde dagegen einen versteckten Schreibvorgang in einer Leseansicht erzeugen.

Gezielt geprüft sind: Download 0/2/1, Indexfehler und separat möglicher Wiederholungslauf,
Erhalt von Warnungen, Auftragsslot über beide Phasen und ein Fall wie 8176 mit neu
vorhandenen Dateien. Die manuellen Löschregeln bleiben unverändert.

## Nächste Schritte und Abnahme

Die [Aufgabenliste](project_tasks.md) enthält ausschließlich die offenen Arbeitspakete.
Das Vorhaben ist abgeschlossen, wenn gezielter Abruf, Kalenderstatus, aktueller
lokaler Dokumentbestand und Dateiansichten im Ratsbereich funktionieren,
Trennungs- und Berechtigungstests bestehen und der Betrieb einschließlich Sicherung
und Wiederherstellung dokumentiert und abgenommen ist. Eine automatische Bereinigung
ist ausdrücklich kein Abschlusskriterium.

Agenten führen nur gezielte schnelle Tests aus. Den vollständigen PR-Testlauf
übernimmt der Nutzer gemäß [Testdokumentation](../entwicklung/tests.md).
