# Plan: Geschützter Ratsbereich für SessionNet `/ri/`

Stand: 10.11.2026. Dieser Plan ist die Grundlage für spätere Teilbranches. Gezielter Proton-Zugangsabruf sowie RI-Anmeldung und RI-Abmeldung sind inzwischen unter WSL und Windows real geprüft. RI-Unterlagendownload, Datenhaltung, Suche und Webzugang sind noch nicht freigeschaltet; eine erste begrenzte HTML-/Metadatenstichprobe und ein RI-/BI-Vergleich wurden durchgeführt. Vertrauliche Ergebnisse bleiben ausschließlich unter dem ignorierten Ordner `tmp/`.

## Fortschritt

Aktuell wird die Einrichtung auf `.env/ri_token.txt`, temporäre CLI-Dateisitzungen und Checks ohne separate Eintragsbindung umgestellt (0.6.0). Der neue Ablauf ist synthetisch geprüft. Der Nutzer bestätigt unter Windows beide Checks einschließlich RI-Abmeldung; die entfernte Proton-Abmeldung bleibt dort unbestätigt. Unter WSL bestätigten die nachfolgenden begrenzten Erkundungsläufe RI- und normale Proton-Abmeldung. Eine breitere Betriebsabnahme steht aus. Bedienung steht ausschließlich in der [RI-Zugangsanleitung](../ri/zugang.md). Die folgenden historischen Abnahmen bis 0.5.76 beziehen sich auf die frühere Keyring-Variante.

Das Proton-Teilpaket ist für die lokale Einrichtung und den manuell gestarteten RI-Zugriffstest unter Windows und WSL abgeschlossen. Neustart-/Ablaufprüfungen, unbeaufsichtigter Betrieb und der bekannte Windows-Proton-Abmeldehinweis sind auf Nutzerwunsch zurückgestellt und nicht abgenommen. Die Anbindung an den RI-Fetcher bleibt Teil dieses Hauptplans. Der abgeschlossene separate Proton-Plan ist entfernt; der maßgebliche Stand und die nächsten Aufgaben werden hier geführt.

Abgehakte Punkte bezeichnen nur den jeweils genannten Umfang. Die dokumentierten realen Zugriffsprüfungen stammen aus den bisherigen Umsetzungspaketen und werden für diese Statuspflege nicht erneut ausgeführt.

- [x] Schritt 1: BI-/RI-Skriptnamen einschließlich Aufrufern, Tests und Dokumentation umgesetzt; über PR #89 übernommen.
- [x] Schritt 1a: Navigation, öffentliche Einstiege, RI-Platzhalter und vertikales Layout einschließlich dokumentierter Tests und Browserabnahme umgesetzt; über PR #90 übernommen.
- [x] Proton-Pass-Teilpaket auf `codex/feature/ri-proton-pass-zugang` abgeschlossen; Einrichtung und manueller RI-Zugriffstest unter Windows und WSL abgenommen (0.5.76).
- [ ] Schritt 2: RI-Aufbau und Dokumentangebot erkunden, Unterschiede zu BI prüfen und benötigten Downloadumfang festlegen; weitere Daten- und Zugriffskontrakte entscheiden. Die Anmeldung und eine erste Metadatenstichprobe sind geprüft; der benötigte Dokumentumfang ist noch nicht festgelegt.
- [x] Proton-Pass-Dokumentation, Befehlsoptionen und Tarifvoraussetzungen geprüft; Zielversion 2.7.0 (`ba80a19`) auf beiden Systemen praktisch getestet.
- [x] Geführte lokale Speicherhilfe für Windows und Linux/WSL implementiert (0.5.69); automatisiert mit simulierten Backends geprüft. Diagnosemodus und Übernahme des GNOME-Steuerpfads sind in 0.5.70 ergänzt. Der reale WSL-Speichertest besteht nach gezieltem Dienstneustart; auch der Windows-Speichertest ist laut Nutzer erfolgreich. Die temporären Proton-CLI-Sitzungen sind inzwischen unter Windows und WSL mit erzwungenem Keyring nutzbar; Neustartabnahme steht aus.
- [x] Skript zur verdeckten lokalen Ablage und zum Ersetzen eines Proton-Pass-Tokens implementiert (0.5.71); Windows- und WSL-Ablage durch erfolgreiche Nutzerläufe bestätigt; feste Eintragsbindung und ausschließlich lesender Zugangsdienst sind inzwischen implementiert und auf beiden Systemen geprüft.
- [x] Eigenständigen Proton-Login-/Logout-Test implementiert (0.5.72); reale Windows-Anmeldung laut Nutzer erfolgreich, normale Abmeldung fehlgeschlagen. Tresorauflistung und gekennzeichnete lokale CLI-Bereinigung sind seit 0.5.73 implementiert; ihre reale Ausführung unter Windows ist durch den Nutzer bestätigt. Unter WSL sind Anmeldung, Tresorauflistung und normale Abmeldung laut Nutzer erfolgreich. Windows-Proton-Abmeldestatus bleibt offen; feste Eintragsbindung und ausschließlich lesender Zugangsdienst sind inzwischen implementiert und real geprüft.
- [x] Proton-Hilfsskripte unter `scripts/setup/` bündeln und Aufrufe, Importe sowie Dokumentation anpassen (0.5.74).
- [x] Zielversion CLI 2.7.0, Windows und WSL sowie manuell gestarteten lokalen Betrieb für die erste Proton-Anbindung festlegen; eigener RI-Tresor mit einem Eintrag, Anwendung ausschließlich lesend.
- [x] Gezielten Lesezugriff und feste Eintragsbindung im Zugangsdienst mit synthetischen Tests implementieren (0.5.75); keine Schreiboperationen an Tresoren, Einträgen oder Tokenrechten.
- [x] Gezielten Passwortabruf sowie RI-Anmeldung, RI-Abmeldung und erneute Zugangssperre unter WSL real bestätigen (0.5.76); keine Unterlagen oder Rohseiten gespeichert.
- [x] Windows-Referenz separat einrichten und echten RI-Test mit Windows-Python abnehmen: RI-Anmeldung, RI-Abmeldung und erneute Zugangssperre bestätigt; bekannter Proton-Abmeldehinweis bleibt.
- [ ] Schritt 3: Getrennte RI-Datenhaltung und Build umsetzen und abnehmen.
- [ ] Schritt 4: Authentifizierten RI-Fetcher umsetzen und mit dem Zugangsdienst verbinden.
- Schritt 5 ist für die erste Ausbaustufe zurückgestellt: keine RI-Volltext-/Vektorindexierung und keine RI-Suchfunktion.
- [ ] Schritt 6: Geschützte RI-Funktionen in die Oberfläche integrieren.
- [ ] Gesamtintegration, reale lokale RI-Stichprobe und Betriebsdokumentation abschließen.

## Ziel und Grenzen

Die vorläufige Richtung ist eine Aufteilung nach Zweck und Sitzungszeitraum: BI als längerfristiger öffentlicher Bestand für vergangene Sitzungen, RI als temporärer lokaler Arbeitsbestand für bevorstehende Sitzungen. Diese Auswahl ist eine Planungsidee und noch keine implementierte Zeitfilter- oder Löschregel. Die Grenze für heutige und laufende Sitzungen sowie ein Nachlauf müssen zuerst festgelegt werden.

Im RI sollen zunächst nur ausgewählte Dokumente lokal liegen und in einer kleinen Datenbank mit Herkunft, Sitzung und Dateipfad verwaltet werden. Diese Datenbank beschreibt ausschließlich tatsächlich vorhandene lokale RI-Dateien. Eine dauerhafte RI-Online-Datenbank und Volltext-/Vektorindexierung sind für die erste Ausbaustufe nicht vorgesehen. Nach einigen Monaten Nutzung wird geprüft, ob längerfristige Aufbewahrung nötig ist.

Unterlagen aus `/ri/` gelten unabhängig vom Datum insgesamt als geschützt. RI-Daten dürfen weder bei Sitzungsende noch bei einem BI-Abgleich automatisch in den öffentlichen Bestand übernommen werden. Die Analysefunktionen sind nicht Teil der ersten Umsetzung.

### Bewertung und offene Regeln des temporären Arbeitsbestands

Die Richtung passt zum Bedarf Sitzungsvorbereitung: weniger lokale Daten, kein zusätzlicher Suchindex und geringerer Pflegeaufwand. Die spätere Erweiterung bleibt möglich, wenn Herkunft, Sitzung und lokale Dateizuordnung von Anfang an gespeichert werden. Ein lokales Dokumentverzeichnis in SQLite ist dabei keine Volltextindexierung.

Vor Umsetzung entscheiden:

- **Zeitgrenze:** Zeitzone `Europe/Berlin`, heutige/laufende Sitzungen, Termine ohne Uhrzeit und abgesagte/verschobene Sitzungen berücksichtigen. Für die Vorbereitung wäre „heute und künftig“ zweckmäßiger als strikt „nach heute“. Das ist ein Vorschlag, noch keine festgelegte Regel.
- **Nachlieferungen:** Ein kurzer RI-Nachlauf nach der Sitzung kann nötig sein, damit spät veröffentlichte Anlagen oder Ergänzungen nicht sofort verschwinden. Nachlauf und Löschfrist sind noch offen. Auch BI-Unterlagen zu vergangenen Sitzungen können später ergänzt werden; BI benötigt deshalb wiederholte Aktualisierung eines jüngeren vergangenen Zeitraums statt nur eines einmaligen Abrufs.
- **Aufbewahrung und Löschung:** Regelmäßige Bereinigung ist das Ziel, nicht eine sofortige automatische Löschung bei Datumswechsel. Zunächst Umfang und betroffene Sitzungen als Vorschau anzeigen; nur die isolierte RI-Wurzel bereinigen. Nach dem Bereinigen muss die lokale RI-Datenbank ausschließlich verbleibende Dateien beschreiben. Temporäre Dateien, Vorschaudaten, Exporte und Sicherungen im Löschkonzept berücksichtigen; eine Sicherung kann gelöschte Daten weiterhin enthalten.
- **Nur im RI vorhandene Unterlagen:** Der Metadatenvergleich zeigt keine einfache Obermenge des BI-Angebots. Aus einer späteren öffentlichen Sitzung folgt nicht, dass alle RI-Dateien im BI nachgeliefert werden. Vor endgültiger Löschfrist Bedarf und gegebenenfalls eine ausdrücklich vorgesehene Aufbewahrungsausnahme prüfen. Eine längere Aufbewahrung wäre eine spätere bewusste Anpassung, kein stiller Standard.
- **Dokumentauswahl:** Einladungen (`EI`) sind laut Nutzer für den RI-Abruf nicht benötigt. Bedarf für Bekanntmachungen, Notizen, Vorlagen, Anlagen, Protokolle und Sammelunterlagen bleibt getrennt zu entscheiden. Gleiche Überschrift oder Dokumentkennung allein beweist weder Inhaltsgleichheit noch öffentliche Freigabe.
- **Verwaltungsausschuss:** Laut Nutzer sind derzeit noch keine Unterlagen als Stichprobe vorhanden; er stuft dieses Gremium als besonders wichtig ein. Sobald Unterlagen verfügbar sind, dort Dokumentgruppen, Kennzeichnungen und Bedarf vor einer allgemeinen Freigabe des Downloadumfangs gezielt prüfen. Andere Gremien ersetzen diese Abnahme nicht; Verfügbarkeit und Bedeutung sind bislang Nutzerangaben, kein vollständiger Portalbefund.

Während der ersten Nutzungsmonate anhand der tatsächlich benötigten Unterlagen entscheiden, ob der kleine temporäre Bestand genügt. Eine Verlängerung der Aufbewahrung erfordert zunächst keinen Suchindex. Aufbewahrungsdauer, Dokumentauswahl und Suche sind getrennte Entscheidungen.

## Bestehende Anknüpfungspunkte

- `src/fetching/sessionnet_client.py` enthält HTTP-Abruf, HTML-Parsing und Dokumentdownload; sein Standardziel ist `/bi/`. Ob RI dieselben HTML- und Dokumentstrukturen verwendet, ist eine offene Annahme.
- `scripts/fetch_bi_session_from_index.py` nutzt die öffentliche Online-Indexdatenbank; `scripts/build_bi_online_index_db.py` baut diesen Index. Der RI-Abruf darf deren Standardpfade nicht verwenden.
- `scripts/build_bi_local_index.py` kann eine Rohdatenwurzel und einen Ausgabe-DB-Pfad erhalten. Die Eignung seiner Scanner- und Pfadlogik für einen isolierten RI-Bestand muss geprüft werden.
- `scripts/build_bi_vector_index.py` baut derzeit den öffentlichen Ratsinfo-Suchindex aus `local_index.sqlite`. Die Suche unter `web/search/` bietet gegenwärtig Ratsinfo und Landkreis als Quellen. Der RI-Bestand wird in der ersten Ausbaustufe nicht an diesen Vektorbuild angeschlossen; eine RI-Suche ist zurückgestellt.
- Die Weboberfläche läuft laut `web/web/settings.py` lokal im Entwicklungsmodus (`DEBUG=True`, feste Entwicklungsschlüssel, keine Benutzeranmeldung). Eine sichtbare Trennung in der Navigation wäre damit noch keine Zugriffssicherung.

## Vorgesehene Aufteilung in Teilbranches

Alle Teilbranches entstehen vom Vorhaben-Branch `codex/feature/ri-ratsbereich` und werden nach Review in diesen zurückgeführt. Konkrete Namen können bei Arbeitsbeginn angepasst werden:

Die Vorbereitung auf `codex/feature/ri-navigation-vorbereitung` (Schritt 1a) ist abgeschlossen und über PR #90 übernommen. Sie benötigte keinen RI-Zugang. Das Zugangspaket auf `codex/feature/ri-proton-pass-zugang` ist mit Version 0.5.76 für die lokale Einrichtung und den manuellen RI-Anmeldetest abgeschlossen. Der separate Proton-Plan ist entfernt; der weitere Ablauf richtet sich nach diesem Hauptplan.

1. `codex/feature/ri-ratsbereich-datenhaltung` – getrennte Pfade, Datenvertrag und Build aus RI-Rohdaten.
2. `codex/feature/ri-ratsbereich-fetch` – authentifizierter Abruf mit wiederverwendetem Parsing und Download.
3. `codex/feature/ri-ratsbereich-web` – geschützte Bedienung für Abruf, Build und Suche.
4. Bei Bedarf ein kurzer Integrationsbranch vom Vorhaben-Branch für Schnittstellenanpassungen und End-to-End-Abnahme.

Die Daten- und Zugriffskontrakte werden vor paralleler Umsetzung festgelegt. Jeder Teilbranch soll einen abgegrenzten, prüfbaren Stand liefern. Änderungen an gemeinsam genutzten Modulen werden auf Rückwirkungen auf `/bi/` getestet.

## 1. Skriptnamen nach Datenbereich ordnen

Umsetzungsstand: Schritt 1 ist auf `codex/refactor/bi-ri-skriptnamen` umgesetzt. Die acht öffentlichen SessionNet-Skripte einschließlich Aufrufern und Dokumentation sind umbenannt; die Namenszuordnung steht im [Changelog](../../CHANGELOG.md#0563--2026-10-30). Das ungenutzte `setup_venv.sh` ist nach bytegleicher Archivierung entfernt. Der vollständige WSL-Testlauf mit `python -m pytest` besteht: 1202 bestanden, einer übersprungen, acht Live-Tests abgewählt. Die vier im vorherigen Windows-Lauf aufgefallenen Plattformannahmen sind in den Tests korrigiert; ein erneuter Windows-Lauf wurde noch nicht bestätigt. Die Zusammenführung in den Vorhaben-Branch ist über PR #89 erfolgt.

Vor der Erweiterung um RI-Funktionen die vorhandenen Skripte inventarisieren und eine einheitliche BI-/RI-Namenskonvention festlegen. Skripte, die heute allgemein benannt sind, aber ausschließlich den öffentlichen Bürgerinformationsbereich (`/bi/`) bearbeiten, sollen dies im Namen ausdrücken, zum Beispiel `fetch_bi_sessions.py`. Neue RI-Skripte erhalten entsprechend Namen wie `fetch_ri_sessions.py`.

Bei einer Umbenennung alle Aufrufer, Tests, Dokumentation und Automatisierungen mit anpassen. Die bestehenden Abläufe müssen danach weiterhin funktionieren. Gemeinsame oder bereichsübergreifende Werkzeuge behalten einen neutralen Namen; die Konvention soll keine künstliche Trennung gemeinsamer Komponenten erzwingen.

**Abnahme:** Für jedes Skript ist erkennbar, ob es BI, RI oder einen gemeinsamen Zweck hat. Alte Namen haben keine unbeabsichtigt verbliebenen Aufrufer; dokumentierte Kommandos und betroffene Tests sind angepasst.

## 1a. Navigation und Seitenaufbau ohne RI-Zugang vorbereiten

Arbeitsbranch: `codex/feature/ri-navigation-vorbereitung`; über PR #90 in den Vorhaben-Branch übernommen. Umgesetzt in Version 0.5.64: Navigation und öffentliche Einstiege, RI-Platzhalter sowie vertikale Hauptbereiche. Navigation und Platzhalter wurden gemeinsam im ersten Implementierungscommit gesichert; Layout und Browserkorrekturen folgten in eigenen Zwischen-Commits. Dieser Zwischenschritt folgt auf die zusammengeführten BI-Skriptumbenennungen und wird vor der RI-Vorprüfung umgesetzt. Die Nummern der weiteren Schritte bleiben erhalten.

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

**Zugang bereits geprüft:** Der manuelle Anmelde-/Abmeldeablauf einschließlich erneuter Zugangssperre ist unter Windows und WSL bestätigt. Neustart-/Ablaufprüfungen und unbeaufsichtigter Betrieb sind zurückgestellt. Eine erste HTML-/Metadatenstichprobe ist durchgeführt; sie ersetzt keine vollständige Struktur- oder Dokumentbedarfsprüfung.

### Nächster Schritt: RI-Aufbau und tatsächlichen Downloadbedarf erkunden

**Status: erste begrenzte Erkundung und konkreter RI-/BI-Vergleich durchgeführt; private Ergebnisse ausschließlich unter `tmp/`.** Gemeinsame Tabellenkennungen sind belegt, die direkt sichtbaren Dokumentzusammenstellungen unterscheiden sich. Der Verwaltungsausschuss bleibt eine noch fehlende vorrangige Stichprobe. Ein vollständiger Dokumentdownload ist kein vorgegebenes Ziel.

- [ ] Bei der weiteren Erkundung die Navigation, Sitzungsübersichten, Sitzungsdetails, Tagesordnungspunkte und gegebenenfalls Vorlagenansichten erfassen; Unterschiede zu `/bi/` konkret dokumentieren.
- [ ] An einer kleinen ausgewählten Stichprobe zunächst ausschließlich HTML-Struktur und sichtbare Dokumentmetadaten prüfen. Keine automatische Verfolgung von Datei-/PDF-Links und keinen vollständigen Crawl starten.
- [ ] Tatsächlich vorhandene Dokumentarten, Einzeldateien und Sammelunterlagen, Anlagen, Kennzeichnungen und Mehrfachverlinkungen inventarisieren. Keine Dokumentkategorien oder Parsergleichheit mit BI voraussetzen.
- [ ] Für die Recherche festlegen, welche Dokumentarten benötigt, optional oder nicht benötigt sind. Mögliche BI-Dubletten und redundante Sammel-/Einzeldateien berücksichtigen; ein RI-Dokument wird dadurch nicht öffentlich freigegeben.
- [ ] Daraus Regeln für einen gezielten Abruf ableiten: auswählbare Sitzungen/Zeiträume und Dokumentarten, Umgang mit Anlagen sowie Duplikaten. Einen späteren Vorschaumodus ohne Dateiabruf vorsehen, bevor Downloadlogik umgesetzt wird.
- [ ] Das Ergebnis als allgemeine Strukturübersicht und begründete Auswahltabelle im Plan festhalten. Vertrauliche Titel, Inhalte, Cookies und vollständige geschützte URLs nicht in Git übernehmen; Parser-Fixtures synthetisch erstellen.

**Abnahme:** Unterschiede zu BI und die tatsächlich vorhandenen Dokumentarten sind belegt; für jede Kategorie ist der vorgesehene Abrufumfang begründet. Erst danach werden Parserwiederverwendung und Downloadstrategie festgelegt. Einzelne Dateiproben wären ein späterer begrenzter Schritt und sind nicht Teil der HTML-/Metadatenerkundung.

### Weitere verbindliche Entscheidungen

Herkunft und Zugriffsrechte vor automatisiertem Abruf klären. Weicht die Struktur ab, wird der RI-spezifische Parser ergänzt, statt den öffentlichen Parser auf Vermutung hin umzubauen.

Vor Implementierung verbindlich festlegen und dokumentieren:

- Betriebsmodell: nur lokal für eine Person oder Zugriff für mehrere Personen/Geräte. Davon hängen Web-Authentifizierung, Berechtigungen und der Speicherort ab.
- Sicherer Speicherort und Backup-Konzept für RI-Daten. Eine zweite SQLite-Datei unter demselben allgemein zugänglichen Datenordner ist für sich allein keine Zugriffssperre.
- Erste Ausbaustufe ohne Qdrant-/Volltextindex für RI. Zugriffsschutz auf lokale Dateien und deren Datenbank bleibt erforderlich; eine spätere Suche wäre neu zu entscheiden.
- Verfahren für Kennzeichnungen: „Ö“, „N“, „unklar“ und widersprüchliche Angaben; bis zur geprüften Einstufung bleibt jedes RI-Dokument intern.

## 3. Getrennte Datenhaltung und Build

Eine eigene, nicht versionierte RI-Dateiwurzel und eine kleine SQLite-Datenbank zur Verwaltung der tatsächlich lokal vorhandenen Dokumente definieren. Darin Sitzung, Termin, Gremium, Dokumentart, Herkunft und lokalen Dateipfad erfassen. Eine gesonderte dauerhafte RI-Online-Datenbank und ein Volltext-/Vektorindex sind für die erste Ausbaustufe nicht erforderlich. Die endgültigen Dateipfade und Schutzrechte werden vor Datenabruf festgelegt. Der öffentliche Builder darf die RI-Wurzel nicht mitscannen.

Dokumentidentitäten müssen Quelle, Sitzungs-ID und dokumenteigene Referenz unterscheiden. Gleiche Sitzungsnummern oder Titel dürfen BI und RI nicht verbinden. Lokale Pfade bleiben innerhalb der erlaubten RI-Wurzel. Aufbewahrte Rohdateien werden nicht nachträglich bearbeitet; die geplante Bestandsbereinigung ist ein eigener, expliziter Vorgang mit konsistenter Datenbankbereinigung.

Öffentlichkeitskennzeichen sind Metadaten, keine Freigabe zum Verschieben in BI. Fehlende, mehrdeutige oder widersprüchliche Kennzeichen ergeben `unklar`. Der Datenbankabgleich erfasst nur tatsächlich vorhandene lokale RI-Dateien und entfernt verwaiste Verweise; eine Online-Stichprobe darf nicht als lokaler Dokumentbestand erscheinen.

**Abnahme:** Die Datenbank beschreibt genau den lokalen RI-Dateibestand. Ein erneuter Aufbau erzeugt keine Duplikate; nach einer vorgesehenen Bereinigung bleiben keine verwaisten Dokumentverweise. Öffentliche Builds erhalten keine RI-Daten. Zeitfilter, Nachlauf und Bereinigung werden vor automatischem Betrieb gesondert geprüft.

## 4. RI-Fetcher mit Anmeldung

### Abgeschlossene Zugangseinrichtung

- Implementierung: `src/config/ri_proton.py` für den lesenden Zugang zum einzigen freigegebenen Login und `src/fetching/ri_login.py` für den begrenzten RI-Anmeldetest. Hilfsskripte und Aufrufe stehen in der [RI-Zugangsanleitung](../ri/zugang.md#gezielten-zugriff-und-ri-anmeldung-prüfen).
- Der RI-Tresor enthält genau einen aktiven Login-Eintrag. Zusätzliche freigegebene Tresore oder aktive Einträge führen zum Abbruch. Ab 0.6.0 werden keine alten Referenzen mehr abgeglichen; bei jedem Lauf wird der einzige aktuell freigegebene Login verwendet. Eine vorhandene Sicherung in einem anderen Tresor wird nicht verwendet.
- Der Token liegt ab 0.6.0 unverschlüsselt in `.env/ri_token.txt`; CLI-Sitzungsdaten und Dateischlüssel bleiben in einem temporären Verzeichnis. Eine separate Referenzdatei entfällt. RI-Benutzername und Passwort werden nicht ausgegeben oder durch die Anwendung in Klartextdateien abgelegt; HTTP-Cookies und geschütztes HTML bleiben flüchtig. Die Anwendung erlaubt nur die vorgesehenen Leseoperationen sowie Login/Logout und lokale Einrichtungs-/Sitzungsverwaltung; serverseitige Schreibrechte des Tokens sind unbekannt.
- Validierung des Implementierungsstands: 47 gezielte Tests je Zielsystem, sechs betroffene Integrationstests und 690 reguläre Tests bestanden. Echte RI-Anmeldung, RI-Abmeldung und erneute Zugangssperre auf beiden Systemen bestätigt; keine Sitzungsunterlagen heruntergeladen. In der aktuellen Dokumentationsänderung werden diese Live-Tests nicht wiederholt.

### Spätere Anbindung an den Fetcher

Historische Abnahme bis 0.5.76 (vor dem Dateiumbau): Die Bereitstellung der Zugangsdaten ist auf `codex/feature/ri-proton-pass-zugang` implementiert: ein Token mit Freigabe ausschließlich für den eigenen RI-Tresor mit einem Eintrag, geschützte lokale Token- und Sitzungsablage sowie schrittweise Tests. Die erste Ausbaustufe verwendet CLI 2.7.0 unter Windows und WSL bei manuell gestarteten lokalen Abrufen; Ablage und Proton-Anmeldung sind dort geprüft. Der Zugangsdienst wird auf lesende Befehle und den fest konfigurierten RI-Eintrag begrenzt; serverseitige Schreibrechte des Tokens werden nicht als eingeschränkt behauptet. Gezielter Passwortabruf sowie RI-Anmeldung und RI-Abmeldung sind mit dem neuen Test unter WSL bestätigt. Auch die Windows-Referenz und der Windows-RI-Test sind real bestätigt; dabei bleibt lediglich der bekannte Hinweis zur nachfolgenden Proton-Abmeldung. Neustartverhalten und echte Fetch-/Daten-/Such-/Webanbindung stehen noch aus.

Den Abrufumfang erst nach der Struktur- und Bedarfsprüfung aus Schritt 2 festlegen; keinen pauschalen Download aller RI-Dateien implementieren. Ein eigenes CLI-Skript für RI-Sitzungsübersicht und gezielte Sitzungsdownloads vorsehen. Wiederverwendbare Komponenten aus `SessionNetClient` nutzen, sobald HTML- und URL-Parität bestätigt ist. Der authentifizierte Client braucht eine klar abgegrenzte Anmeldung, eine zeitlich begrenzte HTTP-Sitzung und einen eindeutigen Fehler bei abgelaufener Anmeldung. Eine Login-Seite darf nie als Sitzungsdetail oder PDF gespeichert werden.

Zugangsdaten nicht als CLI-Argument oder im Quellcode hinterlegen; der Zugangsdienst liest den Token aus der lokalen, Git-ignorierten Datei und die Zugangsfelder aus dem einzigen freigegebenen Proton-Login. Temporäre CLI-Dateisitzungen ersetzen die OS-Schlüsselspeicher für diesen Ablauf. Der Sicherungstresor wird nicht angesprochen; an Tresoren, Einträgen und Tokenrechten werden keine Schreiboperationen durchgeführt. Passwort, Session-Cookies, Token und vollständige geschützte URLs aus Logs und Fehlermeldungen heraushalten. Umleitungen und Dokumentlinks auf erlaubte RI-Hosts und Pfade begrenzen; keine Credentials an fremde Hosts senden. Bestehende Grenzen für Downloadgröße, Rate-Limit, Retry und sichere Dateipfade gelten auch hier.

Fetch-Ergebnisse enthalten die Herkunft `ri` und werden ausschließlich in der RI-Rohdatenwurzel abgelegt. Inkrementelle Abrufe und explizite Aktualisierung folgen dem bestehenden Verhalten, sofern es mit dem angemeldeten Portal vereinbar ist.

**Abnahme:** Synthetische Tests prüfen erfolgreiche Anmeldung, Ablauf/Fehler, unerwartete Weiterleitung, fremden Dokumenthost, doppelte Abrufe und fehlende Dokumente. Der echte Ablauf wird erst mit Zugang und einer kleinen lokalen Probe verifiziert. Es gibt keine Netzwerktests mit produktiven Geheimnissen in der regulären Testsuite.

## 5. Separate Suche (zurückgestellt)

Die erste RI-Ausbaustufe benötigt keine Volltextindexierung, Embeddings, Qdrant-Collection oder eigene Suchfunktion. Die kleine lokale Dokumentdatenbank dient der Bestandsverwaltung und Dateizuordnung. Bestehende RI-Suchplatzhalter aktivieren keine Indexierung und sind keine Abnahmebedingung dieses Umfangs. Eine spätere Suche wird nur bei tatsächlichem Bedarf nach der Nutzungsphase neu geplant.

## 6. Einbindung in die Oberfläche

Die [Navigationsübersicht mit Ist- und Ziel-Diagramm](navigation.md) konkretisiert diese Phase. Schritt 1a zieht die Menüstruktur, RI-Platzhalter und das vertikale Seitenlayout vor. Hier werden die Platzhalter durch geschützte Funktionen ersetzt: ein gemeinsamer Sitzungskalender mit verfügbaren BI-/RI-Einstiegen; Bürgerinformation mit bestehender Suche; geschützter Ratsbereich zunächst mit kommenden Sitzungen, lokal vorhandenen Dokumenten und Datenpflege. Eine RI-Suche bleibt zurückgestellt. Interne Termine, Links und Metadaten im gemeinsamen Kalender benötigen die entsprechende Berechtigung.

Einen deutlich gekennzeichneten Ratsbereich für ausgewählte kommende Sitzungen, lokale Dokumente und kontrollierte Bestandsbereinigung schaffen. Quelle und Schutzstatus bleiben auf jeder RI-Seite sichtbar. Start von RI-Jobs und Zugriff auf RI-Dateien werden serverseitig geschützt; ein bloßer Navigationsschalter oder eine lokale Browseransicht genügen nicht. Die bestehende Django-Konfiguration muss vor einer Nutzung mit RI-Daten hinsichtlich Debug-Modus, Secret-Key, Benutzeranmeldung, Sitzungen und Dateiauslieferung angepasst werden.

Die Jobliste darf keine RI-Titel, URLs, Dokumenttexte oder Zugangsdaten in öffentlich sichtbaren Statusmeldungen ausgeben. Datei-Downloads prüfen Pfad und Berechtigung bei jedem Aufruf. RI-Daten erscheinen weder in öffentlichen Dashboard-Zahlen noch in öffentlichen Exporten oder Analyse-Auswahlfeldern.

**Abnahme:** Ohne Berechtigung sind RI-Seiten, Jobstarts, Dateilinks und Suchergebnisse gesperrt. Mit Berechtigung sind gezielter Abruf, lokaler Dokumentbestand und die freigegebene Bestandsbereinigung bedienbar. Nach Abmeldung funktionieren gespeicherte RI-Links nicht mehr. Öffentliche Recherche und bestehende Datenjobs bestehen ihre Regressionstests.

## Reihenfolge, Dokumentation und Abschluss

1. **Erledigt:** BI-/RI-Skriptnamen geordnet und Schritt 1a ohne RI-Zugang umgesetzt: Navigation und öffentliche Einstiege, RI-Platzhalter, vertikales Seitenlayout und dokumentierte Abnahme. Beide Pakete sind in den Vorhaben-Branch übernommen.
2. **Zugang und erste Metadatenstichprobe bestätigt:** Als Nächstes den RI-Aufbau und tatsächlichen Dokumentbedarf nach Schritt 2 untersuchen, Unterschiede zu BI belegen und einen gezielten Downloadumfang festlegen. Insbesondere eine Stichprobe des Verwaltungsausschusses fehlt noch. Weitere Daten- und Zugriffskontrakte anschließend verbindlich entscheiden.
3. Datenvertrag und isolierten Build umsetzen. Danach den Fetcher und seine Authentifizierung anschließen.
4. Zeitfilter, Nachlauf und Bestandsbereinigung prüfen und die geschützte Weboberfläche anbinden. RI-Suche ist für die erste Ausbaustufe nicht vorgesehen.
5. Mit synthetischen Fixtures und später einer kleinen, lokal gehaltenen RI-Stichprobe prüfen; vor Zusammenführung `python -m pytest -m "not integration and not live"`, betroffene Integrationstests und vor einem PR `python -m pytest` ausführen.
6. Die betroffenen Fachseiten aktualisieren; Wegweiser, Ist-Stand und Aufgaben bei geändertem Umfang nachziehen. Die Version pro zusammenhängendem Änderungspaket gemäß [Versionsregeln](../../AGENTS.md#versionspflege) prüfen und gemeinsam mit dem Changelog pflegen. Vollständige Testsätze aus Schritt 5 führt der Nutzer aus; Agenten führen nur gezielte, schnelle Tests aus.

Der Vorhaben-Branch ist abgeschlossen, wenn gezielter Fetch, lokaler Dokumentbestand und die freigegebene Bestandsbereinigung im geschützten Ratsbereich funktionieren, die Negativtests zur Trennung bestehen und die Betriebsanleitung den Umgang mit Zugang, Sicherung und Wiederherstellung erklärt. Offene Annahmen aus Schritt 2 werden vor produktiver Nutzung entschieden, nicht stillschweigend als erfüllt betrachtet.
