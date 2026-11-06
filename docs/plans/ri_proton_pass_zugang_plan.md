# Plan: RI-Zugang sicher über Proton Pass beziehen

Stand: 06.11.2026. **Status: abgeschlossen im vereinbarten Umfang – lokale Proton-Einrichtung und manueller RI-Zugriffstest unter Windows und WSL.** Weitergehende Prüfungen und die Fetcher-Anbindung sind ausdrücklich zurückgestellt; sie wurden nicht als erledigt abgenommen.

Vorhaben-Branch: `codex/feature/ri-ratsbereich`.
Arbeitsbranch dieses Teilpakets: `codex/feature/ri-proton-pass-zugang`.
Übergeordneter Plan: [Geschützter Ratsbereich](ri_ratsbereich_plan.md), insbesondere Schritte 2 und 4.

## Abschluss und Abgrenzung

Die Einrichtung ist für den vereinbarten manuell gestarteten lokalen Betrieb abgeschlossen:

- [x] Proton Pass CLI 2.7.0 und geschützte getrennte Tokenablage unter Windows und WSL eingerichtet.
- [x] Hilfsskripte unter `scripts/setup/` bereitgestellt und Bedienung dokumentiert.
- [x] Einen festen RI-Eintrag im eigenen Tresor gebunden; Anwendung auf die vorgesehenen Lesebefehle begrenzt.
- [x] Gezielten Zugangsfeldabruf sowie echte RI-Anmeldung, RI-Abmeldung und erneute Zugangssperre auf beiden Systemen bestätigt.
- [x] 47 gezielte Tests auf beiden Systemen, sechs betroffene WSL-Integrationstests und 690 reguläre Tests erfolgreich ausgeführt; Dokumentation und Planstatus aktualisiert.

Der Nutzer möchte die weiteren Arbeiten jetzt nicht durchführen. Neustart-/Ablaufprüfungen, weitergehende Betriebsdokumentation und die Untersuchung des bekannten Windows-Proton-Abmeldehinweises sind deshalb zurückgestellt. Unbeaufsichtigter Betrieb ist nicht abgenommen. Die spätere Anbindung an den RI-Fetcher gehört zu Schritt 4 des [RI-Hauptplans](ri_ratsbereich_plan.md), nicht zum Abschluss dieser Einrichtung. Es wurden noch keine RI-Unterlagen abgerufen oder RI-Datenbanken, Suchindizes oder Webfunktionen freigeschaltet.

Nachfolgende abgehakte Punkte dokumentieren die erledigte Umsetzung. Mit **Zurückgestellt** bezeichnete Punkte bleiben nicht umgesetzt beziehungsweise nicht geprüft und sind keine offenen Arbeitsschritte dieses abgeschlossenen Teilpakets. Historische Prüfergebnisse beschreiben frühere Zwischenstände; maßgeblich ist die obige Abschlussabnahme. Der unbekannte serverseitige Schreibumfang des Tokens wird nicht als eingeschränkt behauptet.

## Ziel und Schutzgrenzen

Der künftige RI-Fetcher soll Benutzername und Passwort bei Bedarf aus einem einzelnen Proton-Pass-Eintrag beziehen. Weder RI-Passwort noch Proton-Zugriffstoken werden als Klartext in `.env`, Konfiguration, Quellcode, Kommandozeilenargumenten, Logs oder temporären Dateien abgelegt. Nicht geheime Referenzen wie Eintrags-ID und CLI-Pfad dürfen konfiguriert werden.

Festgelegt ist ein eigener RI-Tresor mit ausschließlich dem einen benötigten Zugang; der PAT erhält nur Zugriff auf diesen Tresor. Der Nutzer bestätigt eine Sicherung in einem anderen Tresor. Dieser Sicherungstresor wird von der Anwendung weder angesprochen noch freigegeben. Die bestehende Weboberfläche erlaubt dem Nutzer nur die Tresorauswahl, keine Rollenwahl. Die tatsächlichen Schreibrechte des Tokens bleiben deshalb ungeprüft; eine serverseitige `viewer`- oder Eintragsbeschränkung wird nicht als vorhanden behauptet.

Verbindlich für den Anwendungscode: ausschließlich lesender Zugriff auf den vorgesehenen RI-Eintrag und die für seine Identifikation nötigen Metadaten. Keine Befehle zum Erstellen, Ändern, Verschieben, Teilen, Löschen oder Verwalten von Tresoren/Einträgen und Tokenrechten; keine Schreibprobe gegen echte Einträge. Zulässig bleiben die ausdrücklich vorgesehenen lokalen Tokenablagen, Login/Logout und das Entfernen eigener temporärer Sitzungsdaten. Der künftige Zugangsdienst verwendet eine feste Liste erlaubter Leseoperationen und fest konfigurierte Tresor-/Eintragsreferenzen, keine frei übergebenen CLI-Befehle.

Diese Begrenzung gilt für unsere Anwendung, nicht als technische Einschränkung des Tokens außerhalb der Anwendung. Wird später ein weiterer Eintrag in den freigegebenen Tresor gelegt, erweitert sich dessen potenzieller Zugriff. Die Anwendung darf keine vollständige persönliche Proton-Sitzung verwenden. Eine zusätzliche Eintrags-/Rollenfreigabe über die CLI ist eine optionale spätere Härtung und keine Voraussetzung für die vereinbarte erste Ausbaustufe.

Der Token ist selbst ein Geheimnis und braucht einen geeigneten Betriebssystemspeicher. Die CLI muss auch ihre lokalen Sitzungsdaten mit einem Schlüssel aus dem Betriebssystem-Keyring schützen. Ein Dateibackend mit daneben liegendem Klartextschlüssel oder ein dauerhaft in einer Umgebungsdatei gespeicherter Schlüssel erfüllt das Ziel nicht. Für eine Anmeldung nötige Umgebungswerte dürfen allenfalls kurzzeitig und gezielt an den CLI-Unterprozess übergeben werden; sie werden nicht in der globalen Prozessumgebung oder Shell-Historie hinterlegt.

Zur RI-Anmeldung muss das Passwort kurzzeitig entschlüsselt im Prozess verfügbar sein. Diese Lösung schützt die Ablage und begrenzt den Proton-Zugriff; sie ersetzt weder den Schutz des Benutzerkontos auf dem Rechner noch den getrennten Zugriffsschutz für RI-Daten und Weboberfläche.

## Arbeitsweise für den ausführenden Agenten

Dieses Teilpaket ist abgeschlossen; keine neuen Implementierungs- oder Live-Prüfschritte aus den zurückgestellten Punkten ableiten. Die folgenden Aufgaben dokumentieren die Umsetzung. Ein Kästchen bezeichnet nur tatsächlich umgesetzte und geprüfte Arbeit. Zu jedem abgeschlossenen Abschnitt einen kurzen Ergebnisvermerk mit Datum, Prüfung und verbleibenden Grenzen ergänzen, ohne Geheimnisse oder vertrauliche Metadaten. Fehlende echte Zugänge als offen kennzeichnen; synthetische Tests ersetzen keine reale Abnahme.

Kleine, zusammenhängende Commits mit den jeweils betroffenen Tests und Dokumenten erstellen. Das Anlegen dieses Plans aktiviert noch keine Anmeldung, installiert keine Software und erzeugt keinen Token.

## 1. Voraussetzungen und aktuelle Funktionen prüfen

- [x] Repository-Status und Branch prüfen; ausschließlich auf einem passenden `codex/`-Branch arbeiten.
- [x] Aktuelle offizielle CLI-Dokumentation mit Context7 auf PAT, Eintragsfreigabe und feldweisen Passwortabruf prüfen.
- [x] Lokal vorhandene CLI-Version und ihre Befehlsoptionen ohne Anmeldung oder Geheimnisabruf prüfen und dokumentieren.
- [x] Allgemeine Tarifvoraussetzungen anhand der offiziellen Proton-Hilfe prüfen.
- [x] Passenden Proton-Tarif durch Nutzer bestätigen lassen.
- [x] Tatsächliche PAT-Anmeldung unter Windows und WSL durch erfolgreiche Läufe bestätigen; feste Eintragsbindung und gezielter Feldabruf inzwischen ebenfalls auf beiden Systemen geprüft.
- [x] Zielversion auf Proton Pass CLI 2.7.0 (`ba80a19`) festlegen; reale PAT-Anmeldung und Tresorauflistung unter Windows und WSL abgenommen. Unter WSL normale Abmeldung bestätigt, unter Windows nur lokale CLI-Bereinigung; siehe offene Windows-Abmeldeaufgabe.
- [x] Zugriffsmodell festlegen: eigener freigegebener RI-Tresor mit einem Eintrag, ausschließlich lesende Anwendung; serverseitige Eintrags-/Leserechte des Tokens nicht als geprüft einstufen.
- [x] Zielsysteme Windows und WSL sowie manuell gestartete lokale Abrufe für die erste Ausbaustufe festlegen; kein unbeaufsichtigter Dauerbetrieb in dieser Abnahme.
- [x] Fest konfigurierte Eintragsbindung und ausschließlich lesende Befehle in `src/config/ri_proton.py` implementieren und mit künstlichen Daten prüfen. WSL-Referenz anhand echter Metadaten eingerichtet; gezielter Passwortabruf, RI-Anmeldung und RI-Abmeldung anschließend real bestätigt. Windows-Referenz und Windows-RI-Test anschließend ebenfalls real bestätigt; nur der separate Proton-Abmeldehinweis bleibt.
- **Zurückgestellt:** Unbeaufsichtigte Jobs erst nach geprüfter Entsperrung, Neustartverhalten, Sitzungs-/Tokenablauf und festgelegtem Betriebsmodell freigeben.
- [x] Geführte Speicherhilfe `scripts/setup/setup_ri_secret_storage.py` für Windows und Linux/WSL mit verdeckter Eingabe, expliziten OS-Backends, Zufallswerttest und begrenzter Wartezeit implementieren; mit simulierten Backends prüfen.
- [x] WSL-Login-Speicher in der laufenden Sitzung real prüfen: Erreichbarkeit, Entsperrstatus sowie Schreiben, Lesen und Löschen eines künstlichen Zufallswerts bestätigt (06.11.2026). Noch kein PAT oder RI-Passwort gespeichert.
- [x] Windows Credential Manager in der laufenden Sitzung real prüfen: Nutzer bestätigt Schreiben, Lesen und Löschen des Zufallswerts durch die Speicherhilfe (06.11.2026). Noch kein PAT oder RI-Passwort gespeichert.
- [x] Betriebssystemspeicher für PAT und temporäre CLI-Sitzungen in beiden laufenden Umgebungen geprüft: Windows Credential Manager sowie GNOME Secret Service unter WSL mit explizitem D-Bus-Backend; getrennte Ablage, keine automatische gemeinsame Nutzung. Neustartprüfung bleibt offen.
- **Zurückgestellt:** Sichere Einrichtung, Verhalten nach Neustart und Wiederanmeldung nach Ablauf einer Sitzung festlegen. Laut derzeitiger Dokumentation laufen PAT-Sitzungen nach zwei Stunden ab; anhand der gewählten Version bestätigen.

### Verbindlicher Betriebsstand und verbleibende Abnahme

Zielversion: **Proton Pass CLI 2.7.0 (`ba80a19`)**. Zielsysteme: **Windows und WSL**. Erste Ausbaustufe: **lokal und manuell gestartet**; interaktives Entsperren und Ersetzen abgelaufener Tokens sind zulässig. Ein unbeaufsichtigter Betrieb ist noch nicht freigegeben. Die Tests bestätigen reale Anmeldung und Tresorauflistung auf beiden Systemen sowie getrennte sichere Ablage und CLI-Schlüsselverwendung in den laufenden Sitzungen. Unter Windows bleibt die normale Abmeldung ungeklärt; die lokale Bereinigung funktioniert. Unter WSL ist auch die normale Abmeldung bestätigt.

Der Nutzer bestätigt einen eigenen RI-Tresor mit einem Eintrag und eine Sicherung in einem anderen Tresor. Vereinbart ist ausschließlich lesender Anwendungscode; der Token wird nicht als serverseitig schreibgeschützt bezeichnet. Das gezielte Lesen des RI-Eintrags, die feste Eintragsbindung sowie echte RI-Anmeldung und RI-Abmeldung sind inzwischen auf beiden Systemen bestätigt. Neustart-/Ablaufprüfung und die dauerhafte Nutzung durch einen Fetcher bleiben offen. Frühere Vermerke zu CLI 2.3.3 oder fehlgeschlagenen Zwischenprüfungen weiter unten sind historische Prüfergebnisse.

### Geführte Speicherhilfe

Ab Version 0.5.69 ersetzt `python scripts/setup/setup_ri_secret_storage.py` die manuellen Start-, Entsperr- und Testbefehle. Das Skript richtet noch keinen Proton-Zugang ein und ändert keine dauerhafte Proton-Konfiguration. Es prüft ausschließlich den lokalen Speicher und verwendet nur einen eigenen Zufallswert. Ein erfolgreicher Test ist keine Zusage über die Verschlüsselung eines früher angelegten Speichers; ein leeres Speicherpasswort ist unzulässig. Automatisierte Tests nutzen simulierte Backends; die Speicherhilfe ist inzwischen unter Windows und WSL real geprüft. Neustartprüfung, Proton-CLI-Schlüsselablage und PAT-Anbindung bleiben offen.

Validierung der Speicherhilfe: `python -m pytest tests/test_setup_ri_secret_storage.py -q` besteht mit 12 Tests, ohne echte Speicherzugriffe. CLI-Hilfe, lokale Dokumentlinks und `git diff --check` sind geprüft. Der abschließende reguläre Lauf mit `-m "not integration and not live"` besteht mit 621 Tests und 630 abgewählten Tests. Die reale Proton-/RI-Abnahme bleibt offen; die lokalen Speichertests sind inzwischen erfolgreich.

Der Nutzer hat den passenden Tarif bestätigt und CLI 2.7.0 (`ba80a19`) unter Windows und WSL nachgewiesen. Die lokale WSL-Versionsprüfung bestätigt diesen Stand. PAT-Erstellung und Kontofreischaltung wurden nicht praktisch geprüft. GNOME Secret Service antwortet; die manuelle Entsperr-/Speicherprobe war bisher nicht erfolgreich. Das Vorhandensein eines Alias oder Eintrags in `Collections` gilt ausdrücklich nicht als Nachweis eines nutzbaren Speichers.

### Nachbesserung der Speicherhilfe (0.5.70)

Der reale WSL-Speichertest ist laut Nutzerrückmeldung fehlgeschlagen; die tatsächliche Ursache ist noch nicht bestimmt. Die bisherige Sammelmeldung war dafür unzureichend. Die Speicherhilfe übernimmt jetzt den vom GNOME-Dienst gemeldeten Steuerpfad gezielt für den Entsperraufruf und meldet feste Fehlerkategorien ohne native Fehlertexte. Vor einem Schreibversuch wird der Login-Speicher auf Erreichbarkeit und Sperrstatus geprüft. Der neue Aufruf `python scripts/setup/setup_ri_secret_storage.py --check` benötigt kein Passwort und liest keine gespeicherten Geheimnisse; er dient der nächsten lokalen Diagnose. Die Agentenumgebung verweigert selbst den Zugriff auf den Sitzungsbus, was nicht die Ursache im Nutzerterminal belegt. Validierung: 19 gezielte Tests und 628 reguläre Tests bestanden (630 abgewählt); CLI-Hilfe und `git diff --check` geprüft. Reale WSL-Abnahme bleibt offen.

### Erfolgreicher WSL-Speichertest am 06.11.2026

Die direkte Diagnose außerhalb der Agentensandbox reproduzierte den fehlenden D-Bus-Login-Pfad. Ein isolierter Test mit künstlichem Passwort sowie ein isolierter Test einer temporären Kopie der verschlüsselten Login-Datei waren erfolgreich; die Datei selbst war damit grundsätzlich lesbar. Ein vorheriger Neustart über `--replace` hatte den Fehler nicht behoben.

Der fehlerhafte Dienst lief manuell; `gnome-keyring-daemon.service` war inaktiv. Der tatsächlich zu beiden D-Bus-Namen gehörige GNOME-Prozess wurde anhand seiner Prozess-ID und Programmdatei verifiziert, gezielt beendet und anschließend die vorhandene Benutzer-Serviceeinheit gestartet. Danach meldete die Speicherhilfe den Login-Speicher als erreichbar und entsperrt. Der reale Probe-Unterprozess beendete Schreiben, Lesen und Löschen seines eigenen Zufallswerts erfolgreich mit Exitcode 0. Bestehende Geheimnisse wurden nicht ausgelesen; die Originalspeicherdateien wurden weder gelöscht noch ersetzt. Das spricht für einen fehlerhaften Zustand des zuvor laufenden Dienstes; dessen genauer interner Auslöser ist nicht bestimmt.

Damit ist der WSL-Speicher für diese Sitzung geprüft. Der Nutzer bestätigt anschließend auch unter Windows den erfolgreichen vollständigen Lauf der Speicherhilfe: Testwert gespeichert, gelesen und gelöscht. Damit sind beide Betriebssystemspeicher in den laufenden Sitzungen geprüft. Verhalten nach Neustart und die eigene Proton-CLI-Schlüsselablage bleiben separat abzunehmen. Die bisherigen Fehlversuche in den vorherigen Vermerken sind Diagnosehistorie, nicht der aktuelle Speicherstatus. Es wurden noch keine echten Proton- oder RI-Zugangsdaten eingerichtet.

### Lokale Tokenablage (0.5.71)

`python scripts/setup/store_ri_proton_token.py` speichert oder ersetzt einen verdeckt eingegebenen Token im expliziten Betriebssystemspeicher unter `ratsi_melle_ri` / `proton_pass_pat`. Der interne Schreibprozess erhält den Token nur über stdin; Schreiben und anschließendes Lesen werden abgeglichen. Geheimnisse und native Fehlermeldungen werden nicht ausgegeben. Das Skript führt keine Proton-Anmeldung durch und prüft weder Gültigkeit noch Ablauf oder Zugriffsrechte. Bei einem Speicherfehler oder einer Zeitüberschreitung kann der Schreibvorgang bereits erfolgt sein; Erfolg wird dann nicht bestätigt. Unter WSL muss der GNOME-Login-Speicher zuvor entsperrt sein.

Validierung: 31 gezielte Tests der Speicherhilfe und Tokenablage sowie 640 reguläre Tests bestanden (630 abgewählt). CLI-Hilfe, lokale Dokumentlinks und `git diff --check` sind geprüft. Es wurden ausschließlich künstliche Tokens in simulierten Backends verwendet.

Der Nutzer hat einen zunächst einen Tag gültigen Windows-Token erzeugt. Die lokale Ablage samt internem Lesenachweis ist unter Windows durch den erfolgreichen Skriptlauf des Nutzers bestätigt. Die Rechtebeschränkung ist noch nicht bestätigt; tatsächliche Freigaben werden vor Verwendung geprüft. Ein abgelaufener Token wird außerhalb des Skripts erneuert beziehungsweise neu erstellt und anschließend mit demselben Aufruf lokal ersetzt. Nach der inzwischen vereinbarten ersten Ausbaustufe muss die Freigabe beim neuen Token auf den eigenen RI-Tresor beschränkt bleiben.

### Eigenständiger Anmeldetest (0.5.72)

`python scripts/setup/check_ri_proton_login.py` liest den gespeicherten PAT im expliziten OS-Backend und verwendet ein neues temporäres Sitzungsverzeichnis für `pass-cli login`. Persönliche Proton-Umgebungseinstellungen werden entfernt, Keyring wird erzwungen und unter Linux explizit D-Bus gewählt. Nur der Login-Unterprozess erhält den Token als Umgebungswert. Nach jedem Versuch folgt ein Logout ohne Token und die Entfernung des temporären Verzeichnisses. Ein fehlgeschlagener Logout wird nicht als Gesamterfolg ausgegeben. Es werden keine Passworteinträge angefordert; Einzelberechtigung und RI-Anmeldung bleiben offen. Dieser Test ersetzt nicht die noch ausstehende dauerhafte Laufzeitsitzung. Validierung: 36 gezielte Tests der Speicher-, Token- und Login-Skripte sowie 645 reguläre Tests bestanden (630 abgewählt). CLI-Hilfe, lokale Links und `git diff --check` geprüft. Kein echter Token wurde durch den Agenten ausgelesen oder bei Proton verwendet.

### Erweiterter Test und Abmeldegrenzen (0.5.73)

Der Nutzer bestätigt eine echte erfolgreiche Anmeldung unter Windows. Die normale Abmeldung war nicht bestätigt; der anschließende direkte Aufruf `pass-cli logout` nutzte die Standardsitzung und fand dort keine aktive Sitzung. Die konkrete Ursache des Abmeldefehlers ist noch unbekannt. Frühere Angaben zum reinen Login-/Logout-Test oben beschreiben den vorherigen Implementierungsstand.

Der Test führt jetzt nach erfolgreichem Login in derselben Sitzung `pass-cli vault list --output human` aus und zeigt nur deren erfolgreiche Ausgabe an. Er maskiert den vollständigen PAT und entfernt Terminal-Steuerzeichen. Sichtbar sind Tresornamen und IDs, keine einzelnen Passwörter. Weder die Tresorliste noch ein erfolgreicher Login beweisen die Beschränkung auf einen einzigen Eintrag.

Eine nicht bestätigte normale Abmeldung wird als feste Fehlerkategorie ausgegeben; native Fehlertexte bleiben intern. Danach wird `logout --force` mit demselben isolierten Sitzungsverzeichnis ohne PAT im Prozessumfeld ausgeführt. Dies ist ausschließlich lokale CLI-Bereinigung und keine Bestätigung einer serverseitigen Abmeldung. Bei erfolgreichem Test mit nur lokal bestätigter Bereinigung ist der Exitcode 2; Test- oder Bereinigungsfehler ergeben 1, vollständig bestätigter Ablauf 0. Das temporäre Verzeichnis wird wie bisher entfernt. Der Nutzer bestätigt inzwischen den erweiterten Windows-Lauf: Anmeldung und Tresorauflistung erfolgreich, normale Abmeldung mit Fehlerkategorie lokale Bereinigung nicht bestätigt, anschließender `logout --force` laut CLI erfolgreich. Es wurden keine Tresornamen oder IDs in die Dokumentation übernommen. Der serverseitige Abmeldestatus und die Einzelberechtigung bleiben offen. Die Tresorauflistung ohne erneute Tokenübergabe bestätigt die Nutzbarkeit der temporären CLI-Sitzung über Prozessgrenzen hinweg mit dem erzwungenen Windows-Keyring-Backend. Validierung: 40 gezielte Tests und 649 reguläre Tests bestanden (630 abgewählt); CLI-Hilfe und `git diff --check` geprüft.

### Erfolgreicher vollständiger WSL-Anmeldetest am 06.11.2026

Der Nutzer bestätigt den erfolgreichen Lauf von `python scripts/setup/check_ri_proton_login.py` unter WSL: Der gespeicherte PAT wurde intern gelesen, die Proton-Anmeldung und Tresorauflistung waren erfolgreich, und die normale Abmeldung der temporären Testsitzung wurde bestätigt. `logout --force` war nicht erforderlich. Das bestätigt die WSL-Tokenablage sowie die Nutzbarkeit der CLI-Sitzung mit dem erzwungenen D-Bus-Keyring über mehrere Prozesse hinweg. Tresornamen, IDs und Tokenwerte werden nicht in die Dokumentation übernommen.

Die Speicher- und Anmeldeprüfung in den laufenden Sitzungen ist damit für Windows und WSL erfolgt. Die normale Windows-Abmeldung bleibt gesondert offen; dort war nur die lokale Bereinigung bestätigt. Nach dem inzwischen vereinbarten Modell bleiben Neustartverhalten, feste Eintragsbindung und ausschließlich lesender Zugangsdienst, dauerhafte Laufzeitsitzung sowie echte RI-Anbindung offen; serverseitige Schreibrechte sind unbekannt.

### Gemeinsamer Setup-Ordner (0.5.74)

Die drei Proton-Hilfsskripte liegen unter `scripts/setup/`: `setup_ri_secret_storage.py`, `store_ri_proton_token.py` und `check_ri_proton_login.py`. Interne Importe, direkte Starts, Tests und aktive Dokumentation sind an die neue Verzeichnistiefe angepasst. Vor dem Verschieben wurden die bisherigen Dateien unter `archive/scripts/` bytegleich gesichert und per SHA-256 mit dem vorherigen Stand verglichen. Die Archivkopien bleiben unverändert und sind gemäß Repository-Regeln lokal, nicht in Git. Die Zugangsdatenablage und der Name des gespeicherten Tokens werden durch die Verschiebung nicht geändert. Validierung: alle drei direkten Hilfeaufrufe funktionieren; 40 gezielte und 649 reguläre Tests bestanden (630 abgewählt). Lokale Dokumentlinks, alte Pfad-/Importverweise und `git diff --check` sind geprüft. Archivkopien vor dem Commit erneut mit dem vorherigen Git-Stand per SHA-256 verglichen.

### Bisherige Prüfergebnisse vom 06.11.2026

- Repository sauber auf `codex/feature/ri-proton-pass-zugang` geprüft. Die Statusprüfung ist bei Fortsetzung erneut auszuführen.
- Bei der ersten Vorprüfung war in der WSL2-Umgebung `/home/diane/.local/bin/pass-cli` vorhanden: `Proton Pass CLI 2.3.3 (0d7235d)`. Es wurde nichts installiert oder aktualisiert. Windows wurde nicht geprüft.
- `pass-cli pat access grant --help` bestätigt in dieser Version `--personal-access-token-id`, `--share-id`, `--item-id` und `--role viewer`. Diese Optionen waren für die ursprüngliche serverseitige Eintragsbegrenzung vorgesehen. Inzwischen vereinbart ist der eigene RI-Tresor mit einem Eintrag und ausschließlich lesender Anwendungscode; feinere CLI-Freigaben bleiben optional.
- `pass-cli item view --help` bestätigt `--share-id`, `--item-id`, `--field` und `--output`. Context7 dokumentiert die Felder `username` und `password`. Der vorgesehene Aufruf ist `pass-cli item view --share-id <SHARE_ID> --item-id <ITEM_ID> --field password`; seine Standardausgabe muss der spätere Zugangsdienst intern abfangen. Dieser Abruf wurde nicht ausgeführt.
- Die lokale Login-Hilfe nennt `--pat`, die aktuelle Dokumentation dagegen `--personal-access-token`. Der geplante Anmeldeweg bleibt die kurzzeitige Übergabe über `PROTON_PASS_PERSONAL_ACCESS_TOKEN` an den Unterprozess; dessen Funktion in der gewählten Zielversion ist noch real zu prüfen. Keine geheimen Tokenwerte als Argument verwenden.
- Das [offizielle Changelog](https://github.com/protonpass/pass-cli/blob/main/CHANGELOG.md) führt PAT-Unterstützung ab 1.10.0 (08.04.2026) und als neuesten dort gelisteten Stand 2.7.0 (03.11.2026). Daraus folgt keine vollständige Mindestversionszusage für alle benötigten Sicherheitsmerkmale. 2.3.3 ist vorläufig nur die lokal untersuchte Version. Seit 2.5.0 ist der direkte Login mit Kontopasswort entfernt; für die Verwaltung ist der Weblogin vorzusehen.
- Die [Proton-Hilfe zu Zugriffstokens](https://proton.me/support/pass-access-tokens) nennt Pass Plus, Pass Family, Proton Unlimited, Pass Professional und Workspace Standard. Das konkret verwendete Konto und seine Freischaltung wurden nicht geprüft. Die Webanleitung beschreibt Tresorfreigaben; die feinere Eintragsfreigabe ist in der CLI-Dokumentation und lokalen Befehlsoptionen belegt und muss mit Testtoken bestätigt werden.
- Laut aktueller Konfigurationsdokumentation verliert der Linux-Kernel-Keyring seine Schlüssel beim Neustart. Ein optionales D-Bus-Secret-Service-Backend kann persistent speichern (`PROTON_PASS_LINUX_KEYRING=dbus`), benötigt aber einen verfügbaren entsperrten Dienst. Verfügbarkeit und Unterstützung in der lokalen Version sind noch offen; Kernel-Keyring allein löst die dauerhafte PAT-Ablage nicht.
- Es wurden ausschließlich Version und Hilfe aufgerufen, keine Kontodaten, Einträge, Token oder vorhandenen Sitzungsinhalte ausgelesen. Echte Anmeldung, Passwortausgabe, Speichereignung und Rechtebegrenzung sind nicht abgenommen.

Abnahme: Version, Kontovoraussetzungen und tragfähiges Speicherkonzept sind belegt. Ohne verfügbaren sicheren Speicher bleibt die Anbindung gesperrt; kein stiller Wechsel auf Klartextablage.

## 2. Zugang aus dem eigenen RI-Tresor bereitstellen

- [x] Eintragsbindung und Ablehnung fremder beziehungsweise zusätzlicher Einträge mit künstlichen Referenzen und CLI-Antworten testen; keine zusätzlichen echten Passworteinträge erzeugt.
- [x] Verwaltungsanmeldung und Testsitzung trennen: pro Test neues temporäres CLI-Sitzungsverzeichnis außerhalb des Repositorys verwenden und ausschließlich mit dem gespeicherten PAT anmelden. Eine dauerhafte Fetcher-Sitzung ist nicht Teil dieser Abnahme.
- [x] Zeitlich begrenzte PATs mit Zugriff auf den eigenen RI-Tresor einrichten; reale Windows-/WSL-Anmeldungen bestätigt. Der Tresor enthält laut Nutzer ausschließlich den RI-Eintrag. Tokenrollen sind nicht geprüft. Tokenwerte nicht in Agentenprotokolle, Terminalmitschnitte oder Tickets übernehmen.
- [x] Skript `scripts/setup/store_ri_proton_token.py` zum verdeckten Speichern und Ersetzen des PAT mit internem Schreib-/Lesenachweis implementieren; synthetisch testen.
- [x] Windows-PAT verdeckt im Windows Credential Manager hinterlegen und internes Lesen bestätigen; Nutzer bestätigt erfolgreichen Lauf von `store_ri_proton_token.py` (06.11.2026).
- [x] PAT für Linux/WSL separat im GNOME-Login-Speicher hinterlegen; erfolgreicher Login-Test mit intern aus dem Speicher gelesenem Token durch Nutzer bestätigt (06.11.2026).
- [x] Eigenes Skript `scripts/setup/check_ri_proton_login.py` für einen begrenzten Login-/Logout-Test in einer neuen temporären Sitzung mit erzwungenem Keyring implementieren; synthetisch prüfen.
- [x] Echte Windows-Anmeldung mit gespeichertem Token durch Nutzerlauf bestätigt (06.11.2026); normale Abmeldung fehlgeschlagen.
- [x] Tresorauflistung und gesonderte lokale CLI-Bereinigung bei Abmeldefehlern implementieren (0.5.73); synthetisch prüfen.
- [x] Erweiterten Windows-Test mit erfolgreicher Anmeldung und Tresorauflistung ausführen; Nutzer bestätigt auch erfolgreiche lokale CLI-Bereinigung über `logout --force` (06.11.2026).
- [x] Erweiterten WSL-Test ausführen: Anmeldung, Tresorauflistung und normale Abmeldung laut Nutzer erfolgreich (06.11.2026); keine erzwungene Bereinigung benötigt.
- **Zurückgestellt:** Normale Windows-Abmeldung weiter untersuchen und serverseitigen Sitzungsstatus verifizieren; der gemeldete Fehler betrifft die Kategorie lokale Bereinigung, beweist aber weder Erfolg noch Fehlschlag der entfernten Abmeldung.
- [x] Mit künstlichen Daten nachweisen: Nur der konfigurierte RI-Eintrag wird angefordert, fremde Tresor-/Eintragsreferenzen und nicht erlaubte CLI-Operationen werden vor einem Prozessaufruf abgewiesen. Gezieltes Lesen unter WSL real bestätigt; keine Schreibprobe und kein Zugriff auf den Sicherungstresor.
- **Zurückgestellt:** Ablauf, Entzug und Erneuerung des Tokens beschreiben; für Erneuerung ausschließlich dieselbe RI-Tresorfreigabe beibehalten.

Abnahme: Der Zugriff auf den eigenen RI-Tresor und das gezielte Lesen des konfigurierten Eintrags sind bestätigt; der Zugangsdienst lässt ausschließlich die festgelegten Leseoperationen zu. Serverseitige Schreibrechte des Tokens bleiben davon getrennt als unbekannt dokumentiert. Keine Änderungsversuche an echten Einträgen, kein Zugriff auf die Sicherung. Ergebnisse ohne Tokenwerte und Eintragsinhalte festhalten.

## 3. Abgegrenzten Zugangsdienst implementieren

- [x] Eine kleine Schnittstelle für den RI-Zugangsabruf definieren, unabhängig vom HTTP-Client. Konfiguration enthält ausschließlich nicht geheime, feste Tresor-/Eintragsreferenzen; keine Auswahl beliebiger Einträge oder Befehle über Webparameter. Nur explizit erlaubte Leseoperationen zulassen und jede Schreiboperation vor einem CLI-Aufruf abweisen.
- [x] CLI mit festgelegtem Programm, Argumentliste ohne Shell, begrenzter Laufzeit und abgefangenen Ausgaben aufrufen. Passwortausgabe nur intern über eine Pipe lesen; weder anzeigen noch auf Platte schreiben.
- [x] PAT bei nötiger Anmeldung aus dem Betriebssystemspeicher lesen und ausschließlich an den vorgesehenen CLI-Unterprozess übergeben. Vererbung vorhandener Proton-Kontopasswörter oder fremder Sitzungs-/Schlüsseleinstellungen verhindern.
- [x] Für den Test eine neue isolierte Sitzung mit dem vorgesehenen PAT und erzwungenem Keyring verwenden; vollständige Kontositzungen und unsichere Backends ablehnen.
- **Zurückgestellt:** Fehlende CLI, fehlenden Speicherzugriff, Zeitüberschreitung, leere oder ungültige Ausgabe, fehlenden Eintrag, abgelaufenen beziehungsweise widerrufenen Token und abgelaufene Sitzung mit inhaltsfreien Fehlern behandeln. Keine unbegrenzten Wiederanmeldeversuche.
- **Zurückgestellt:** Geheimnisse nur solange benötigt im Speicher halten. CLI-Ausgaben, Prozessumgebung und Zugangsdaten nicht in Fehlerobjekte, Debug-Logs oder Jobstatus übernehmen; keine garantierte Speicherlöschung für Python behaupten.

Abnahme: Zugangsdienst ist mit einer simulierten CLI prüfbar und liefert entweder den vorgesehenen Zugang oder einen sicheren Fehler. Öffentliche BI-Abläufe benötigen keine Proton-Abhängigkeit.

### Echte RI-Abnahme unter WSL und Windows (0.5.76)

Der erste echte Lauf bestätigte den gezielten internen Zugangsfeldabruf; die zu enge Zielprüfung brach bei einem Zwischenschritt ab. Die datensparsame Ablaufdiagnose identifizierte den Schritt `ylogonstart.asp` sowie den Abmeldeabschluss `smc_end.asp`, jeweils auf demselben HTTPS-Host. Das öffentliche Formular verwendet `logongopn=info` ohne `.asp`. Diese beobachteten Abläufe sind jetzt gezielt freigegeben; fremde Hosts und andere Pfade bleiben abgewiesen. HTML-Meta-Weiterleitungen werden innerhalb der festen Ziele und des Weiterleitungslimits verarbeitet. Beim Logout wird die reine Abschlussseite nicht aufgerufen, sondern die Zugangssperre unmittelbar geprüft.

Der abschließende echte Aufruf von `scripts/setup/check_ri_access.py` unter WSL bestand mit Exitcode 0: Proton-Zugang geöffnet, Felder des fest gebundenen Eintrags intern gelesen, RI-Anmeldung über geschützten Einstieg bestätigt und RI-Abmeldung durch erneute Weiterleitung zum Loginformular bestätigt. Es wurden keine Namen, IDs, Geheimniswerte, Cookieinhalte oder geschützten HTML-Inhalte in diese Dokumentation übernommen. Keine Sitzungsunterlagen heruntergeladen, keine Rohdaten oder Indizes geschrieben und keine Änderung an Passworteinträgen vorgenommen.

Validierung des korrigierten Ablaufs: 47 gezielte Tests sowohl unter WSL als auch unter Windows bestanden, darunter sechs separat ausgeführte betroffene WSL-Integrationstests; reguläre Suite mit 690 bestandenen und 636 abgewählten Tests. Lokale Links und `git diff --check` sind geprüft. Die separate Windows-Eintragsbindung und der echte RI-Test mit Windows-Python 3.14.8 sind inzwischen ebenfalls erfolgreich ausgeführt: RI-Anmeldung, RI-Abmeldung und anschließende Zugangssperre bestätigt. Die nachfolgende Proton-Abmeldung liefert weiterhin den bekannten Hinweis mit Exitcode 2. Beim Agentenstart aus WSL musste nur für den Testprozess das bereits installierte Windows-Proton-Verzeichnis im PATH ergänzt werden; keine dauerhafte PATH-Änderung. Eine produktive Laufzeitsitzung für den späteren Fetcher, Neustart-/Ablaufverhalten und RI-Download-/Index-/Webfunktionen sind durch diese Abnahme nicht erledigt.

### Gezielter Anmeldetest (0.5.75)

Der öffentliche RI-Ablauf ist ohne Credentials geprüft: Einstieg über `default.asp`/`info.asp`, Weiterleitung zu `ylogon.asp`, Formular `smclogon` mit POST nach `ylogon2.asp`. Die Zugangsfelder und versteckten Formularparameter werden ausschließlich im Speicher verarbeitet; eine Passwortänderung oder Wiederherstellung wird nicht angefordert. Der Test akzeptiert nur das feste HTTPS-Ziel und bekannte Login-/Status-/Logoutpfade, begrenzt Antworten und Weiterleitungen und versucht keine zweite Passwortübermittlung.

`python scripts/setup/check_ri_access.py --configure` speichert nur die Referenzen des einzigen aktiven Login-Eintrags. Dieser Schritt war unter WSL mit echten Metadaten erfolgreich. `python scripts/setup/check_ri_access.py` liest danach gezielt die Zugangsfelder intern und prüft die RI-Anmeldung ohne Unterlagendownload. Referenzen werden auf jedem Betriebssystem separat eingerichtet. Erfolgsprüfung über geschützten Einstieg und bestätigte RI-Abmeldung sind Voraussetzung für die echte Abnahme; diese steht vor dem ersten realen Lauf noch aus. Reguläre Tests verwenden ausschließlich künstliche Seiten und Zugangswerte.

## 4. Zurückgestellte Anbindung an den RI-Fetcher

- **Zurückgestellt:** Abhängigkeit mit dem Fetcher-Teilbranch abstimmen. Falls dieser noch fehlt, nur die Zugangsschnittstelle und ihre Tests liefern; echte Anmeldung weiterhin als offen führen.
- **Zurückgestellt:** Zugang unmittelbar vor der RI-Anmeldung abrufen; keine Weitergabe an öffentliche BI-Jobs, Suchdienste oder Analysefunktionen.
- **Zurückgestellt:** HTTP-Anmeldung gemäß RI-Hauptplan auf erlaubte Hosts begrenzen und Zugangsdaten, Cookies und Token aus Logs und Statusanzeigen ausschließen.
- **Zurückgestellt:** Bei Secret- oder Anmeldefehlern den Job vor Dokumentabrufen abbrechen; keine Ausweichanmeldung mit Klartextkonfiguration.

Abnahme: Der Fetcher erhält den Zugang ausschließlich über den Zugangsdienst. Eine erfolgreiche Passwortabfrage allein gilt noch nicht als erfolgreiche RI-Anmeldung.

## 5. Automatisiert prüfen und lokal abnehmen

- [x] Tests mit künstlichen Geheimnissen und simulierter CLI für Eintragsbindung, erlaubte Leseoperationen, Metadatenfehler und Erfolgsfall ergänzen; zusätzliche realistische Ablauf-/Neustartfälle bleiben separat offen. Reguläre Tests greifen weder auf Proton noch auf das echte RI zu.
- **Zurückgestellt:** Mit künstlichen Werten nachweisen, dass weder RI-Passwort noch PAT in Logs, Fehlertexten, Jobstatus, persistenten Dateien oder Prozessargumenten erscheinen und nur der vorgesehene Unterprozess nötige Umgebungswerte erhält.
- **Zurückgestellt:** Testen, dass falsche Sitzungsart, unsichere Schlüsselanbieter und fehlende Speicherunterstützung abgewiesen werden. Bestehende öffentliche Abläufe ohne Proton-Konfiguration prüfen.
- [x] Reguläre Suite (690 Tests), betroffene Integrationstests (sechs) und gezielte Windows-/WSL-Tests (je 47) ausführen und Ergebnisse dokumentieren. Ein PR wurde nicht erstellt; dessen vorgeschriebener vollständiger Testlauf bleibt vor einem späteren PR separat erforderlich.
- **Zurückgestellt:** In jeder unterstützten Umgebung mit Testtoken und Testeinträgen Anmeldung, erneute Anmeldung nach Sitzungsablauf, Neustart, Entzug und Rechtebegrenzung prüfen. Nicht ausgeführte Fälle ausdrücklich offen lassen.
- [x] Kleine echte RI-Anmeldung unter WSL und Windows nach Prüfung des Formularablaufs bestätigen; RI-Abmeldung jeweils durch erneute Sperre des geschützten Einstiegs geprüft. Kein Dokumentdownload und keine persistenten HTML-/Cookie-/Passwortdaten. Separater Windows-Proton-Abmeldehinweis bleibt offen.

Abnahme im abgeschlossenen Umfang: Automatisierte Tests und echte manuelle RI-Zugriffe auf beiden Systemen bestehen. Eintrags- und Befehlsbindung sind in der Anwendung geprüft; serverseitige Schreibrechte des Tokens bleiben unbekannt. Neustart-/Ablauf- und weitere Betriebsprüfungen sind ausdrücklich nicht abgenommen.

## 6. Betrieb dokumentieren und abschließen

- **Zurückgestellt:** Betriebsanleitung für Installation der geprüften CLI-Version, sichere lokale Einrichtung, Eintragsfreigabe, Anmeldung, Token-Erneuerung, Widerruf und Entfernung lokaler Sitzungen erstellen. Beispiele enthalten ausschließlich Platzhalter.
- **Zurückgestellt:** Verhalten bei gesperrtem Keyring, Neustart und abgelaufenem Zugang sowie Wiederherstellung auf einem neuen Rechner beschreiben; keine Geheimnisse in ungeschützte Backups aufnehmen.
- [x] README, `docs/ist_stand.md`, RI-Hauptplan und `docs/plans/project_tasks.md` anhand der tatsächlichen Umsetzung aktualisieren; `VERSION` bei den funktionalen Schritten bis 0.5.76 angepasst. Der reine Planabschluss benötigt keinen weiteren Versionssprung.
- [x] Diff, Dokumentlinks und Whitespace prüfen sowie zusammenhängende Zwischen-Commits erstellen. Kein PR erstellt; Abnahmegrenzen sind in diesem Plan dokumentiert.

## Quellen und zurückgestellte Entscheidungen

Die Quellen beschreiben den aktuellen Entwicklungsstand; vor Implementierung mit der tatsächlich installierten Version abgleichen:

- [Proton Pass CLI](https://github.com/protonpass/pass-cli)
- [PAT erstellen und Eintragsrechte vergeben](https://github.com/protonpass/pass-cli/blob/main/docs/public/docs/commands/personal-access-token.md)
- [Konfiguration und sichere Schlüsselablage](https://github.com/protonpass/pass-cli/blob/main/docs/public/docs/get-started/configuration.md)
- [Tarifvoraussetzungen für Zugriffstokens](https://proton.me/support/pass-access-tokens)
- [Versionshistorie](https://github.com/protonpass/pass-cli/blob/main/CHANGELOG.md)
- [Feldweiser Eintragsabruf](https://github.com/protonpass/pass-cli/blob/main/docs/public/docs/commands/item.md)
- [Anmeldung und PAT-Sitzungen](https://github.com/protonpass/pass-cli/blob/main/docs/public/docs/commands/login.md)

Festgelegt sind CLI 2.7.0, Windows und WSL sowie manuell gestarteter lokaler Betrieb mit ausschließlich lesendem Anwendungscode. Feste Eintragsbindung, gezielter Passwortabruf und echter RI-Anmelde-/Abmeldeablauf sind inzwischen unter WSL und Windows bestätigt. Offen bleiben Neustart-/Ablaufverhalten, normale Windows-Proton-Abmeldung, dauerhafte Laufzeitsitzung und Anbindung an den zukünftigen RI-Fetcher. Diese Punkte sind zurückgestellte Folgearbeiten außerhalb des abgeschlossenen Einrichtungsumfangs und keine zugesicherten Eigenschaften der Anwendung.
