# Plan: RI-Skripte in die Oberfläche einbinden

Stand: 27.11.2026. Status: Web-Skriptsteuerung umgesetzt (seit 0.8.0), gemeinsame
UI-Bausteine seit 0.9.3 und optionaler Indexnachlauf seit 0.10.0 ergänzt. Dieser
Teilplan dokumentiert die abgeschlossene Umsetzung; offene Aufgaben stehen in der
[Aufgabenliste](project_tasks.md).

## Umfang und Entscheidungen

Die vorhandenen CLI-Skripte werden über die RI-Datenpflege bedient: Zugang prüfen,
Dokumente abrufen, Onlineindex aktualisieren und lokalen Index aktualisieren.
Sitzungsansichten und lokale PDF-Auslieferung sind seit 0.9.0 umgesetzt. RI-Suche
bleibt zurückgestellt; Aufbewahrung und Dokumentlöschung verwaltet der Nutzer
manuell. Eine automatische Bestandsbereinigung ist kein Arbeitspaket. Die
Abgrenzung steht im [RI-Hauptplan](ri_ratsbereich_plan.md).

Auf Nutzerwunsch sind die RI-Funktionen im lokalen Einzelplatzbetrieb ohne Web-Anmeldung zugänglich. Ein lokales Benutzerkonto ist nicht erforderlich. Der Portalzugang über `.env/ri_token.txt` wird weiterhin ausschließlich von den Skripten verwendet. Öffentliche Datenpflege und Suche bleiben im bisherigen Ablauf nutzbar.

RI-Jobs erhalten eine eigene Datenbank unter `data/ri/db/ri_jobs.sqlite`. Sie werden
nicht in der öffentlichen Jobablage gespeichert. Ein gemeinsamer RI-Auftragsslot
verhindert parallele RI-Anmeldungen und Überschneidungen von Download und Build.
Nur feste Skripte und typisierte Formularparameter sind startbar; Tokens,
Zugangsdaten, freie Befehle oder Ausgabe- und Quellpfade werden nicht über Formulare
angenommen. GET-Aufrufe starten keine Jobs. Die Formulare verwenden CSRF-Schutz.
Exitcode 2 wird als abgeschlossener Auftrag mit Hinweisen angezeigt.

## Umsetzung

- [x] RI-Views, Jobdetails und Statusabfragen direkt ohne Web-Anmeldung für den lokalen Betrieb verfügbar machen.
- [x] Bestehende RI-Einstiege für Zugang, Download, Build und Datenstatus mit Formularen und Ergebnissen verbinden.
- [x] Eigene RI-Jobablage und begrenzte Hintergrundausführung einschließlich Parallelitätsschutz und Wiederanlauferkennung ergänzen.
- [x] Öffentliche Joblisten und APIs auf Trennung prüfen; RI-Aktionen dort weiterhin ablehnen.
- [x] Formularfehler, fehlenden Datenbestand, laufende Jobs, Teilstatus und Fehler verständlich darstellen.
- [x] Gezielte Tests für Direktzugriff ohne Anmeldung, alte Login-Links, CSRF, Befehlsparameter, Datenisolation und Jobzustände ergänzen; betroffene bisherige Platzhaltertests aktualisieren.
- [x] Neue RI-Seiten mit synthetischen Daten im Browser prüfen, ohne reale Downloads oder Portalprüfungen zu starten.
- [x] Zugangseinrichtung, Bedienung, Ist-Stand und offene Aufgaben nachführen; Version und Changelog gemeinsam aktualisieren.
- [x] Gemeinsame BI-/RI-Formularrenderer, Statuspanels und Jobausgaben verwenden (0.9.3).
- [x] RI-Download mit standardmäßig aktiviertem, abschaltbarem lokalem Indexnachlauf im selben Job verbinden; Phasen und Ergebnisse getrennt anzeigen (0.10.0).

Die UI-Vereinheitlichung ist abgeschlossen. Weitere Prüfung und Wiederverwendung
im Backend wird in der [Aufgabenliste](project_tasks.md) geführt.

## Abnahme

Die vier Skriptaktionen sowie Jobdaten sind auf dem lokalen Rechner direkt ohne Anmeldung über ihre Formulare und Seiten erreichbar. Status
und Ausgabe bleiben auf den Ratsbereich beschränkt. Parallele RI-Aufträge werden
abgewiesen; ein unterbrochener Auftrag und Exitcode 2 sind eindeutig erkennbar.
Ein Seitenaufruf führt weder Portalzugriff noch Skriptausführung aus.
Die reale UI-Kette für 8178/8179 wurde am 22.11.2026 geprüft. Die Erweiterungen
von 0.10.0 wurden gezielt mit Tests und synthetischen Browserdaten geprüft;
ein erneuter Live-Abruf fand dafür nicht statt. Einzelheiten und Grenzen stehen in
der [UI-Dokumentation](../ri/oberflaeche.md).
Der vollständige PR-Testlauf bleibt gemäß [Testregeln](../entwicklung/tests.md)
beim Nutzer.
