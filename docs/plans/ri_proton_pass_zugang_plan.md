# Plan: RI-Zugang sicher über Proton Pass beziehen

Stand: 06.11.2026. Status: Vorprüfung begonnen, geführte Speicherhilfe implementiert; noch keine Proton-/RI-Anbindung eingerichtet.

Vorhaben-Branch: `codex/feature/ri-ratsbereich`.
Arbeitsbranch dieses Teilpakets: `codex/feature/ri-proton-pass-zugang`.
Übergeordneter Plan: [Geschützter Ratsbereich](ri_ratsbereich_plan.md), insbesondere Schritte 2 und 4.

## Ziel und Schutzgrenzen

Der künftige RI-Fetcher soll Benutzername und Passwort bei Bedarf aus einem einzelnen Proton-Pass-Eintrag beziehen. Weder RI-Passwort noch Proton-Zugriffstoken werden als Klartext in `.env`, Konfiguration, Quellcode, Kommandozeilenargumenten, Logs oder temporären Dateien abgelegt. Nicht geheime Referenzen wie Eintrags-ID und CLI-Pfad dürfen konfiguriert werden.

Die Anwendung erhält einen Personal Access Token (PAT), der ausschließlich den RI-Eintrag mit der Rolle `viewer` lesen darf. Die Begrenzung gilt für einen vollständigen Eintrag einschließlich seiner Felder, nicht für ein einzelnes Passwortfeld. Ein eigener Tresor kann die Organisation erleichtern, ersetzt aber keine Beschränkung des Tokens auf den Eintrag. Die Anwendung darf keine vollständige persönliche Proton-Sitzung verwenden.

Der Token ist selbst ein Geheimnis und braucht einen geeigneten Betriebssystemspeicher. Die CLI muss auch ihre lokalen Sitzungsdaten mit einem Schlüssel aus dem Betriebssystem-Keyring schützen. Ein Dateibackend mit daneben liegendem Klartextschlüssel oder ein dauerhaft in einer Umgebungsdatei gespeicherter Schlüssel erfüllt das Ziel nicht. Für eine Anmeldung nötige Umgebungswerte dürfen allenfalls kurzzeitig und gezielt an den CLI-Unterprozess übergeben werden; sie werden nicht in der globalen Prozessumgebung oder Shell-Historie hinterlegt.

Zur RI-Anmeldung muss das Passwort kurzzeitig entschlüsselt im Prozess verfügbar sein. Diese Lösung schützt die Ablage und begrenzt den Proton-Zugriff; sie ersetzt weder den Schutz des Benutzerkontos auf dem Rechner noch den getrennten Zugriffsschutz für RI-Daten und Weboberfläche.

## Arbeitsweise für den ausführenden Agenten

Die Aufgaben in Reihenfolge bearbeiten. Ein Kästchen erst nach Umsetzung und passender Prüfung abhaken. Zu jedem abgeschlossenen Abschnitt einen kurzen Ergebnisvermerk mit Datum, Prüfung und verbleibenden Grenzen ergänzen, ohne Geheimnisse oder vertrauliche Metadaten. Fehlende echte Zugänge als offen kennzeichnen; synthetische Tests ersetzen keine reale Abnahme.

Kleine, zusammenhängende Commits mit den jeweils betroffenen Tests und Dokumenten erstellen. Das Anlegen dieses Plans aktiviert noch keine Anmeldung, installiert keine Software und erzeugt keinen Token.

## 1. Voraussetzungen und aktuelle Funktionen prüfen

- [x] Repository-Status und Branch prüfen; ausschließlich auf einem passenden `codex/`-Branch arbeiten.
- [x] Aktuelle offizielle CLI-Dokumentation mit Context7 auf PAT, Eintragsfreigabe und feldweisen Passwortabruf prüfen.
- [x] Lokal vorhandene CLI-Version und ihre Befehlsoptionen ohne Anmeldung oder Geheimnisabruf prüfen und dokumentieren.
- [x] Allgemeine Tarifvoraussetzungen anhand der offiziellen Proton-Hilfe prüfen.
- [x] Passenden Proton-Tarif durch Nutzer bestätigen lassen.
- [ ] Tatsächliche Kontofreischaltung mit eingeschränktem Testtoken prüfen.
- [ ] Verbindliche Zielversion für die Umsetzung wählen und mit eingeschränktem Testtoken abnehmen; die lokale Hilfe allein belegt noch keine funktionsfähige Anmeldung oder Rechtebegrenzung.
- [ ] Betriebsumgebung festlegen: Windows, WSL oder beide; interaktiver lokaler Abruf oder unbeaufsichtigte Jobs. Unterstützte Umgebungen und Einschränkungen dokumentieren.
- [x] Geführte Speicherhilfe `scripts/setup_ri_secret_storage.py` für Windows und Linux/WSL mit verdeckter Eingabe, expliziten OS-Backends, Zufallswerttest und begrenzter Wartezeit implementieren; mit simulierten Backends prüfen.
- [ ] Je unterstützter Umgebung prüfen, ob ein geeigneter Betriebssystemspeicher für den PAT und das CLI-Keyring-Backend tatsächlich verfügbar sind. Windows Credential Manager und Linux-Kernel-Keyring nicht als automatisch zwischen Windows und WSL geteilt voraussetzen.
- [ ] Sichere Einrichtung, Verhalten nach Neustart und Wiederanmeldung nach Ablauf einer Sitzung festlegen. Laut derzeitiger Dokumentation laufen PAT-Sitzungen nach zwei Stunden ab; anhand der gewählten Version bestätigen.

### Geführte Speicherhilfe

Ab Version 0.5.69 ersetzt `python scripts/setup_ri_secret_storage.py` die manuellen Start-, Entsperr- und Testbefehle. Das Skript richtet noch keinen Proton-Zugang ein und ändert keine dauerhafte Proton-Konfiguration. Es prüft ausschließlich den lokalen Speicher und verwendet nur einen eigenen Zufallswert. Ein erfolgreicher Test ist keine Zusage über die Verschlüsselung eines früher angelegten Speichers; ein leeres Speicherpasswort ist unzulässig. Automatisierte Tests nutzen simulierte Backends; reale Windows-/WSL-Abnahme und Neustartprüfung bleiben offen.

Validierung der Speicherhilfe: `python -m pytest tests/test_setup_ri_secret_storage.py -q` besteht mit 12 Tests, ohne echte Speicherzugriffe. CLI-Hilfe, lokale Dokumentlinks und `git diff --check` sind geprüft. Der abschließende reguläre Lauf mit `-m "not integration and not live"` besteht mit 621 Tests und 630 abgewählten Tests. Die reale Abnahme bleibt offen.

Der Nutzer hat den passenden Tarif bestätigt und CLI 2.7.0 (`ba80a19`) unter Windows und WSL nachgewiesen. Die lokale WSL-Versionsprüfung bestätigt diesen Stand. PAT-Erstellung und Kontofreischaltung wurden nicht praktisch geprüft. GNOME Secret Service antwortet; die manuelle Entsperr-/Speicherprobe war bisher nicht erfolgreich. Das Vorhandensein eines Alias oder Eintrags in `Collections` gilt ausdrücklich nicht als Nachweis eines nutzbaren Speichers.

### Nachbesserung der Speicherhilfe (0.5.70)

Der reale WSL-Speichertest ist laut Nutzerrückmeldung fehlgeschlagen; die tatsächliche Ursache ist noch nicht bestimmt. Die bisherige Sammelmeldung war dafür unzureichend. Die Speicherhilfe übernimmt jetzt den vom GNOME-Dienst gemeldeten Steuerpfad gezielt für den Entsperraufruf und meldet feste Fehlerkategorien ohne native Fehlertexte. Vor einem Schreibversuch wird der Login-Speicher auf Erreichbarkeit und Sperrstatus geprüft. Der neue Aufruf `python scripts/setup_ri_secret_storage.py --check` benötigt kein Passwort und liest keine gespeicherten Geheimnisse; er dient der nächsten lokalen Diagnose. Die Agentenumgebung verweigert selbst den Zugriff auf den Sitzungsbus, was nicht die Ursache im Nutzerterminal belegt. Validierung: 19 gezielte Tests und 628 reguläre Tests bestanden (630 abgewählt); CLI-Hilfe und `git diff --check` geprüft. Reale WSL-Abnahme bleibt offen.

### Bisherige Prüfergebnisse vom 06.11.2026

- Repository sauber auf `codex/feature/ri-proton-pass-zugang` geprüft. Die Statusprüfung ist bei Fortsetzung erneut auszuführen.
- Bei der ersten Vorprüfung war in der WSL2-Umgebung `/home/diane/.local/bin/pass-cli` vorhanden: `Proton Pass CLI 2.3.3 (0d7235d)`. Es wurde nichts installiert oder aktualisiert. Windows wurde nicht geprüft.
- `pass-cli pat access grant --help` bestätigt in dieser Version `--personal-access-token-id`, `--share-id`, `--item-id` und `--role viewer`. Mit `--item-id` muss der Zugriff auf den einzelnen Eintrag begrenzt werden; keine zusätzliche Tresorfreigabe erteilen.
- `pass-cli item view --help` bestätigt `--share-id`, `--item-id`, `--field` und `--output`. Context7 dokumentiert die Felder `username` und `password`. Der vorgesehene Aufruf ist `pass-cli item view --share-id <SHARE_ID> --item-id <ITEM_ID> --field password`; seine Standardausgabe muss der spätere Zugangsdienst intern abfangen. Dieser Abruf wurde nicht ausgeführt.
- Die lokale Login-Hilfe nennt `--pat`, die aktuelle Dokumentation dagegen `--personal-access-token`. Der geplante Anmeldeweg bleibt die kurzzeitige Übergabe über `PROTON_PASS_PERSONAL_ACCESS_TOKEN` an den Unterprozess; dessen Funktion in der gewählten Zielversion ist noch real zu prüfen. Keine geheimen Tokenwerte als Argument verwenden.
- Das [offizielle Changelog](https://github.com/protonpass/pass-cli/blob/main/CHANGELOG.md) führt PAT-Unterstützung ab 1.10.0 (08.04.2026) und als neuesten dort gelisteten Stand 2.7.0 (03.11.2026). Daraus folgt keine vollständige Mindestversionszusage für alle benötigten Sicherheitsmerkmale. 2.3.3 ist vorläufig nur die lokal untersuchte Version. Seit 2.5.0 ist der direkte Login mit Kontopasswort entfernt; für die Verwaltung ist der Weblogin vorzusehen.
- Die [Proton-Hilfe zu Zugriffstokens](https://proton.me/support/pass-access-tokens) nennt Pass Plus, Pass Family, Proton Unlimited, Pass Professional und Workspace Standard. Das konkret verwendete Konto und seine Freischaltung wurden nicht geprüft. Die Webanleitung beschreibt Tresorfreigaben; die feinere Eintragsfreigabe ist in der CLI-Dokumentation und lokalen Befehlsoptionen belegt und muss mit Testtoken bestätigt werden.
- Laut aktueller Konfigurationsdokumentation verliert der Linux-Kernel-Keyring seine Schlüssel beim Neustart. Ein optionales D-Bus-Secret-Service-Backend kann persistent speichern (`PROTON_PASS_LINUX_KEYRING=dbus`), benötigt aber einen verfügbaren entsperrten Dienst. Verfügbarkeit und Unterstützung in der lokalen Version sind noch offen; Kernel-Keyring allein löst die dauerhafte PAT-Ablage nicht.
- Es wurden ausschließlich Version und Hilfe aufgerufen, keine Kontodaten, Einträge, Token oder vorhandenen Sitzungsinhalte ausgelesen. Echte Anmeldung, Passwortausgabe, Speichereignung und Rechtebegrenzung sind nicht abgenommen.

Abnahme: Version, Kontovoraussetzungen und tragfähiges Speicherkonzept sind belegt. Ohne verfügbaren sicheren Speicher bleibt die Anbindung gesperrt; kein stiller Wechsel auf Klartextablage.

## 2. Zugriff auf genau einen Eintrag einrichten

- [ ] Einrichtung zunächst mit einem künstlichen RI-Eintrag und einem zweiten, nicht freigegebenen Testeintrag vorbereiten.
- [ ] Verwaltungsanmeldung und Laufzeitsitzung trennen: separates CLI-Sitzungsverzeichnis für die Anwendung außerhalb des Repositorys verwenden; dort ausschließlich eine PAT-Sitzung zulassen.
- [ ] Einen benannten PAT mit begrenztem Ablaufdatum erstellen und ausschließlich dem vorgesehenen Eintrag die Rolle `viewer` gewähren. Token-Ausgabe nicht in Agentenprotokolle, Terminalmitschnitte oder Tickets übernehmen.
- [ ] PAT über eine geschützte lokale Eingabe im gewählten Betriebssystemspeicher hinterlegen. Das Konto-Passwort von Proton nicht in der Anwendung speichern.
- [ ] Mit der Laufzeitsitzung nachweisen: freigegebener Testeintrag lesbar, zweiter Testeintrag nicht lesbar, Änderung des freigegebenen Eintrags nicht erlaubt. Freigabeliste auf zusätzliche Rechte prüfen.
- [ ] Ablauf, Entzug und Erneuerung des Tokens beschreiben; für Erneuerung dieselbe Eintragsbeschränkung sicherstellen.

Abnahme: Die Rechtebegrenzung ist mit einem echten eingeschränkten Testtoken geprüft, ohne Zugriff auf andere persönliche Einträge vorauszusetzen. Ergebnis nur ohne Tokenwerte und Eintragsinhalte festhalten.

## 3. Abgegrenzten Zugangsdienst implementieren

- [ ] Eine kleine Schnittstelle für den RI-Zugangsabruf definieren, unabhängig vom HTTP-Client. Konfiguration enthält ausschließlich nicht geheime Referenzen; beliebige Einträge dürfen nicht über Webparameter auswählbar sein.
- [ ] CLI mit festgelegtem Programm, Argumentliste ohne Shell, begrenzter Laufzeit und abgefangenen Ausgaben aufrufen. Passwortausgabe nur intern über eine Pipe lesen; weder anzeigen noch auf Platte schreiben.
- [ ] PAT bei nötiger Anmeldung aus dem Betriebssystemspeicher lesen und ausschließlich an den vorgesehenen CLI-Unterprozess übergeben. Vererbung vorhandener Proton-Kontopasswörter oder fremder Sitzungs-/Schlüsseleinstellungen verhindern.
- [ ] Sicherstellen, dass die Laufzeitsitzung den vorgesehenen PAT verwendet und der konfigurierte sichere Schlüsselanbieter aktiv ist; vollständige Kontositzungen und unsichere Backends ablehnen.
- [ ] Fehlende CLI, fehlenden Speicherzugriff, Zeitüberschreitung, leere oder ungültige Ausgabe, fehlenden Eintrag, abgelaufenen beziehungsweise widerrufenen Token und abgelaufene Sitzung mit inhaltsfreien Fehlern behandeln. Keine unbegrenzten Wiederanmeldeversuche.
- [ ] Geheimnisse nur solange benötigt im Speicher halten. CLI-Ausgaben, Prozessumgebung und Zugangsdaten nicht in Fehlerobjekte, Debug-Logs oder Jobstatus übernehmen; keine garantierte Speicherlöschung für Python behaupten.

Abnahme: Zugangsdienst ist mit einer simulierten CLI prüfbar und liefert entweder den vorgesehenen Zugang oder einen sicheren Fehler. Öffentliche BI-Abläufe benötigen keine Proton-Abhängigkeit.

## 4. An den RI-Fetcher anschließen

- [ ] Abhängigkeit mit dem Fetcher-Teilbranch abstimmen. Falls dieser noch fehlt, nur die Zugangsschnittstelle und ihre Tests liefern; echte Anmeldung weiterhin als offen führen.
- [ ] Zugang unmittelbar vor der RI-Anmeldung abrufen; keine Weitergabe an öffentliche BI-Jobs, Suchdienste oder Analysefunktionen.
- [ ] HTTP-Anmeldung gemäß RI-Hauptplan auf erlaubte Hosts begrenzen und Zugangsdaten, Cookies und Token aus Logs und Statusanzeigen ausschließen.
- [ ] Bei Secret- oder Anmeldefehlern den Job vor Dokumentabrufen abbrechen; keine Ausweichanmeldung mit Klartextkonfiguration.

Abnahme: Der Fetcher erhält den Zugang ausschließlich über den Zugangsdienst. Eine erfolgreiche Passwortabfrage allein gilt noch nicht als erfolgreiche RI-Anmeldung.

## 5. Automatisiert prüfen und lokal abnehmen

- [ ] Tests mit künstlichen Geheimnissen und simulierter CLI für Erfolgsfall sowie die Fehlerfälle aus Schritt 3 ergänzen. Reguläre Tests greifen weder auf Proton noch auf das echte RI zu.
- [ ] Mit künstlichen Werten nachweisen, dass weder RI-Passwort noch PAT in Logs, Fehlertexten, Jobstatus, persistenten Dateien oder Prozessargumenten erscheinen und nur der vorgesehene Unterprozess nötige Umgebungswerte erhält.
- [ ] Testen, dass falsche Sitzungsart, unsichere Schlüsselanbieter und fehlende Speicherunterstützung abgewiesen werden. Bestehende öffentliche Abläufe ohne Proton-Konfiguration prüfen.
- [ ] `python -m pytest -m "not integration and not live"` und betroffene Integrationstests ausführen; vor einem PR gemäß Repository-Regeln `python -m pytest` ausführen. Ergebnisse dokumentieren.
- [ ] In jeder unterstützten Umgebung mit Testtoken und Testeinträgen Anmeldung, erneute Anmeldung nach Sitzungsablauf, Neustart, Entzug und Rechtebegrenzung prüfen. Nicht ausgeführte Fälle ausdrücklich offen lassen.
- [ ] Erst mit bereitgestelltem RI-Zugang und geklärtem Loginablauf eine kleine lokale Anmeldung prüfen. Echte Geheimnisse ausschließlich über den geschützten lokalen Einrichtungsweg eingeben, nie im Chat oder Repository.

Abnahme: Automatisierte Tests bestehen; reale Rechtebegrenzung und die unterstützten Betriebsumgebungen sind geprüft. Fehlende RI-Zugangsdaten blockieren nur die reale RI-Abnahme, nicht die unabhängigen Vorarbeiten.

## 6. Betrieb dokumentieren und abschließen

- [ ] Betriebsanleitung für Installation der geprüften CLI-Version, sichere lokale Einrichtung, Eintragsfreigabe, Anmeldung, Token-Erneuerung, Widerruf und Entfernung lokaler Sitzungen erstellen. Beispiele enthalten ausschließlich Platzhalter.
- [ ] Verhalten bei gesperrtem Keyring, Neustart und abgelaufenem Zugang sowie Wiederherstellung auf einem neuen Rechner beschreiben; keine Geheimnisse in ungeschützte Backups aufnehmen.
- [ ] README, `docs/ist_stand.md`, RI-Hauptplan und `docs/plans/project_tasks.md` anhand der tatsächlichen Umsetzung aktualisieren. Beim ersten sichtbaren funktionalen Schritt `VERSION` bewusst anpassen; reine Planung benötigt keinen Versionssprung.
- [ ] Diff auf Geheimnisse, unbeabsichtigte Dateien, funktionierende Dokumentlinks und Whitespace prüfen. Zusammenhängende Commits erstellen und verbleibende Abnahmegrenzen im PR zum Vorhaben-Branch nennen.

## Quellen und offene Entscheidungen

Die Quellen beschreiben den aktuellen Entwicklungsstand; vor Implementierung mit der tatsächlich installierten Version abgleichen:

- [Proton Pass CLI](https://github.com/protonpass/pass-cli)
- [PAT erstellen und Eintragsrechte vergeben](https://github.com/protonpass/pass-cli/blob/main/docs/public/docs/commands/personal-access-token.md)
- [Konfiguration und sichere Schlüsselablage](https://github.com/protonpass/pass-cli/blob/main/docs/public/docs/get-started/configuration.md)
- [Tarifvoraussetzungen für Zugriffstokens](https://proton.me/support/pass-access-tokens)
- [Versionshistorie](https://github.com/protonpass/pass-cli/blob/main/CHANGELOG.md)
- [Feldweiser Eintragsabruf](https://github.com/protonpass/pass-cli/blob/main/docs/public/docs/commands/item.md)
- [Anmeldung und PAT-Sitzungen](https://github.com/protonpass/pass-cli/blob/main/docs/public/docs/commands/login.md)

Offen sind insbesondere Zielumgebung, interaktiver oder unbeaufsichtigter Betrieb, verfügbare Kontofunktionen, konkrete sichere Tokenablage und der echte RI-Anmeldeablauf. Diese Punkte sind Prüfaufgaben, keine bereits zugesicherten Eigenschaften der Anwendung.
