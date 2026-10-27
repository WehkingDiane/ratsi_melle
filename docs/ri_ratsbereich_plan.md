# Plan: Geschützter Ratsbereich für SessionNet `/ri/`

Stand: 27.10.2026. Dieser Plan ist die Grundlage für spätere Teilbranches. Er beschreibt noch keine freigeschaltete RI-Anbindung; Zugangsdaten und ein Beispiel der angemeldeten Seiten liegen derzeit nicht vor.

## Ziel und Grenzen

Der bestehende Ablauf „herunterladen → lokale Datenbank bauen → suchen“ soll auch für Unterlagen aus dem Ratsinformationssystem (RI) funktionieren. Der Bürgerinformationsbereich (`/bi/`) bleibt die Quelle des öffentlichen Datenbestands, auch für kommende Sitzungen. Ein Sitzungsdatum allein entscheidet nicht über die Vertraulichkeit: Unterlagen aus `/ri/` gelten zunächst insgesamt als geschützt, auch wenn eine PDF mit „Ö“ gekennzeichnet ist oder die Sitzung bereits stattgefunden hat.

RI-Rohdaten, Datenbanken, Suchindex, Protokolle und eventuelle Exporte dürfen nicht unbemerkt in öffentliche Pfade oder Abläufe gelangen. Die Analysefunktionen sind **nicht** Teil der ersten Umsetzung; RI-Inhalte werden ihnen auch nicht als auswählbare Quelle angeboten.

## Bestehende Anknüpfungspunkte

- `src/fetching/sessionnet_client.py` enthält HTTP-Abruf, HTML-Parsing und Dokumentdownload; sein Standardziel ist `/bi/`. Ob RI dieselben HTML- und Dokumentstrukturen verwendet, ist eine offene Annahme.
- `scripts/fetch_session_from_index.py` nutzt die öffentliche Online-Indexdatenbank; `scripts/build_online_index_db.py` baut diesen Index. Der RI-Abruf darf deren Standardpfade nicht verwenden.
- `scripts/build_local_index.py` kann eine Rohdatenwurzel und einen Ausgabe-DB-Pfad erhalten. Die Eignung seiner Scanner- und Pfadlogik für einen isolierten RI-Bestand muss geprüft werden.
- `scripts/build_vector_index.py` baut derzeit den öffentlichen Ratsinfo-Suchindex aus `local_index.sqlite`. Die Suche unter `web/search/` bietet gegenwärtig Ratsinfo und Landkreis als Quellen. Eine eigene RI-Collection und eindeutige Quellenwahl sind nötig.
- Die Weboberfläche läuft laut `web/web/settings.py` lokal im Entwicklungsmodus (`DEBUG=True`, feste Entwicklungsschlüssel, keine Benutzeranmeldung). Eine sichtbare Trennung in der Navigation wäre damit noch keine Zugriffssicherung.

## Vorgesehene Aufteilung in Teilbranches

Alle Teilbranches entstehen vom Vorhaben-Branch `codex/feature/ri-ratsbereich` und werden nach Review in diesen zurückgeführt. Konkrete Namen können bei Arbeitsbeginn angepasst werden:

1. `codex/feature/ri-ratsbereich-datenhaltung` – getrennte Pfade, Datenvertrag und Build aus RI-Rohdaten.
2. `codex/feature/ri-ratsbereich-fetch` – authentifizierter Abruf mit wiederverwendetem Parsing und Download.
3. `codex/feature/ri-ratsbereich-suche` – eigene Vektor-Collection, Build und Suchservice.
4. `codex/feature/ri-ratsbereich-web` – geschützte Bedienung für Abruf, Build und Suche.
5. Bei Bedarf ein kurzer Integrationsbranch vom Vorhaben-Branch für Schnittstellenanpassungen und End-to-End-Abnahme.

Die Daten- und Zugriffskontrakte werden vor paralleler Umsetzung festgelegt. Jeder Teilbranch soll einen abgegrenzten, prüfbaren Stand liefern. Änderungen an gemeinsam genutzten Modulen werden auf Rückwirkungen auf `/bi/` getestet.

## 0. Vorprüfung und verbindliche Entscheidungen

**Ohne RI-Zugang möglich:** Aufrufketten und Pfadannahmen erfassen; Daten- und Sicherheitsgrenzen festlegen; Tests mit synthetischen Seiten vorbereiten. Keine echten Zugangsdaten, Cookies oder vertraulichen Beispieldokumente ins Repository übernehmen.

**Nach Erhalt des Zugangs:** Anmeldeablauf prüfen (Formular, Umleitungen, eventuelle zusätzliche Faktoren, Ablauf der Sitzung), eine freigegebene Beispiel-Sitzung nur lokal untersuchen und HTML-, URL-, PDF- und Kennzeichnungsstruktur mit `/bi/` vergleichen. Herkunft und Zugriffsrechte vor automatisiertem Abruf klären. Weicht die Struktur ab, wird der RI-spezifische Parser ergänzt, statt den öffentlichen Parser auf Vermutung hin umzubauen.

Vor Implementierung verbindlich festlegen und dokumentieren:

- Betriebsmodell: nur lokal für eine Person oder Zugriff für mehrere Personen/Geräte. Davon hängen Web-Authentifizierung, Berechtigungen und der Speicherort ab.
- Sicherer Speicherort und Backup-Konzept für RI-Daten. Eine zweite SQLite-Datei unter demselben allgemein zugänglichen Datenordner ist für sich allein keine Zugriffssperre.
- Ob ein lokaler Qdrant-Server die RI-Collection zuverlässig nur für berechtigte Nutzer zugänglich macht. Falls nicht, RI-Suche erst mit einer passenden isolierten Instanz oder Zugriffssicherung aktivieren.
- Verfahren für Kennzeichnungen: „Ö“, „N“, „unklar“ und widersprüchliche Angaben; bis zur geprüften Einstufung bleibt jedes RI-Dokument intern.

## 1. Getrennte Datenhaltung und Build

Eine eigene, nicht versionierte RI-Rohdatenwurzel und eigene SQLite-Dateien für Sitzungsübersicht und lokalen Dokumentindex definieren. Vorgeschlagene Namen sind `data/raw/ri/`, `data/db/ri_online_index.sqlite` und `data/db/ri_local_index.sqlite`; bei Bedarf liegen sie außerhalb des Repositorys an einem zugriffsgeschützten Ort. Die endgültigen Pfade werden zentral konfiguriert. Der öffentliche Builder darf die RI-Wurzel nicht mitscannen, auch wenn sie innerhalb von `data/raw/` liegt.

Für die Herkunft jedes Datensatzes eine feste Quellenkennung (`bi` oder `ri`) verwenden. Dokumentidentitäten sollen Quelle, Sitzungs-ID und dokumenteigene URL/ID einbeziehen; gleiche Sitzungsnummern oder Titel dürfen die Bestände nicht verbinden. Lokale Dokumentpfade müssen innerhalb der jeweils erlaubten Rohdatenwurzel aufgelöst werden. Einmal abgerufene Rohdateien bleiben unverändert; Builds erzeugen nur abgeleitete Daten.

Öffentlichkeitskennzeichen als Metadatum mit Erkennungsquelle und Status speichern. Die Erkennung aus PDF-Kopf oder HTML ist eine Orientierung, keine Freigabe zum Verschieben. Für fehlende, mehrdeutige oder technisch nicht lesbare Kennzeichen gilt `unklar`. Ein späterer Abgleich mit `/bi/` darf nur Metadaten verknüpfen, keine RI-Datei in öffentliche Indizes kopieren.

**Abnahme:** Ein RI-Build mit Testdaten schreibt ausschließlich in RI-Zielpfade. Ein öffentlicher Neuaufbau nimmt keine RI-Sitzung, PDF oder Textpassage auf. Wiederholte Builds erzeugen keine Duplikate und verändern keine Rohdaten.

## 2. RI-Fetcher mit Anmeldung

Ein eigenes CLI-Skript für RI-Sitzungsübersicht und gezielte Sitzungsdownloads vorsehen. Wiederverwendbare Komponenten aus `SessionNetClient` nutzen, sobald HTML- und URL-Parität bestätigt ist. Der authentifizierte Client braucht eine klar abgegrenzte Anmeldung, eine zeitlich begrenzte HTTP-Sitzung und einen eindeutigen Fehler bei abgelaufener Anmeldung. Eine Login-Seite darf nie als Sitzungsdetail oder PDF gespeichert werden.

Zugangsdaten nicht als CLI-Argument oder im Quellcode hinterlegen; ein geeigneter lokaler Secret-Speicher oder eine geschützte Eingabe wird nach Prüfung des echten Loginablaufs gewählt. Passwort, Session-Cookies, Token und vollständige geschützte URLs aus Logs und Fehlermeldungen heraushalten. Umleitungen und Dokumentlinks auf erlaubte RI-Hosts und Pfade begrenzen; keine Credentials an fremde Hosts senden. Bestehende Grenzen für Downloadgröße, Rate-Limit, Retry und sichere Dateipfade gelten auch hier.

Fetch-Ergebnisse enthalten die Herkunft `ri` und werden ausschließlich in der RI-Rohdatenwurzel abgelegt. Inkrementelle Abrufe und explizite Aktualisierung folgen dem bestehenden Verhalten, sofern es mit dem angemeldeten Portal vereinbar ist.

**Abnahme:** Synthetische Tests prüfen erfolgreiche Anmeldung, Ablauf/Fehler, unerwartete Weiterleitung, fremden Dokumenthost, doppelte Abrufe und fehlende Dokumente. Der echte Ablauf wird erst mit Zugang und einer kleinen lokalen Probe verifiziert. Es gibt keine Netzwerktests mit produktiven Geheimnissen in der regulären Testsuite.

## 3. Separate Suche

Eine eigene RI-Collection und einen expliziten RI-Vektorbuild vorsehen. Die bestehende Ratsinfo-Collection (`ratsi_passages`) und die Landkreis-Collection bleiben unberührt. Der Suchdienst muss Quelle und zugehörige Pfadwurzel serverseitig festlegen; ein URL-Parameter darf keine beliebige Collection oder Dateiwurzel wählen. Ergebnislinks für RI-Dateien benötigen dieselbe Zugriffskontrolle wie die Suchseite.

Die Freigabe des RI-Index hängt von der Betriebsentscheidung aus Phase 0 ab. Bei ungeschütztem gemeinsamem Qdrant-Server wird die RI-Collection nicht dort aufgebaut; für die erste Version kann stattdessen eine lokal isolierte Suchinstanz genutzt werden. Die Oberfläche zeigt den Status „RI-Suche noch nicht eingerichtet“, bis Index und Zugriff geprüft sind.

**Abnahme:** Öffentliche Suchen liefern keine RI-Treffer; RI-Suchen liefern nur RI-Treffer. Ein versehentliches Schreiben in öffentliche Collections wird durch Tests und Build-Vorprüfung verhindert. Fehlende Collections und abgelaufene Zugriffssitzungen führen zu klaren, inhaltsfreien Fehlermeldungen.

## 4. Einbindung in die Oberfläche

Einen deutlich gekennzeichneten Ratsbereich für „Sitzungen abrufen“, „Datenbank bauen“ und „Suchen“ schaffen. Quelle und Schutzstatus bleiben auf jeder RI-Seite sichtbar. Start von RI-Jobs und Zugriff auf RI-Dateien werden serverseitig geschützt; ein bloßer Navigationsschalter oder eine lokale Browseransicht genügen nicht. Die bestehende Django-Konfiguration muss vor einer Nutzung mit RI-Daten hinsichtlich Debug-Modus, Secret-Key, Benutzeranmeldung, Sitzungen und Dateiauslieferung angepasst werden.

Die Jobliste darf keine RI-Titel, URLs, Dokumenttexte oder Zugangsdaten in öffentlich sichtbaren Statusmeldungen ausgeben. Datei-Downloads prüfen Pfad und Berechtigung bei jedem Aufruf. RI-Daten erscheinen weder in öffentlichen Dashboard-Zahlen noch in öffentlichen Exporten oder Analyse-Auswahlfeldern.

**Abnahme:** Ohne Berechtigung sind RI-Seiten, Jobstarts, Dateilinks und Suchergebnisse gesperrt. Mit Berechtigung ist der Ablauf Abruf → Build → Suche bedienbar. Nach Abmeldung funktionieren gespeicherte RI-Links nicht mehr. Öffentliche Recherche und bestehende Datenjobs bestehen ihre Regressionstests.

## Reihenfolge, Dokumentation und Abschluss

1. Plan und Schutzgrenzen abstimmen; Phase 0 mit realem Zugang abschließen.
2. Datenvertrag und isolierten Build umsetzen. Danach den Fetcher und seine Authentifizierung anschließen.
3. Suche mit passender Zugriffssicherung bauen. Anschließend die Weboberfläche anbinden.
4. Mit synthetischen Fixtures und später einer kleinen, lokal gehaltenen RI-Stichprobe prüfen; vor Zusammenführung `python -m pytest -m "not integration and not live"`, betroffene Integrationstests und vor einem PR `python -m pytest` ausführen.
5. README, `docs/ist_stand.md`, die betroffenen aktiven Spezialdokumente und `docs/project_tasks.md` bei den jeweiligen funktionalen Änderungen aktualisieren. `VERSION` beim ersten sichtbaren funktionalen Schritt bewusst prüfen.

Der Vorhaben-Branch ist abgeschlossen, wenn Fetch, Datenbank und Suche im geschützten Ratsbereich funktionieren, die Negativtests zur Trennung bestehen und die Betriebsanleitung den Umgang mit Zugang, Sicherung und Wiederherstellung erklärt. Offene Annahmen aus Phase 0 werden vor produktiver Nutzung entschieden, nicht stillschweigend als erfüllt betrachtet.
