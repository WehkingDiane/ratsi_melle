# Aktuelle Projektaufgabe

Stand: 27.11.2026. Aktuelles Vorhaben ist der geschützte Ratsbereich für SessionNet
`/ri/`. Der [Hauptplan](ri_ratsbereich_plan.md) führt Schutzgrenzen und offene
Entscheidungen; die [RI-Übersicht](../ri/README.md) beschreibt den vorhandenen Umfang.

## Kontext

Anmeldung, Onlineindex, Dokumentabruf und lokaler Dokumentindex wurden im
Testbereich praktisch erprobt und mit 0.7.0 ins Projekt übernommen. Der reguläre
Bestand liegt unter `data/ri/`. Die CLI-Bedienung steht in der
[CLI-Anleitung](../ri/datenablauf.md). Die Untergrenze November 2026 ist konfiguriert;
BI-Verlinkung bestimmt `öffentlich` oder `nicht öffentlich`. Ein fehlender Nachweis
ergibt `nicht öffentlich`. Seit 0.8.0 steuert die [lokale Web-Datenpflege](../ri/oberflaeche.md) die Skripte und zeigt eigene Jobausgaben. Der lokale Einzelplatzbetrieb benötigt keine Web-Anmeldung. Seit 0.9.0 sind Sitzungslisten, TOP-Details und sitzungsgebundene lokale PDFs angebunden; Listen-/Detailtemplates und Filterlogik werden mit BI geteilt. Seit 0.9.1 enthält die lokale Startseite gemeinsame BI-/RI-Termine mit getrennten Direktlinks.

Die Untersuchung der Hinweise zu 9516/8181 und 8176 ist abgeschlossen und wurde
am 27.11.2026 vom Nutzer als erledigt bestätigt. Die
[Nachprüfung](../ri/oberflaeche.md#nachprüfung-der-hinweise-vom-27112026) dokumentiert
die Ergebnisse. Der lokale Indexnachlauf für 8176 wurde danach am selben Tag
ausgeführt und mit 14 vorhandenen Dokumenten verifiziert. Seit 0.10.0 werden
Kalenderstatus und geänderte Termine durchgehend verarbeitet und angezeigt. Der
RI-Webdownload bietet einen zunächst aktivierten lokalen Indexnachlauf im selben
Auftrag; Downloadwarnungen bleiben dabei erhalten. Bei verschobenen oder
abgesagten Terminen erscheinen fehlende Uhrzeit und fehlender Ort im Dashboard
als „–“. Kalenderstatus, Indexnachlauf und diese Anzeigeanpassung sind umgesetzt;
sie sind keine offenen UI-Aufgaben mehr. Gezielte Tests und Browserprüfungen mit
synthetischen Daten sind abgeschlossen; für diese Erweiterungen gab es keinen
erneuten Live-Abruf. Der vollständige PR-Testlauf bleibt beim Nutzer.

RI bleibt ein lokaler Arbeitsbestand zur Sitzungsvorbereitung ohne Volltext-/Vektorindex.
Der Nutzer hat am 27.11.2026 entschieden, Aufbewahrung und Dokumentlöschung selbst
manuell zu verwalten. Eine automatische Bereinigung oder weitere Fristenbewertung
ist nicht vorgesehen; die verbindliche Regel steht im
[Datenablauf](../ri/datenablauf.md#aufbewahrung-und-manuelles-löschen).
Die einzelne entfernte Proton-Abmeldewarnung bleibt sichtbar; unbeaufsichtigter
Betrieb ist nicht abgenommen.

Der Stand der RI-Webanbindung wird als erster funktionsfähiger Prototyp übernommen. Formularraster, Statuspanels und Jobausgabe sind gestalterisch an BI angeglichen. Seit 0.9.3 werden auch Formular-/Feldrenderer, Statuspanelrahmen sowie Auftragspanel und Live-Aktualisierung gemeinsam verwendet. Die verbleibende Vereinheitlichung betrifft das Backend. Die reguläre UI-Kette wurde am 22.11.2026 mit Verwaltungsausschuss 8178 und Betriebsausschuss 8179 real geprüft; Ergebnis und verbleibende Hinweise stehen in der [UI-Abnahme](../ri/oberflaeche.md#reale-ui-abnahme-vom-22112026).

## RI-Vorhaben

#### Konkrete Aufgaben

- [ ] BI und RI im Backend auf weitere fachlich identische Teile prüfen: Skripte, Befehlsaufbau, Abruf-/Build-Logik und Jobverwaltung. Gemeinsamkeiten und notwendige Bereichsunterschiede festhalten.
- [ ] Weitere geeignete Backendteile schrittweise in wiederverwendbare Funktionen, Module oder Skripte überführen und beide Bereiche darauf umstellen. Getrennte Daten-/Jobablagen, RI-Portalzugang und Öffentlichkeitskennzeichnung erhalten und mit gezielten Regressionstests absichern.
- [ ] Dokumentartauswahl für die weitere Nutzung präzisieren; der aktuelle CLI-Abruf übernimmt verlinkte Sitzungs- und TOP-Dokumente einschließlich Einladungen. Umgang mit Sammelunterlagen, Anlagen und Dubletten entscheiden.
- [ ] Betriebsmodell und Betriebssystem-Zugriffsrechte einschließlich Sicherung und Wiederherstellung für den regulären RI-Bestand abnehmen; zurückgestellte Neustart-/Ablauf- und Proton-Abmeldeprüfungen bei erweitertem Betrieb nachholen.
- [ ] Verbleibende Export- und Betriebsabnahme durchführen; die RI-Abgrenzung vorhandener öffentlicher Exporte prüfen und bei späteren Exportfunktionen erneut absichern.
