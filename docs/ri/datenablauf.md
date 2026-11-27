# RI-Daten per CLI abrufen und lokal indexieren

[RI-Übersicht](README.md) · [Zugang einrichten](zugang.md)

## Zweck und Voraussetzungen

Die RI-Skripte erfassen Sitzungsmetadaten, laden verlinkte Dokumente und bauen eine
Datenbank der tatsächlich lokal vorhandenen Dateien. Der Ablauf ist für manuell
gestartete lokale Nutzung vorgesehen. Für Onlineindex und Download wird der gültige
Token aus der [Zugangsanleitung](zugang.md) benötigt. Der lokale Build läuft offline.
Alle Befehle gelten aus dem Repository-Stamm.

## Ablauf

Optional die Anmeldung ohne Dokumentabruf prüfen:

```powershell
python scripts/login_ri.py
```

Anschließend die gewünschten Monate abrufen und lokal indexieren:

```powershell
python scripts/build_ri_online_index_db.py 2026 --months 11
python scripts/fetch_ri_sessions.py 2026 --months 11
python scripts/build_ri_local_index.py
```

Onlineindex und Dokumentabruf können unabhängig voneinander gestartet werden.
Der Onlineindex enthält sichtbare Portalmetadaten, auch wenn keine Datei lokal
vorliegt. Der lokale Index enthält ausschließlich vorhandene, nicht leere Dateien
innerhalb des jeweiligen RI-Sitzungsordners. Jeder Online-Aufruf meldet sich einmal
an und versucht anschließend RI- und Proton-Abmeldung, auch nach Fehlern.
Es werden keine dauerhaften HTTP-Cookies gespeichert.

## Pfade und Konfiguration

| Inhalt | Standardpfad |
| --- | --- |
| RI-Bestand | `data/ri/` |
| Kalender, Sitzungsseiten, TOPs, Manifeste und Dokumente | `data/ri/raw/YYYY/MM/` |
| Onlineindex | `data/ri/db/online_session_index.sqlite` |
| Lokaler Dokumentindex | `data/ri/db/local_index.sqlite` |
| RI-Protokolle | `logs/ri/<skriptname>.log` |
| Standard-Abrufgrenze | `src/config/ri.json` |
| Optionale lokale Konfiguration | `data/ri/config.json` |

Die RI-Wurzel liegt unter `data/ri/`. RI-Laufzeitdaten,
Zugangsdaten und Protokolle werden nicht versioniert. Sie liegen außerhalb der
öffentlichen Rohdaten- und Datenbankpfade und werden nicht in öffentliche Suche,
Exporte oder Oberfläche eingebunden. Auch als öffentlich gekennzeichnete RI-Dateien
bleiben im RI-Bestand.

Die lokale Konfiguration ersetzt bei Vorhandensein die Standardkonfiguration:

```json
{"earliest_month": "2026-11"}
```

Onlineindex und Download schließen frühere Sitzungsmonate vor der Anmeldung aus.
Ohne `--months` werden alle zugänglichen Monate des Jahres gewählt; für 2026 sind
das November und Dezember. Ohne verbleibenden Monat oder bei ungültiger
Konfiguration bricht der Aufruf ab. Die Grenze betrifft Sitzungsmonate, nicht das
Erstellungsdatum einzelner Unterlagen. Die manuelle Verwaltung des Bestands ist
unter [Aufbewahrung und manuelles Löschen](#aufbewahrung-und-manuelles-löschen) festgelegt.

## Dokument-ID und Öffentlichkeitskennzeichnung

Vor dem Dokumentdownload wird die BI-Seite derselben Sitzung ohne RI-Anmeldecookies
gelesen. Der Abgleich verwendet die Dokument-ID aus dem `getfile.asp`-Link und lädt
keine zusätzlichen BI-Dokumentdateien. Jeder Dokumenteintrag im Manifest enthält
neben der URL:

- `document_id`: Dokument-ID als Zeichenfolge, sonst `null`.
- `visibility`: `öffentlich`, wenn die ID im BI verlinkt ist; sonst `nicht öffentlich`.
- `visibility_checked_at`: Zeitpunkt des Abgleichs.
- `bi_comparison_status`: `erfolgreich` oder `fehlgeschlagen`.

Bei fehlgeschlagenem BI-Abgleich werden alle Dokumente der Sitzung als
`nicht öffentlich` gekennzeichnet; der RI-Abruf läuft weiter. Ein öffentlicher TOP
ändert diese Regel nicht. Die Kennzeichnung beschreibt die BI-Verlinkung, keine
inhaltliche oder rechtliche Bewertung. Beim erneuten Downloadlauf werden auch
Einträge wiederverwendeter Dateien neu gekennzeichnet. Der aktuelle Abruf übernimmt
die verlinkten Sitzungs- und TOP-Dokumente einschließlich Einladungen; eine feinere
Auswahl nach Dokumentart ist noch nicht umgesetzt.

Der lokale Index übernimmt diese Felder aus dem Manifest und führt keinen neuen
BI-Abgleich aus. Fehlende Kennzeichnungen ergeben `nicht öffentlich`. Die interne
SQLite-Spalte `id` bleibt vom SessionNet-Feld `document_id` getrennt.
`session_path` wird für den regulären Bestand relativ zum Repository-Stamm gespeichert,
damit Windows und WSL denselben Index verwenden können. `local_path` ist relativ
zu diesem Sitzungsordner aufzulösen. Für die Datenbank dürfen
veraltete Metadaten aus gespeichertem Sitzungs-HTML neu geparst werden; bestehende
Dateizuordnungen und Kennzeichnungen bleiben dabei erhalten. Rohdateien und
Manifeste werden durch den Build nicht verändert.

## Wiederholen und Aktualisieren

```powershell
python scripts/fetch_ri_sessions.py 2026 --months 11 --force-download
python scripts/build_ri_online_index_db.py 2026 --months 11 --refresh-existing
python scripts/build_ri_local_index.py --refresh-existing
python scripts/build_ri_local_index.py --only-refresh
```

`--force-download` lädt auch vorhandene Dateien abgeschlossener Sitzungen erneut.
Beide Builder unterstützen `--refresh-existing` und `--only-refresh`: Ersteres
aktualisiert bekannte Sitzungen und fügt neue hinzu, Letzteres aktualisiert nur
bereits indexierte Sitzungen. Beim lokalen Build lösen geänderte Metadaten und
entfernte Dokumentdateien automatisch eine Aktualisierung aus. Unveränderte
Sitzungen werden übersprungen; `Indexed sessions=0` zählt nur diesen Lauf und
bedeutet keine leere Datenbank. Sitzungen ohne Dokumente werden erneut geprüft.

Online- und Local-Builder akzeptieren `--output` nur innerhalb der RI-db-Wurzel
und schützen die jeweilige andere Standarddatenbank. Der Local-Builder akzeptiert
`--data-root` nur innerhalb der RI-Rohdatenwurzel; die Quelle muss Jahresordner mit
Monats- und Sitzungsunterordnern enthalten. Der Online-Builder kann mit dem
optionalen `--migrate-from` eine vorhandene RI-Onlinedatenbank übernehmen, wenn
sein Ziel fehlt. Eine lokale Dokumentdatenbank wird nicht automatisch kopiert.
Alle drei Datenskripte unterstützen `--log-level`.

## Fehler und Grenzen

Bekannte verschobene/abgesagte Termine werden als Kalenderstatus erfasst und ohne
Dokumentabruf verarbeitet. Eine eng geprüfte `si0050.asp`-Terminansicht mit explizitem
Änderungshinweis wird ebenfalls als Status erfasst. Nicht unterstützte oder unklare
Detailansichten bleiben ungeprüft und werden übersprungen; die übrigen Sitzungen
werden weiter verarbeitet. Login-/Berechtigungsfehler führen zum Abbruch. Die 90-Sekunden-Frist für die
RI-Anmeldung beginnt erst, wenn die Zugangsdaten aus Proton vorliegen. Ein HTML-Loginformular
wird nicht als Sitzung oder Dokument gespeichert. Dokumentziele sind auf HTTPS
und `/ri/getfile.asp` auf `session.melle.info` begrenzt; unbekannte Ziele werden
abgewiesen. Downloadmeldungen zeigen die Dokument-ID statt der URL.

Gewöhnliche HTTP-Fehler beim Dokumentabruf (z. B. 404 oder 503, auch mit
HTML-Fehlerseite) und Verbindungsfehler beim Download werden als Dokumentfehler
behandelt. Scheitert die Abfrage der Dateiinformationen (HEAD) an der Verbindung,
wird der Download direkt versucht. HTTP 401/403, HTML statt
eines Dokuments bei HTTP 200 und unzulässige Weiterleitungen führen weiterhin
zum Abbruch wegen fehlender oder ungeklärter Zugriffsberechtigung.

Exitcodes der Online-Aufrufe: `0` erfolgreich, `1` Abbruch, `2` ungeprüfte Sitzungen,
fehlgeschlagene Dokumentdownloads oder unbestätigte Abmeldung. Dokumentfehler, etwa
wegen Größenüberschreitung oder erschöpfter Stream-Wiederholungen, stoppen die
übrigen Downloads nicht. Die betroffene Sitzung zählt als unvollständig; Protokoll
und Abschlussmeldung nennen Sitzungs- und Dokument-ID. Ein vorhandener alter
Manifest-Eintrag bleibt bei einem fehlgeschlagenen Download erhalten; ein neues
Dokument wird erst nach erfolgreichem Download eingetragen. Der Teilstatus gilt
für den aktuellen Lauf und wird bei einem erfolgreichen Wiederholungslauf aufgehoben. Ein fehlgeschlagener BI-Abgleich wird als Warnung im
Protokoll und im Manifest festgehalten. Der lokale Build liefert `0` bei Erfolg
und `1` bei Abbruch; fehlende oder unzulässige Dateien werden mit Warnung
übersprungen. Teilstände können mit demselben Aufruf erneut verarbeitet werden.
Die bekannte unbestätigte entfernte Proton-Abmeldung bleibt ein eigener Warnstatus.

Die [lokale Web-Datenpflege](oberflaeche.md) steuert diese Skripte seit 0.8.0;
Sitzungs- und Dateiansichten sind ebenfalls angebunden. Die begrenzte reale
[UI-Abnahme](oberflaeche.md#reale-ui-abnahme-vom-22112026) umfasst auch den Verwaltungsausschuss.
Weitere Aufgaben stehen im [aktuellen RI-Aufgaben](../plans/project_tasks.md). Eine RI-Volltext-
oder Vektorindexierung ist nicht vorgesehen. Lokale Dateien und Sicherungen bleiben
unter der Verantwortung des Benutzerkontos; eine getrennte Ablage allein ersetzt
keine Betriebssystem-Zugriffsrechte.

## Kalenderstatus

Seit 0.10.0 trennen BI und RI den Kalenderstatus von Uhrzeit und Ort. Die
Sitzungs-ID und das ursprüngliche Datum bleiben erhalten. Die Felder
`calendar_status`, `calendar_note`, `rescheduled_date`, `replacement_session_id`
und `calendar_observed_at` werden in Manifest-/Kalenderdaten und den jeweiligen
Sitzungsindizes gespeichert. Bestehende Tabellen erhalten zusätzliche Spalten;
bestehende Dokumente und TOPs werden durch reine Statusänderungen nicht entfernt.
Statuswerte sind `scheduled`, `postponed`, `cancelled` und `unknown`.

Zeigt die RI-Monatsübersicht einen zuvor geänderten Termin wieder als geplant,
prüft der Onlinebuilder die Detailseite auch ohne `--refresh-existing` erneut.
Ein dort bestätigter Änderungsstatus bleibt erhalten, solange keine reguläre
Detailansicht die Rückkehr bestätigt. Fehlt die Detail-URL oder ist die Seite nicht
auswertbar, bleiben Status und vorhandene Unterlagen erhalten. Sobald reguläre
Details verfügbar sind, werden sie beim normalen Build übernommen.

Eine Ersatz-ID wird nur aus einem expliziten Verweis übernommen; übereinstimmende
Gremiennamen und Datumsangaben erzeugen keine automatische Verbindung. Bekannte
Varianten wie „abgesagt“, „findet nicht statt“ und „verschoben auf den …“ werden
verstanden. Bei unklaren Hinweisen bleibt der Originaltext sichtbar. Ein
Ersatzdatum ohne neue ID ermöglicht noch keinen direkten Link zur neuen Sitzung.

Der lokale Builder übernimmt Änderungen auch aus gespeicherten Monatskalendern.
Er kann geänderte Kalendereinträge ohne Sitzungsordner als Metadaten aufnehmen;
vorhandene Dokumenteinträge bleiben erhalten. `--only-refresh` fügt auch dabei
keine neuen Sitzungen hinzu. Statusseiten-Ergebnisse eines RI-Downloads werden
in `calendar_changes.json` neben dem betreffenden Monatskalender abgelegt und
nur übernommen, wenn dessen SHA-256 noch zur gespeicherten Quelle passt. Diese
Datei enthält Kalenderinformationen, keine Zugangsdaten oder Dokumentdateien.

Die [Sitzungsübersicht](../oberflaeche/sitzungen.md) beschreibt die Anzeige.
Öffentliche Suche und Exporte bleiben auf ihren eigenen Bestand begrenzt;
der RI-Kalender wird nur für den lokalen gemeinsamen Überblick verwendet.

## Aufbewahrung und manuelles Löschen

Festlegung des Nutzers vom 27.11.2026: Die bisherige RI-Datenhaltung bleibt bestehen.
Der Nutzer entscheidet selbst über die Aufbewahrung und löscht Dokumente manuell.
Eine automatische Bereinigung, automatische altersabhängige Löschung oder weitere
Bewertung von Aufbewahrungs-/Löschfristen ist nicht vorgesehen. Diese Punkte sind
keine offenen Ausbau- oder Abnahmekriterien. Die bestehende Abrufuntergrenze
`earliest_month` wird dadurch nicht geändert.

Dateilöschung und lokale Indexaktualisierung bleiben getrennte Vorgänge. Der
vorhandene lokale Builder berücksichtigt fehlende Dateien in noch vorhandenen
Sitzungsordnern beim nächsten Aufbau. Vollständig entfernte Sitzungsordner werden
aktuell nicht automatisch aus der Datenbank entfernt. PDF-Links prüfen zusätzlich,
ob die Datei noch vorhanden ist. Das beschreibt den bestehenden Stand; es wird
keine neue Lösch- oder Bereinigungsfunktion eingeführt.

## Übernahme des bisherigen Testbestands

Der zuvor unter `tmp/ri/` erprobte Bestand wurde lokal in die RI-Wurzel
kopiert. Rohdateien und Manifeste wurden bytegleich geprüft, der Onlineindex per
SQLite-Backup übernommen und der lokale Index am neuen Ort neu aufgebaut.
Die bisherigen Dateien unter `tmp/` bleiben als Rückfallebene bestehen und werden
von den regulären Skripten nicht mehr verwendet. Diese lokale Datenübernahme ist
nicht Bestandteil des Git-Commits und wird auf anderen Rechnern nicht automatisch
ausgeführt. Weitere Systeme beginnen mit einem regulären Abruf oder übernehmen
ihren eigenen privaten Datenbestand entsprechend.

Gezielte Offline-Tests stehen in der [Testdokumentation](../entwicklung/tests.md).
