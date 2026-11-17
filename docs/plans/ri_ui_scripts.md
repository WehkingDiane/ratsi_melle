# Plan: RI-Skripte in die Oberfläche einbinden

Stand: 17.11.2026. Arbeitsbranch: `codex/feature/ri-ui-scripts`.

## Umfang und Entscheidungen

Die vorhandenen CLI-Skripte werden über die RI-Datenpflege bedient: Zugang prüfen,
Dokumente abrufen, Onlineindex aktualisieren und lokalen Index aktualisieren.
Sitzungsansichten, Dateiauslieferung, Suche und Bestandsbereinigung bleiben eigene
Arbeitspakete des [RI-Hauptplans](ri_ratsbereich_plan.md).

Die bisher öffentliche Entwicklungsoberfläche erhält für RI-Funktionen eine
Django-Anmeldung. Nur aktive lokale Benutzer mit Mitarbeiterstatus dürfen RI-Jobs
starten oder deren Status und Ausgaben sehen. Die Anmeldung an der Weboberfläche
ist vom Portalzugang über `.env/ri_token.txt` getrennt. Öffentliche Datenpflege und
Suche bleiben im bisherigen Ablauf nutzbar.

RI-Jobs erhalten eine eigene Datenbank unter `data/ri/db/ri_jobs.sqlite`. Sie werden
nicht in der öffentlichen Jobablage gespeichert. Ein gemeinsamer RI-Auftragsslot
verhindert parallele RI-Anmeldungen und Überschneidungen von Download und Build.
Nur feste Skripte und typisierte Formularparameter sind startbar; Tokens,
Zugangsdaten, freie Befehle oder Ausgabe- und Quellpfade werden nicht über Formulare
angenommen. GET-Aufrufe starten keine Jobs. Die Formulare verwenden CSRF-Schutz.
Exitcode 2 wird als abgeschlossener Auftrag mit Hinweisen angezeigt.

## Umsetzung

- [ ] Django-Authentifizierung einrichten und RI-Views, Jobdetails und Statusabfragen serverseitig schützen.
- [ ] Bestehende RI-Einstiege für Zugang, Download, Build und Datenstatus mit Formularen und Ergebnissen verbinden.
- [ ] Eigene RI-Jobablage und begrenzte Hintergrundausführung einschließlich Parallelitätsschutz und Wiederanlauferkennung ergänzen.
- [ ] Öffentliche Joblisten und APIs auf Trennung prüfen; RI-Aktionen dort weiterhin ablehnen.
- [ ] Formularfehler, fehlenden Datenbestand, laufende Jobs, Teilstatus und Fehler verständlich darstellen.
- [ ] Gezielte Tests für Anmeldung, Berechtigungen, CSRF, Befehlsparameter, Datenisolation und Jobzustände ergänzen; betroffene bisherige Platzhaltertests aktualisieren.
- [ ] Neue RI-Seiten mit synthetischen Daten im Browser prüfen, ohne reale Downloads oder Portalprüfungen zu starten.
- [ ] Zugangseinrichtung, Bedienung, Ist-Stand und offene Aufgaben nachführen; Version und Changelog gemeinsam aktualisieren.

## Abnahme

Unberechtigte Besucher erhalten keine RI-Jobdaten und können keine RI-Aktion starten.
Die vier Skriptaktionen sind nach Anmeldung über ihre Formulare erreichbar. Status
und Ausgabe bleiben auf den Ratsbereich beschränkt. Parallele RI-Aufträge werden
abgewiesen; ein unterbrochener Auftrag und Exitcode 2 sind eindeutig erkennbar.
Ein Seitenaufruf führt weder Portalzugriff noch Skriptausführung aus.
Der vollständige PR-Testlauf bleibt gemäß [Testregeln](../entwicklung/tests.md)
beim Nutzer.
