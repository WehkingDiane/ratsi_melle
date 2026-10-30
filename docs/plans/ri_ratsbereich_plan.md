# Plan: Geschützter Ratsbereich für SessionNet `/ri/`

Stand: 30.10.2026. Dieser Plan ist die Grundlage für spätere Teilbranches. Er beschreibt noch keine freigeschaltete RI-Anbindung; Zugangsdaten und ein Beispiel der angemeldeten Seiten liegen derzeit nicht vor.

## Ziel und Grenzen

Der bestehende Ablauf „herunterladen → lokale Datenbank bauen → suchen“ soll auch für Unterlagen aus dem Ratsinformationssystem (RI) funktionieren. Der Bürgerinformationsbereich (`/bi/`) bleibt die Quelle des öffentlichen Datenbestands, auch für kommende Sitzungen. Ein Sitzungsdatum allein entscheidet nicht über die Vertraulichkeit: Unterlagen aus `/ri/` gelten zunächst insgesamt als geschützt, auch wenn eine PDF mit „Ö“ gekennzeichnet ist oder die Sitzung bereits stattgefunden hat.

RI-Rohdaten, Datenbanken, Suchindex, Protokolle und eventuelle Exporte dürfen nicht unbemerkt in öffentliche Pfade oder Abläufe gelangen. Die Analysefunktionen sind **nicht** Teil der ersten Umsetzung; RI-Inhalte werden ihnen auch nicht als auswählbare Quelle angeboten.

## Bestehende Anknüpfungspunkte

- `src/fetching/sessionnet_client.py` enthält HTTP-Abruf, HTML-Parsing und Dokumentdownload; sein Standardziel ist `/bi/`. Ob RI dieselben HTML- und Dokumentstrukturen verwendet, ist eine offene Annahme.
- `scripts/fetch_bi_session_from_index.py` nutzt die öffentliche Online-Indexdatenbank; `scripts/build_bi_online_index_db.py` baut diesen Index. Der RI-Abruf darf deren Standardpfade nicht verwenden.
- `scripts/build_bi_local_index.py` kann eine Rohdatenwurzel und einen Ausgabe-DB-Pfad erhalten. Die Eignung seiner Scanner- und Pfadlogik für einen isolierten RI-Bestand muss geprüft werden.
- `scripts/build_bi_vector_index.py` baut derzeit den öffentlichen Ratsinfo-Suchindex aus `local_index.sqlite`. Die Suche unter `web/search/` bietet gegenwärtig Ratsinfo und Landkreis als Quellen. Eine eigene RI-Collection und eindeutige Quellenwahl sind nötig.
- Die Weboberfläche läuft laut `web/web/settings.py` lokal im Entwicklungsmodus (`DEBUG=True`, feste Entwicklungsschlüssel, keine Benutzeranmeldung). Eine sichtbare Trennung in der Navigation wäre damit noch keine Zugriffssicherung.

## Vorgesehene Aufteilung in Teilbranches

Alle Teilbranches entstehen vom Vorhaben-Branch `codex/feature/ri-ratsbereich` und werden nach Review in diesen zurückgeführt. Konkrete Namen können bei Arbeitsbeginn angepasst werden:

Vor den folgenden RI-Teilbranches wird auf `codex/feature/ri-navigation-vorbereitung` die Navigation mit Platzhalterseiten und durchgehend untereinander angeordneten Hauptcontainern vorbereitet (Schritt 1a). Dieses Arbeitspaket benötigt keinen RI-Zugang.

1. `codex/feature/ri-ratsbereich-datenhaltung` – getrennte Pfade, Datenvertrag und Build aus RI-Rohdaten.
2. `codex/feature/ri-ratsbereich-fetch` – authentifizierter Abruf mit wiederverwendetem Parsing und Download.
3. `codex/feature/ri-ratsbereich-suche` – eigene Vektor-Collection, Build und Suchservice.
4. `codex/feature/ri-ratsbereich-web` – geschützte Bedienung für Abruf, Build und Suche.
5. Bei Bedarf ein kurzer Integrationsbranch vom Vorhaben-Branch für Schnittstellenanpassungen und End-to-End-Abnahme.

Die Daten- und Zugriffskontrakte werden vor paralleler Umsetzung festgelegt. Jeder Teilbranch soll einen abgegrenzten, prüfbaren Stand liefern. Änderungen an gemeinsam genutzten Modulen werden auf Rückwirkungen auf `/bi/` getestet.

## 1. Skriptnamen nach Datenbereich ordnen

Umsetzungsstand: Schritt 1 ist auf `codex/refactor/bi-ri-skriptnamen` umgesetzt. Die acht öffentlichen SessionNet-Skripte einschließlich Aufrufern und Dokumentation sind umbenannt; die Namenszuordnung steht in der README. Das ungenutzte `setup_venv.sh` ist nach bytegleicher Archivierung entfernt. Der vollständige WSL-Testlauf mit `python -m pytest` besteht: 1202 bestanden, einer übersprungen, acht Live-Tests abgewählt. Die vier im vorherigen Windows-Lauf aufgefallenen Plattformannahmen sind in den Tests korrigiert; ein erneuter Windows-Lauf wurde noch nicht bestätigt. Die Zusammenführung in den Vorhaben-Branch erfolgt per PR.

Vor der Erweiterung um RI-Funktionen die vorhandenen Skripte inventarisieren und eine einheitliche BI-/RI-Namenskonvention festlegen. Skripte, die heute allgemein benannt sind, aber ausschließlich den öffentlichen Bürgerinformationsbereich (`/bi/`) bearbeiten, sollen dies im Namen ausdrücken, zum Beispiel `fetch_bi_sessions.py`. Neue RI-Skripte erhalten entsprechend Namen wie `fetch_ri_sessions.py`.

Bei einer Umbenennung alle Aufrufer, Tests, Dokumentation und Automatisierungen mit anpassen. Die bestehenden Abläufe müssen danach weiterhin funktionieren. Gemeinsame oder bereichsübergreifende Werkzeuge behalten einen neutralen Namen; die Konvention soll keine künstliche Trennung gemeinsamer Komponenten erzwingen.

**Abnahme:** Für jedes Skript ist erkennbar, ob es BI, RI oder einen gemeinsamen Zweck hat. Alte Namen haben keine unbeabsichtigt verbliebenen Aufrufer; dokumentierte Kommandos und betroffene Tests sind angepasst.

## 1a. Navigation und Seitenaufbau ohne RI-Zugang vorbereiten

Arbeitsbranch: `codex/feature/ri-navigation-vorbereitung`. Umgesetzt in Version 0.5.64: Navigation und öffentliche Einstiege, RI-Platzhalter sowie vertikale Hauptbereiche. Navigation und Platzhalter wurden gemeinsam im ersten Implementierungscommit gesichert; Layout und Browserkorrekturen folgten in eigenen Zwischen-Commits. Dieser Zwischenschritt folgt auf die zusammengeführten BI-Skriptumbenennungen und wird vor der RI-Vorprüfung umgesetzt. Die Nummern der weiteren Schritte bleiben erhalten.

### Umfang und praktische Zwischen-Commits

1. **Navigation und öffentliche Einstiege:** Die Hauptnavigation gemäß [Navigationsentwurf](navigation.md) auf Übersicht, Bürgerinformation, Ratsbereich, Landkreis, Erweiterungen und Einstellungen umstellen. Analyse unter Erweiterungen bündeln, Veröffentlichung aus dem Menü entfernen. Vorhandene öffentliche Sitzungs-, Such- und Datenpflegefunktionen den passenden Bereichen zuordnen. Bei gemeinsam genutzten Seiten muss der gewählte Bereich eindeutig bleiben; BI- und Landkreis-Links dürfen nicht nur unterschiedlich heißen und dann unbemerkt denselben ungefilterten Bestand anzeigen. Bestehende URLs und gespeicherte Joblinks berücksichtigen.
2. **RI-Platzhalterseiten:** URLs, Views und Templates für die im Zielbild vorgesehenen RI-Seiten anlegen: Zugang, Sitzungen, Sitzungsdetails, Suche sowie Datenpflege für Abruf, Datenbank, Suchindex und Status/Jobs. Jede Seite erklärt ihren Zweck und zeigt „Ratsbereich noch nicht eingerichtet“. Benötigte Dateien erhalten einen konkreten Zweck und nutzbaren Platzhalterinhalt; keine vorsorglichen leeren Fetcher-, Datenbank- oder Authentifizierungsmodule anlegen. Keine Anmeldedaten entgegennehmen, RI-Jobs starten oder interne Daten einlesen. Unbekannte Sitzungen dürfen keine erfundenen Details erhalten.
3. **Hauptcontainer untereinander:** Alle bestehenden und neuen Seiten anhand einer Template-Inventur prüfen. Eigenständige Hauptbereiche wie Formular, Ergebnisse, Status und Jobhistorie wie im Dashboard in einer durchgehenden Spalte anordnen. Zusammengehörige Formularfelder, Tabellen und Bediengruppen innerhalb eines Containers dürfen ihren passenden Aufbau behalten. Bestehende Vergleichs- oder Leseransichten gesondert prüfen und bei Anpassungen ihre Bedienbarkeit erhalten. Zentrale Layoutbausteine verwenden und Desktop sowie schmale Fenster berücksichtigen.
4. **Abnahme und Dokumentation:** Seiten-, Navigations- und betroffene Workflowtests sowie eine visuelle Prüfung durchführen. README, Ist-Stand, UI-Regeln, Navigationsbeschreibung und Ist-Diagramm an die tatsächliche Umsetzung anpassen. Den Planstatus aktualisieren und `VERSION` beim ersten sichtbaren funktionalen Commit erhöhen. Jeder der vorherigen Zwischen-Commits enthält seine unmittelbar betroffenen Tests und Dokumentationsänderungen.

### Validierung des umgesetzten Zwischenstands

Der vollständige WSL-Testlauf ergab 1214 bestandene Tests, einen übersprungenen Test und acht abgewählte Live-Tests. Ein während des Laufs bereits korrigierter Test erwartete noch den alten Menütext „Service → Wartung“. Der anschließende gezielte Lauf auf dem aktuellen Stand bestand mit 23 Tests, einschließlich dieses Falls, der aktiven Navigation, der RI-Platzhalter und der Quellentrennung. Django-Systemprüfung und `git diff --check` sind ohne Befund.

Nachtrag aus dem PR-Review: Zwei Wartungsfälle von `test_build_and_maintenance_posts_stay_in_their_own_area` erwarteten ebenfalls noch „Service“. Diese im bisherigen Testvermerk nicht erfasste Erwartung ist auf den aktiven Bereich und die neue Beschriftung umgestellt; die Absicherung gegen den Start bereichsfremder Jobs bleibt erhalten. Die anschließende vollständige Integrationssuite mit `python -m pytest -m "integration and not live" -q` besteht: 607 bestanden, einer übersprungen, 616 abgewählt. Weitere fehlerhafte Webtest-Erwartungen wurden dabei nicht gefunden.

Im Browser wurden Datenpflege, RI-Platzhalter, Antwort-Leseansicht, Wartung und Landkreis-Suche geprüft. Bei 1440 Pixeln stehen die Hauptcontainer untereinander; bei 390 Pixeln bleiben die geprüften Seiten ohne horizontalen Überlauf. Das mobile Menü ist scrollbar, aktive Bereiche sind markiert und versteckte Laufhinweise bleiben verborgen. Es wurden keine produktiven Datenjobs gestartet.

### Grenzen und Abnahme

Die Platzhalter bereiten ausschließlich die Bedienoberfläche vor. Die echte RI-Anbindung und ihr Zugriffsschutz folgen nach Schritt 2 und den weiteren Umsetzungsschritten. Im Dashboard werden bis dahin nur vorhandene öffentliche Termine und Unterlagen angezeigt; RI-Links erscheinen erst bei tatsächlich verfügbaren und berechtigten Inhalten. Das Entfernen von Veröffentlichung aus dem Menü löscht keine Backend-Funktion oder vorhandenen Artefakte.

**Abnahme:** Die neue Navigation ist auf allen Seiten einschließlich aktiver Menükennzeichnung konsistent; Links sind erreichbar und alte öffentliche Recherche- und Datenjobs funktionieren weiter. Alle RI-Platzhalter sind als noch nicht eingerichtet erkennbar und lösen keine Datenoperation aus. Eigenständige Hauptcontainer stehen untereinander, ohne versteckte Statusmeldungen einzublenden oder bestehende Formulare und JavaScript-Anbindungen zu beschädigen. Die Abnahme ist ohne RI-Zugang und ohne produktive Downloads, Builds oder KI-Aufträge möglich.

## 2. Vorprüfung und verbindliche Entscheidungen

**Ohne RI-Zugang möglich:** Aufrufketten und Pfadannahmen erfassen; Daten- und Sicherheitsgrenzen festlegen; Tests mit synthetischen Seiten vorbereiten. Keine echten Zugangsdaten, Cookies oder vertraulichen Beispieldokumente ins Repository übernehmen.

**Nach Erhalt des Zugangs:** Anmeldeablauf prüfen (Formular, Umleitungen, eventuelle zusätzliche Faktoren, Ablauf der Sitzung), eine freigegebene Beispiel-Sitzung nur lokal untersuchen und HTML-, URL-, PDF- und Kennzeichnungsstruktur mit `/bi/` vergleichen. Herkunft und Zugriffsrechte vor automatisiertem Abruf klären. Weicht die Struktur ab, wird der RI-spezifische Parser ergänzt, statt den öffentlichen Parser auf Vermutung hin umzubauen.

Vor Implementierung verbindlich festlegen und dokumentieren:

- Betriebsmodell: nur lokal für eine Person oder Zugriff für mehrere Personen/Geräte. Davon hängen Web-Authentifizierung, Berechtigungen und der Speicherort ab.
- Sicherer Speicherort und Backup-Konzept für RI-Daten. Eine zweite SQLite-Datei unter demselben allgemein zugänglichen Datenordner ist für sich allein keine Zugriffssperre.
- Ob ein lokaler Qdrant-Server die RI-Collection zuverlässig nur für berechtigte Nutzer zugänglich macht. Falls nicht, RI-Suche erst mit einer passenden isolierten Instanz oder Zugriffssicherung aktivieren.
- Verfahren für Kennzeichnungen: „Ö“, „N“, „unklar“ und widersprüchliche Angaben; bis zur geprüften Einstufung bleibt jedes RI-Dokument intern.

## 3. Getrennte Datenhaltung und Build

Eine eigene, nicht versionierte RI-Rohdatenwurzel und eigene SQLite-Dateien für Sitzungsübersicht und lokalen Dokumentindex definieren. Vorgeschlagene Namen sind `data/raw/ri/`, `data/db/ri_online_index.sqlite` und `data/db/ri_local_index.sqlite`; bei Bedarf liegen sie außerhalb des Repositorys an einem zugriffsgeschützten Ort. Die endgültigen Pfade werden zentral konfiguriert. Der öffentliche Builder darf die RI-Wurzel nicht mitscannen, auch wenn sie innerhalb von `data/raw/` liegt.

Für die Herkunft jedes Datensatzes eine feste Quellenkennung (`bi` oder `ri`) verwenden. Dokumentidentitäten sollen Quelle, Sitzungs-ID und dokumenteigene URL/ID einbeziehen; gleiche Sitzungsnummern oder Titel dürfen die Bestände nicht verbinden. Lokale Dokumentpfade müssen innerhalb der jeweils erlaubten Rohdatenwurzel aufgelöst werden. Einmal abgerufene Rohdateien bleiben unverändert; Builds erzeugen nur abgeleitete Daten.

Öffentlichkeitskennzeichen als Metadatum mit Erkennungsquelle und Status speichern. Die Erkennung aus PDF-Kopf oder HTML ist eine Orientierung, keine Freigabe zum Verschieben. Für fehlende, mehrdeutige oder technisch nicht lesbare Kennzeichen gilt `unklar`. Ein späterer Abgleich mit `/bi/` darf nur Metadaten verknüpfen, keine RI-Datei in öffentliche Indizes kopieren.

**Abnahme:** Ein RI-Build mit Testdaten schreibt ausschließlich in RI-Zielpfade. Ein öffentlicher Neuaufbau nimmt keine RI-Sitzung, PDF oder Textpassage auf. Wiederholte Builds erzeugen keine Duplikate und verändern keine Rohdaten.

## 4. RI-Fetcher mit Anmeldung

Ein eigenes CLI-Skript für RI-Sitzungsübersicht und gezielte Sitzungsdownloads vorsehen. Wiederverwendbare Komponenten aus `SessionNetClient` nutzen, sobald HTML- und URL-Parität bestätigt ist. Der authentifizierte Client braucht eine klar abgegrenzte Anmeldung, eine zeitlich begrenzte HTTP-Sitzung und einen eindeutigen Fehler bei abgelaufener Anmeldung. Eine Login-Seite darf nie als Sitzungsdetail oder PDF gespeichert werden.

Zugangsdaten nicht als CLI-Argument oder im Quellcode hinterlegen; ein geeigneter lokaler Secret-Speicher oder eine geschützte Eingabe wird nach Prüfung des echten Loginablaufs gewählt. Passwort, Session-Cookies, Token und vollständige geschützte URLs aus Logs und Fehlermeldungen heraushalten. Umleitungen und Dokumentlinks auf erlaubte RI-Hosts und Pfade begrenzen; keine Credentials an fremde Hosts senden. Bestehende Grenzen für Downloadgröße, Rate-Limit, Retry und sichere Dateipfade gelten auch hier.

Fetch-Ergebnisse enthalten die Herkunft `ri` und werden ausschließlich in der RI-Rohdatenwurzel abgelegt. Inkrementelle Abrufe und explizite Aktualisierung folgen dem bestehenden Verhalten, sofern es mit dem angemeldeten Portal vereinbar ist.

**Abnahme:** Synthetische Tests prüfen erfolgreiche Anmeldung, Ablauf/Fehler, unerwartete Weiterleitung, fremden Dokumenthost, doppelte Abrufe und fehlende Dokumente. Der echte Ablauf wird erst mit Zugang und einer kleinen lokalen Probe verifiziert. Es gibt keine Netzwerktests mit produktiven Geheimnissen in der regulären Testsuite.

## 5. Separate Suche

Eine eigene RI-Collection und einen expliziten RI-Vektorbuild vorsehen. Die bestehende Ratsinfo-Collection (`ratsi_passages`) und die Landkreis-Collection bleiben unberührt. Der Suchdienst muss Quelle und zugehörige Pfadwurzel serverseitig festlegen; ein URL-Parameter darf keine beliebige Collection oder Dateiwurzel wählen. Ergebnislinks für RI-Dateien benötigen dieselbe Zugriffskontrolle wie die Suchseite.

Die Freigabe des RI-Index hängt von der Betriebsentscheidung aus Schritt 2 ab. Bei ungeschütztem gemeinsamem Qdrant-Server wird die RI-Collection nicht dort aufgebaut; für die erste Version kann stattdessen eine lokal isolierte Suchinstanz genutzt werden. Die Oberfläche zeigt den Status „RI-Suche noch nicht eingerichtet“, bis Index und Zugriff geprüft sind.

**Abnahme:** Öffentliche Suchen liefern keine RI-Treffer; RI-Suchen liefern nur RI-Treffer. Ein versehentliches Schreiben in öffentliche Collections wird durch Tests und Build-Vorprüfung verhindert. Fehlende Collections und abgelaufene Zugriffssitzungen führen zu klaren, inhaltsfreien Fehlermeldungen.

## 6. Einbindung in die Oberfläche

Die [Navigationsübersicht mit Ist- und Ziel-Diagramm](navigation.md) konkretisiert diese Phase. Schritt 1a zieht die Menüstruktur, RI-Platzhalter und das vertikale Seitenlayout vor. Hier werden die Platzhalter durch geschützte Funktionen ersetzt: ein gemeinsamer Sitzungskalender mit verfügbaren BI-/RI-Einstiegen; Bürgerinformation und geschützter Ratsbereich mit jeweils Sitzungen, Suche und Datenpflege. Interne Termine, Links und Metadaten im gemeinsamen Kalender benötigen die entsprechende Berechtigung.

Einen deutlich gekennzeichneten Ratsbereich für „Sitzungen abrufen“, „Datenbank bauen“ und „Suchen“ schaffen. Quelle und Schutzstatus bleiben auf jeder RI-Seite sichtbar. Start von RI-Jobs und Zugriff auf RI-Dateien werden serverseitig geschützt; ein bloßer Navigationsschalter oder eine lokale Browseransicht genügen nicht. Die bestehende Django-Konfiguration muss vor einer Nutzung mit RI-Daten hinsichtlich Debug-Modus, Secret-Key, Benutzeranmeldung, Sitzungen und Dateiauslieferung angepasst werden.

Die Jobliste darf keine RI-Titel, URLs, Dokumenttexte oder Zugangsdaten in öffentlich sichtbaren Statusmeldungen ausgeben. Datei-Downloads prüfen Pfad und Berechtigung bei jedem Aufruf. RI-Daten erscheinen weder in öffentlichen Dashboard-Zahlen noch in öffentlichen Exporten oder Analyse-Auswahlfeldern.

**Abnahme:** Ohne Berechtigung sind RI-Seiten, Jobstarts, Dateilinks und Suchergebnisse gesperrt. Mit Berechtigung ist der Ablauf Abruf → Build → Suche bedienbar. Nach Abmeldung funktionieren gespeicherte RI-Links nicht mehr. Öffentliche Recherche und bestehende Datenjobs bestehen ihre Regressionstests.

## Reihenfolge, Dokumentation und Abschluss

1. BI-/RI-Skriptnamen ordnen und alle betroffenen Aufrufer, Tests und Dokumente anpassen.
   Anschließend Schritt 1a ohne RI-Zugang umsetzen: Navigation und öffentliche Einstiege, RI-Platzhalter, vertikales Seitenlayout und Abnahme in eigenen Zwischen-Commits.
2. Plan und Schutzgrenzen abstimmen; Vorprüfung und verbindliche Entscheidungen aus Schritt 2 mit realem Zugang abschließen.
3. Datenvertrag und isolierten Build umsetzen. Danach den Fetcher und seine Authentifizierung anschließen.
4. Suche mit passender Zugriffssicherung bauen. Anschließend die Weboberfläche anbinden.
5. Mit synthetischen Fixtures und später einer kleinen, lokal gehaltenen RI-Stichprobe prüfen; vor Zusammenführung `python -m pytest -m "not integration and not live"`, betroffene Integrationstests und vor einem PR `python -m pytest` ausführen.
6. README, `docs/ist_stand.md`, die betroffenen aktiven Spezialdokumente und `docs/plans/project_tasks.md` bei den jeweiligen funktionalen Änderungen aktualisieren. `VERSION` beim ersten sichtbaren funktionalen Schritt bewusst prüfen.

Der Vorhaben-Branch ist abgeschlossen, wenn Fetch, Datenbank und Suche im geschützten Ratsbereich funktionieren, die Negativtests zur Trennung bestehen und die Betriebsanleitung den Umgang mit Zugang, Sicherung und Wiederherstellung erklärt. Offene Annahmen aus Schritt 2 werden vor produktiver Nutzung entschieden, nicht stillschweigend als erfüllt betrachtet.
