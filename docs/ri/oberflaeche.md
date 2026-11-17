# RI-Skripte über die Oberfläche bedienen

[RI-Übersicht](README.md) · [CLI-Datenablauf](datenablauf.md)

Seit 0.8.0 lassen sich die RI-Skripte in der lokalen Django-Oberfläche starten.
Dafür gibt es eine eigene Anmeldung und eine getrennte RI-Jobhistorie. Die
öffentliche Suche und Datenpflege benötigen weiterhin keine Anmeldung.

## Einmalige Einrichtung

Im Repository-Stamm mit der passenden Python-Umgebung ausführen:

```powershell
python web/manage.py migrate
python web/manage.py createsuperuser
python scripts/run_web.py
```

Benutzername und Passwort beim interaktiven Einrichten selbst wählen. Das Passwort
wird von Django als Hash gespeichert. `createsuperuser` erzeugt ein aktives Konto
mit Mitarbeiterstatus. Nur aktive Konten mit diesem Status dürfen RI-Datenpflege,
Jobdetails und Statusabfragen verwenden. Die Befehle richten keine Portalzugangsdaten
ein und starten keine RI-Downloads.

Die Anmeldung unter `/ratsbereich/anmelden/` verwendet dieses lokale Webkonto,
nicht das Portalpasswort. Für Online-Aufträge muss der bestehende
[RI-Portalzugang](zugang.md) separat eingerichtet sein. Portalpasswort und Token
werden nicht in Webformulare eingegeben oder als Auftragsparameter angenommen.

Die Oberfläche bleibt für den lokalen Entwicklungsbetrieb auf `127.0.0.1`
konfiguriert. `RATSI_WEB_SECRET_KEY` kann einen eigenen stabilen Django-Schlüssel
bereitstellen. Ohne diese Variable wird pro Serverstart ein zufälliger Schlüssel
verwendet; bisherige Anmeldungen werden dadurch bei einem Neustart ungültig.
Browser-Schließen und eine begrenzte Sitzungsdauer beenden den lokalen Webzugang.
Netzwerkbereitstellung und Mehrbenutzerbetrieb benötigen weiterhin eine gesonderte
Betriebskonfiguration und Abnahme; `run_web.py` startet einen Entwicklungsserver.

## Seiten und Aktionen

Nach der Anmeldung über **Ratsbereich** die gewünschte Seite öffnen:

| Seite | Aktion |
| --- | --- |
| Zugang | `login_ri.py`: Portalzugang prüfen und anschließend wieder abmelden |
| Unterlagen herunterladen | `fetch_ri_sessions.py`: gewählte Sitzungsmonate und Dokumente abrufen |
| Datenbank aktualisieren | `build_ri_online_index_db.py`: Online-Metadaten erfassen |
| Datenbank aktualisieren | `build_ri_local_index.py`: vorhandene Dateien lokal indexieren |
| Datenstatus und Jobs | RI-Datenbankstatus und private Auftragshistorie ansehen |

Jahr und Monate folgen der [Abrufkonfiguration](datenablauf.md#pfade-und-konfiguration).
Ohne Monatsangabe werden die zugänglichen Monate des Jahres gewählt; frühere
Monate werden ausgeschlossen. Ungültige Angaben werden im Formular angezeigt.
Der Download bietet die Option zum erneuten Herunterladen vorhandener Dokumente;
die Builder bieten Aktualisierung bekannter Sitzungen beziehungsweise ausschließlich
bekannter Sitzungen. Die genaue CLI-Semantik steht in der Datenablaufanleitung.

Erst das Absenden eines Formulars startet einen Auftrag. Die Oberfläche öffnet
danach dessen Detailseite und aktualisiert dort Status und Ausgabe automatisch.
Alternativ kann der Status manuell aktualisiert werden. Das Schließen der Seite
beendet den Hintergrundauftrag nicht. Der Webserver muss dafür weiterlaufen.

## Status und Jobablage

RI-Aufträge liegen ausschließlich unter `data/ri/db/ri_jobs.sqlite`. Die öffentliche
Jobliste, deren Status-API und die öffentlichen Datenjobs verwenden weiterhin ihre
bisherige eigene Ablage. RI-Jobseiten und die zugehörige Status-API erfordern bei
jedem Abruf ein berechtigtes Konto und werden mit privaten No-Store-Headern geliefert.

| Status | Bedeutung |
| --- | --- |
| wartet / läuft | Auftrag ist reserviert oder wird ausgeführt |
| erfolgreich | Skript hat Exitcode 0 geliefert |
| mit Hinweisen abgeschlossen | Exitcode 2, etwa bei Dokumentfehlern, ungeprüften Sitzungen oder unbestätigter Abmeldung |
| fehlgeschlagen | Startfehler, anderer Exitcode oder unterbrochener Auftrag |

Die Ausgabe ist begrenzt und wird als Text angezeigt. Es wird kein erfundener
Prozentfortschritt ausgegeben. Eine Warnung bei Exitcode 2 ist in der Ausgabe zu
prüfen; Portal- und entfernte Proton-Abmeldung bleiben unterschiedliche Ergebnisse.
Vorhandene RI-Jobdaten bleiben nach einem Serverneustart lesbar. Nicht mehr laufende
Aufträge werden als unterbrochen erkannt, sobald weder ihr Serverprozess noch ihr
Kindprozess existiert.

Gleichzeitig ist höchstens ein RI-Webauftrag erlaubt. Ein weiterer Start wird mit
einem Hinweis abgewiesen. Dieser Slot koordiniert die Weboberfläche; während eines
Webauftrags keine zusätzlichen RI-Skripte manuell per CLI starten. Auch mehrere
angemeldete Webkonten teilen sich denselben RI-Auftragsslot.

## Grenzen und Prüfung

Die Webanbindung umfasst die Skriptsteuerung, Datenbankstatus und Jobausgaben.
Sitzungslisten, interne Dateiauslieferung und Bestandsbereinigung sind noch nicht
angebunden. RI-Suche und Vektorindex sind für diese Ausbaustufe nicht vorgesehen;
die entsprechenden alten Platzhalter starten keine Aufträge.

Gezielte Offline-Tests stehen in der [Testdokumentation](../entwicklung/tests.md).
Die Browserabnahme dieser Änderung verwendete ein temporäres Testkonto, leere
Testdatenbanken und einen synthetischen Auftrag mit Hinweisen. Es wurden keine
realen Portalprüfungen oder Downloads über die Oberfläche gestartet. Den echten
Ablauf nach Einrichtung des eigenen Kontos bewusst mit dem gewünschten Umfang prüfen.
