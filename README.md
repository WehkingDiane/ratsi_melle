# Ratsi Melle

Die Anwendung sammelt **öffentliche** Sitzungs- und Dokumentdaten aus dem Bürgerinformationssystem der Stadt Melle (`/bi/`) und Veröffentlichungen des Landkreises Osnabrück. Sie erstellt lokale SQLite-Indizes, bietet semantische Suche und eine Django-Oberfläche für Datenpflege und Analyse. Der geschützte Ratsbereich (`/ri/`) ist derzeit geplant und noch nicht implementiert.

Der [Ist-Stand](docs/ist_stand.md) beschreibt Quellen, Datenhaltung, Suche und Oberfläche. Der [RI-Plan](docs/plans/ri_ratsbereich_plan.md) ist das einzige aktuelle Ausbauvorhaben.

## Voraussetzungen und Start

Python 3.14, pip und Git werden empfohlen. Für die Oberfläche wird Tkinter nicht benötigt. Unter WSL kann `.venv-wsl` verwendet werden; falls `python` fehlt, `python3` beziehungsweise `.venv-wsl/bin/python` nutzen.

```bash
pip install -r requirements.txt
python scripts/run_web.py
```

Die lokale Django-Oberfläche ist danach unter `http://127.0.0.1:8000/` erreichbar. Sie ist aktuell für lokale Entwicklung konfiguriert und besitzt keine Benutzeranmeldung.

## RI-Schlüsselspeicher prüfen (Vorbereitung)

Ab Version 0.5.69 führt ein Skript durch die lokale Speicherprüfung. In der aktivierten Python-Umgebung unter Windows oder Linux/WSL als normaler Benutzer starten:

```bash
python scripts/setup/setup_ri_secret_storage.py
```

Unter WSL alternativ `.venv-wsl/bin/python scripts/setup/setup_ri_secret_storage.py` verwenden. Voraussetzung ist die vorhandene Projektabhängigkeit `keyring`; fehlt unter Ubuntu/WSL GNOME Keyring, einmal `sudo apt install gnome-keyring` ausführen.

Bei Problemen unter WSL liefert `python scripts/setup/setup_ri_secret_storage.py --check` ohne Passworteingabe den aktuellen Sperr-/Erreichbarkeitsstatus. Dieser Modus startet keinen Dienst, entsperrt nichts und greift auf keine gespeicherten Passwörter zu. Die Fehlerausgabe unterscheidet fehlende Python-Unterstützung, gesperrten oder fehlenden Login-Speicher, unerreichbaren Dienst und verweigerten Zugriff; native Fehlertexte werden nicht ausgegeben.

Unter Windows prüft das Skript den Windows Credential Manager. Unter Linux startet es GNOME Keyring und fragt verdeckt nach dem Passwort des lokalen Login-Schlüsselspeichers. Bei vorhandenem Speicher dessen bisheriges Passwort verwenden; bei neuem Speicher ein starkes, nicht leeres Passwort wählen. Kein Proton-Passwort, RI-Passwort oder Token eingeben. Die Eingabe zeigt keine Zeichen; bei einer Fehlermeldung wird das Passwort nicht ausgegeben.

Das Skript speichert, liest und entfernt einen eigenen Zufallswert. Bestehende Einträge werden nicht verändert. Bei Fehlern oder Zeitüberschreitung bricht es ab, ohne auf Klartextspeicher auszuweichen. Bei einem unterbrochenen Test kann ein harmloser Eintrag mit Präfix `ratsi_melle_storage_test_` zurückbleiben. Ein erfolgreicher Lauf bestätigt nur die Nutzbarkeit in dieser Sitzung, nicht das Verhalten nach einem Neustart, eine Proton-Anmeldung oder die Verschlüsselung eines bereits früher angelegten Schlüsselspeichers. Der Schlüsselspeicher darf nicht mit leerem Passwort eingerichtet werden.

Das Skript hinterlegt keinen PAT, konfiguriert keine Proton-Sitzung und aktiviert keinen RI-Abruf. Die lokale Einrichtung ist abgeschlossen; das weitere Vorhaben steht im [RI-Hauptplan](docs/plans/ri_ratsbereich_plan.md).

## RI-Proton-Token hinterlegen oder ersetzen

In der aktivierten Python-Umgebung als normaler Benutzer ausführen:

```bash
python scripts/setup/store_ri_proton_token.py
```

Unter WSL alternativ `.venv-wsl/bin/python scripts/setup/store_ri_proton_token.py` verwenden. Voraussetzung ist der erfolgreich geprüfte, entsperrte lokale Speicher. Falls der Login-Speicher unter WSL gesperrt ist, zuerst die oben beschriebene Speicherhilfe starten.

Den vollständigen Proton-Pass-Zugriffstoken bei der unsichtbaren Eingabe einfügen und Enter drücken. Das Skript speichert unter Dienst `ratsi_melle_ri` und Benutzername `proton_pass_pat` im Windows Credential Manager beziehungsweise im GNOME-Login-Speicher. Ein dort vorhandener Token wird ersetzt; mit demselben Aufruf kann später ein neuer Token hinterlegt werden. Windows und WSL haben getrennte Speicher, sodass die Ablage auf jedem Zielsystem separat erfolgt.

Es werden nur das lokale Format und das erfolgreiche Schreiben/Lesen geprüft, nicht Ablaufdatum, Gültigkeit oder Proton-Berechtigungen. Vereinbart ist ein eigener freigegebener RI-Tresor mit einem Eintrag und ausschließlich lesender Anwendungscode. Die serverseitigen Schreibrechte des Tokens sind unbekannt; die eigene Sicherung in einem anderen Tresor wird nicht angesprochen. Es werden keine Schreibproben an echten Einträgen ausgeführt. Die Ablage startet keine Proton-Anmeldung und keinen RI-Abruf. Der Token wird nicht angezeigt und weder als Prozessargument oder Umgebungswert noch als Klartextdatei übergeben. Bei Zeitüberschreitung oder Schreib-/Prüffehler ist die Speicherung nicht bestätigt; sie kann bereits erfolgt sein und muss nach Behebung erneut ausgeführt werden. Die Anwendung benutzt keinen Klartext-Fallback.

Die Zielversion der ersten Ausbaustufe ist Proton Pass CLI 2.7.0 (`ba80a19`) unter Windows und WSL. Vorgesehen sind manuell gestartete lokale Abrufe. Unbeaufsichtigte Jobs sind noch nicht abgenommen; Neustart-/Entsperrverhalten und Token-/Sitzungsablauf bleiben zu prüfen.

## RI-Proton-Anmeldung testen

Nach erfolgreicher Tokenablage in derselben Windows-/WSL-Umgebung:

```bash
python scripts/setup/check_ri_proton_login.py
```

Das Skript liest ausschließlich den hinterlegten RI-PAT und übergibt ihn kurzzeitig über die Umgebung an den Login-Unterprozess. Es verwendet eine neue temporäre Sitzung mit erzwungenem CLI-Keyring-Backend (unter Linux D-Bus), unabhängig von einer persönlichen CLI-Anmeldung. Nach erfolgreichem Login zeigt `pass-cli vault list --output human` die für diesen Token sichtbaren Tresore einschließlich ihrer Namen/IDs. Das sind Tresore, keine einzelnen Login-Einträge oder Passwörter. Tresor- und Passwortänderungen werden nicht ausgeführt.

Nach jedem Versuch wird die Testsitzung abgemeldet. Scheitert das, meldet das Skript eine feste Fehlerkategorie und versucht `logout --force` für die lokale Bereinigung derselben Sitzung. Das bestätigt keine entfernte Abmeldung; die Sitzung kann bis zum Ablauf bestehen bleiben. Das temporäre Verzeichnis wird danach entfernt. Exitcode 0 bestätigt den gesamten Ablauf, 2 eine erfolgreiche Anmeldung/Tresorauflistung mit nur lokal bestätigter Bereinigung, 1 einen Test- oder Bereinigungsfehler. Ein separat aufgerufenes `pass-cli logout` verwendet normalerweise die Standardsitzung, nicht diese Testsitzung. Eine dauerhafte RI-Laufzeitsitzung wird nicht eingerichtet. Zeitgrenzen: Anmeldung 45, Tresorauflistung 30, normale Abmeldung 30 und erzwungene lokale Bereinigung zehn Sekunden.

Nur die ausdrücklich angeforderte erfolgreiche Tresorliste wird angezeigt; sonstige CLI-Ausgaben und native Fehlertexte bleiben intern. Der vollständige Token wird aus der Tresorlistenausgabe ausgeblendet; Terminal-Steuerzeichen werden entfernt. Das Skript fordert keine Passworteinträge an; Gültigkeit des Tokens wird durch den Login geprüft, der gezielte Abruf des fest konfigurierten RI-Eintrags und die ausschließliche Nutzung erlaubter Lesebefehle bleiben im Zugangsdienst umzusetzen und zu prüfen. Der Aufruf führt keine RI-Anmeldung durch. Unter WSL muss der lokale Login-Schlüsselspeicher entsperrt und der Token dort separat hinterlegt sein.

## Gezielten Zugriff und RI-Anmeldung prüfen

Ab Version 0.5.75 kann der einzige freigegebene Proton-Eintrag lokal fest gebunden und die RI-Anmeldung getrennt vom Datenabruf geprüft werden. Zuerst pro Betriebssystem einmal ausführen:

```bash
python scripts/setup/check_ri_access.py --configure
```

Dafür sind genau ein sichtbarer Tresor und genau ein aktiver Login-Eintrag erforderlich. Es werden nur dessen Referenz-IDs gespeichert: unter Windows in `%LOCALAPPDATA%/ratsi_melle/ri_proton_access.json`, unter WSL in `~/.local/share/ratsi_melle/ri_proton_access.json`. Die Datei enthält keine Benutzernamen oder Passwörter. Eine bestehende abweichende Bindung wird nicht automatisch ersetzt. Ein später hinzugefügter aktiver Eintrag oder ein weiterer freigegebener Tresor blockiert den Abruf.

Danach den eigentlichen Anmeldetest starten:

```bash
python scripts/setup/check_ri_access.py
```

Unter WSL jeweils `.venv-wsl/bin/python` statt `python` verwenden. Der Token wird aus dem lokalen OS-Speicher gelesen. Der Zugangsdienst erlaubt nur die vorgesehenen Metadatenabfragen und das Lesen von Benutzername (ersatzweise E-Mail) und Passwort des fest gebundenen Eintrags. Er gibt keine Zugangsdaten aus und erlaubt keine frei übergebenen Proton-Befehle.

Das feste Testziel ist `https://session.melle.info/ri/`. Der Test liest das öffentliche Anmeldeformular und sendet den Zugang genau einmal an den geprüften RI-Anmeldeendpunkt. Passwortänderung und Kennwort-Wiederherstellung werden nicht ausgewählt. HTTPS, Host und Zielpfade werden vor Weiterleitungen geprüft; Wiederholung eines Passwort-POST bei 307/308 wird abgelehnt. Es gibt keine automatischen Anmeldewiederholungen.

Der beobachtete Ablauf nutzt nach dem POST `ylogonstart.asp` und kann HTML-Meta-Weiterleitungen enthalten. Der Formularparameter `logongopn` erhält den Seitennamen `info` ohne `.asp`. Die reine Abschlussseite `smc_end.asp` nach der Abmeldung wird nicht angefordert; stattdessen wird der geschützte Einstieg erneut geprüft.

Eine HTTP-200-Antwort allein gilt nicht als Erfolg: Die geschützte Einstiegsseite muss einen erkannten Abmeldelink enthalten. Danach wird die RI-Abmeldung über erneute Prüfung des geschützten Einstiegs bestätigt. Der Test lädt keine Sitzungen oder Dokumente herunter und schreibt weder HTML noch HTTP-Cookies auf Platte. Eine möglicherweise notwendige zusätzliche Anmeldung, Passwortänderung oder ein verändertes Formular führt zum Abbruch. Bei einem Abbruch nach dem Passwortversand kann eine entfernte RI-Sitzung bis zu ihrem Ablauf bestehen bleiben; lokale Cookies werden verworfen. Der BI-Abruf und die öffentliche Datenhaltung werden nicht verwendet.

Die Proton-Sitzung wird anschließend separat beendet; eine nicht bestätigte normale Proton-Abmeldung ergibt wie beim bisherigen Test einen Hinweis mit Status 2. Der vollständige echte Test ist unter WSL und Windows bestätigt: gezielter Zugangsfeldabruf, RI-Anmeldung, RI-Abmeldung und anschließende Zugangssperre. Die Referenz ist auf beiden Systemen separat eingerichtet. Unter Windows bleibt der bereits bekannte Hinweis zur nachfolgenden Proton-Abmeldung (Status 2); die RI-Abmeldung selbst ist dort erfolgreich bestätigt. Die Umsetzung enthält noch keinen RI-Dokumentabruf, RI-Index oder Webzugang.

## Daten aufbauen

Die SessionNet-Skripte für den öffentlichen Bürgerinformationsbereich tragen `bi` im Namen. RI-Abrufskripte sind noch nicht vorhanden; für die vorbereitende Speicherprüfung gibt es die unten beschriebene Einrichtungshilfe. Seit Version 0.5.63 gelten folgende Umbenennungen; eigene Automatisierungen müssen die neuen Namen verwenden:

| Bisher | Neu |
| --- | --- |
| `fetch_sessions.py` | `fetch_bi_sessions.py` |
| `fetch_session_from_index.py` | `fetch_bi_session_from_index.py` |
| `build_online_index_db.py` | `build_bi_online_index_db.py` |
| `build_local_index.py` | `build_bi_local_index.py` |
| `build_vector_index.py` | `build_bi_vector_index.py` |
| `check_vector_index.py` | `check_bi_vector_index.py` |
| `update_vector_index.py` | `update_bi_vector_index.py` |
| `evaluate_search.py` | `evaluate_bi_search.py` |

Landkreis-Skripte behalten ihre eindeutigen Namen. Gemeinsame Werkzeuge wie `prepare_embedding_models.py`, `migrate_legacy_index.py` und `run_web.py` bleiben neutral benannt. Die Weboberfläche verwendet die neuen Skriptpfade; bestehende Job-Aktionskennungen bleiben erhalten.

```bash
# Öffentliche SessionNet-Daten und Indizes
python scripts/fetch_bi_sessions.py 2024 --months 5 6
python scripts/build_bi_online_index_db.py 2024 --months 5 6
python scripts/fetch_bi_session_from_index.py --list --from-date 2026-04-01 --to-date 2026-04-30
python scripts/fetch_bi_session_from_index.py --session-id 7128
python scripts/build_bi_local_index.py

# Lokale Suchmodelle und Ratsinfo-Vektorindex
python scripts/prepare_embedding_models.py --download
python scripts/build_bi_vector_index.py

# Landkreis-Veröffentlichungen
python scripts/fetch_landkreis_publications.py --source all
python scripts/build_landkreis_publications_db.py
python scripts/build_landkreis_vector_index.py
```

Die Befehle sind Beispiele. Fetch-Jahr, Monate und Sitzungs-ID müssen zum gewünschten Datenbestand passen. Die Weboberfläche bietet die entsprechenden Datenjobs unter `/daten/`. Die Suche liegt unter `/suche/`; die SQLite-Suche für Landkreis-Daten ist außerdem mit `python scripts/search_landkreis_publications.py "Melle Genehmigung"` nutzbar.

Standardmäßig verwendet die Suche Qdrant unter `http://127.0.0.1:6333`. Ein anderer Server kann mit `RATSI_QDRANT_URL` gewählt werden. Für lokalen Speicher ohne Server `RATSI_QDRANT_MODE=local` setzen und `RATSI_QDRANT_URL` frei lassen. Vor dem Vektorbuild müssen die lokalen Modelle vorbereitet sein.

Die [Index-Kompatibilität](docs/index_compatibility.md) beschreibt die Weiterverwendung des bestehenden Ratsinfo-Index mit den am 03.11.2026 akzeptierten Windows-Modellbibliotheken. Der normale Aufbau ergänzt weiterhin nur fehlende oder unvollständige Dokumente.

Die Vektorstatusanzeige zeigt die Dokumentabdeckung aus dem letzten Build. Einmalig nach einem bestehenden Aufbau können die Zahlen mit `python scripts/check_bi_vector_index.py --update-status` gespeichert werden; der Vektorindex bleibt dabei unverändert.

## Lokale Daten

Öffentliche SessionNet-Rohdaten liegen unter `data/raw/YYYY/MM/`, Landkreis-Rohdaten unter `data/raw/landkreis/`. SQLite-Dateien liegen unter `data/db/`, private Prompt-Dateien unter `data/private/`, Analyseausgaben unter `data/analysis_outputs/`. Diese Laufzeitdaten und Geheimnisse werden nicht versioniert. Die Struktur der Analyseartefakte steht in [Analyseausgaben](docs/analysis_outputs.md).

## Tests gezielt ausfuehren

Die Marker `integration` und `live` sind in `pyproject.toml` registriert. `integration` prüft das Zusammenspiel mehrerer Komponenten mit lokalen oder simulierten Abhängigkeiten. `live` benötigt echte Dienste, Modelle oder nicht versionierte Quelldaten und ist im normalen Lauf ausgeschlossen.

Die regulären RI-/Proton-Tests verwenden ausschließlich erfundene Tokens und Zugangsdaten sowie simulierte Schlüsselspeicher, CLI-Aufrufe und HTTP-Antworten. Sie lesen keine echten Tokens und melden sich weder bei Proton noch beim RI an. Die manuell gestarteten Prüfskripte unter `scripts/setup/` greifen dagegen auf den eingerichteten lokalen Speicher und die echten Dienste zu.

```bash
python -m pytest -m "not integration and not live"
python -m pytest -m "integration and not live"
python -m pytest
```

## Dokumentation

- [Ist-Stand](docs/ist_stand.md): vorhandene Datenflüsse, Speicherorte, Suche und Oberfläche
- [RI-Plan](docs/plans/ri_ratsbereich_plan.md): einziges aktuelles Ausbauvorhaben
- [Aktuelle Aufgaben](docs/plans/project_tasks.md): Arbeitspakete des RI-Vorhabens
- [Repository-Regeln](docs/repository_guidelines.md) und [Agentenregeln](AGENTS.md)
- [UI-Regeln](docs/ui_guidelines.md) und [Analyseausgaben](docs/analysis_outputs.md)

## Navigation der Weboberfläche

Seit 0.5.64 gliedert sich die Oberfläche in Übersicht, Bürgerinformation, Ratsbereich,
Landkreis, Erweiterungen und Einstellungen. Bürgerinformation und Landkreis haben
getrennte Einstiege für Suche und Datenpflege. Bestehende URLs bleiben erreichbar.
Analyse liegt unter Erweiterungen; Wartung und Konfiguration unter Einstellungen.
Der Ratsbereich zeigt vorerst informative Platzhalter und verarbeitet keine
Zugangsdaten oder internen Unterlagen. Hauptbereiche stehen wie im Dashboard
untereinander.
