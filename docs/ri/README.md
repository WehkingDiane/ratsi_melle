# Ratsbereich: aktueller Stand

[Dokumentation](../README.md)

Seit 0.7.0 steht der im lokalen Testbereich erprobte RI-Datenablauf als reguläres
CLI-Paket bereit. Der Bestand liegt getrennt unter `data/ri/` und wird nicht von
öffentlichen Datenjobs eingelesen. Seit 0.8.0 lassen sich die Skripte außerdem über die lokale RI-Datenpflege starten. Seit 0.9.0 sind Sitzungsübersicht, TOPs und lokale PDFs im Ratsbereich verfügbar.

- [Zugang einrichten und prüfen](zugang.md)
- [Onlineindex, Dokumentabruf und lokalen Index bedienen](datenablauf.md)
- [Ratsbereich über die Oberfläche bedienen](oberflaeche.md)
- [Weiterer Ausbau und offene Entscheidungen](../plans/ri_ratsbereich_plan.md)

Der RI-Webbereich ist ein erster funktionsfähiger Prototyp für den lokalen Betrieb.
Formulare, Status und Jobausgaben nutzen seit 0.8.1 die BI-Gestaltungselemente; die weitere gemeinsame Nutzung geeigneter Komponenten bleibt offen.
Die Prüfung gemeinsamer Frontend- und Backendteile und ihre Überführung in
wiederverwendbare Komponenten stehen in der [Aufgabenliste](../plans/project_tasks.md).

## Vorhandene Implementierung

`src/config/ri_proton.py` liest den Token aus `.env/ri_token.txt` und stellt genau
die Zugangsdaten des freigegebenen Proton-Logins bereit. Temporäre CLI-Dateisitzungen
ersetzen den OS-Keyring; Zugangsdaten werden nicht versioniert oder ausgegeben.
Die Check-Skripte unter `scripts/setup/` bleiben für die Einrichtung verfügbar.

`src/fetching/ri_login.py` prüft den Anmeldeablauf. `src/fetching/ri_session.py`
verbindet ihn mit dem SessionNet-Metadatentransport und der automatischen Abmeldung.
Die regulären Einstiege sind `scripts/login_ri.py`,
`scripts/build_ri_online_index_db.py`, `scripts/fetch_ri_sessions.py` und
`scripts/build_ri_local_index.py`.

Der Onlineindex enthält sichtbare Metadaten; der lokale Index erfasst tatsächlich
vorhandene Dokumentdateien. Der Abruf übernimmt Dokument-ID und BI-Verlinkung als
Kennzeichnung `öffentlich` oder `nicht öffentlich`. Fehlende oder fehlgeschlagene
BI-Nachweise ergeben `nicht öffentlich`. Ein solcher Eintrag bleibt trotzdem im
RI-Bestand; es gibt keine automatische Übernahme in öffentliche Indizes.
Pfade, Konfiguration, Befehle und Fehlerbehandlung stehen verbindlich in der
[CLI-Anleitung](datenablauf.md).

## Abnahme und Grenzen

Der Prototyp wurde mit echten RI-Abrufen unter Windows und lokalen Builds unter
Windows und WSL geprüft. Bei der Übernahme ins Projekt wurden Rohdateien bytegleich
kopiert, der Onlineindex geprüft und der lokale Index am neuen Ort neu aufgebaut.
Die regulären Skripte sind mit gezielten Offline-Tests geprüft; ein neuer Live-Abruf
mit den verschobenen Skripten wurde bei der Übernahme nicht ausgeführt.

Die entfernte Proton-Abmeldung bleibt unter Windows teilweise unbestätigt und wird
als eigener Warnstatus angezeigt. Neustart-/Ablaufverhalten und unbeaufsichtigter
Betrieb sind nicht abgenommen. Web-Skriptsteuerung sowie Sitzungs- und Dateiansichten
sind mit synthetischen Daten geprüft. Bestandsbereinigung und die vollständige
Bedarfsabnahme des Verwaltungsausschusses bleiben offen. RI-Volltext- und
Vektorindexierung sind nicht Teil dieser Ausbaustufe. Historische Änderungen stehen
im [Changelog](../../CHANGELOG.md).
