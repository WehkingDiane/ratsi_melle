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
Erstellungsdatum einzelner Unterlagen. Regeln für Nachlauf und automatische Löschung
sind noch nicht implementiert.

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

Nicht unterstützte Sitzungsdetailansichten, etwa bei verschobenen Terminen, werden
als ungeprüft protokolliert und übersprungen. Die übrigen Sitzungen werden weiter
verarbeitet. Login-/Berechtigungsfehler führen zum Abbruch. Ein HTML-Loginformular
wird nicht als Sitzung oder Dokument gespeichert. Dokumentziele sind auf HTTPS
und `/ri/getfile.asp` auf `session.melle.info` begrenzt; unbekannte Ziele werden
abgewiesen. Downloadmeldungen zeigen die Dokument-ID statt der URL.

Gewöhnliche HTTP-Fehler beim Dokumentabruf (z. B. 404 oder 503, auch mit
HTML-Fehlerseite) werden als Dokumentfehler behandelt. HTTP 401/403, HTML statt
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

Die [lokale Web-Datenpflege](oberflaeche.md) steuert diese Skripte seit 0.8.0. Sitzungs- und Dateiansichten,
Aufbewahrung und Bestandsbereinigung sowie ein Bedarfstest des Verwaltungsausschusses
bleiben Teil des [RI-Plans](../plans/ri_ratsbereich_plan.md). Eine RI-Volltext- oder
Vektorindexierung ist nicht vorgesehen. Lokale Dateien und Sicherungen bleiben
unter der Verantwortung des Benutzerkontos; eine getrennte Ablage allein ersetzt
keine Betriebssystem-Zugriffsrechte.

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
