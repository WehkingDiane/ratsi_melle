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
die Ergebnisse; Statusbehandlung und lokaler Indexnachlauf bleiben eigene Folgeaufgaben.

Die weitere Richtung ist ein temporärer Arbeitsbestand zur Sitzungsvorbereitung
ohne RI-Volltext-/Vektorindex. Ein Zeitfilter für heutige/künftige Sitzungen,
Nachlauf und Löschfristen sind noch offen. Die einzelne entfernte
Proton-Abmeldewarnung bleibt sichtbar; unbeaufsichtigter Betrieb ist nicht abgenommen.

Der Stand der RI-Webanbindung wird als erster funktionsfähiger Prototyp übernommen. Formularraster, Statuspanels und Jobausgabe sind gestalterisch an BI angeglichen. Seit 0.9.3 werden auch Formular-/Feldrenderer, Statuspanelrahmen sowie Auftragspanel und Live-Aktualisierung gemeinsam verwendet. Die verbleibende Vereinheitlichung betrifft das Backend. Die reguläre UI-Kette wurde am 22.11.2026 mit Verwaltungsausschuss 8178 und Betriebsausschuss 8179 real geprüft; Ergebnis und verbleibende Hinweise stehen in der [UI-Abnahme](../ri/oberflaeche.md#reale-ui-abnahme-vom-22112026).

## RI-Vorhaben

#### Konkrete Aufgaben

- [ ] BI und RI im Backend auf weitere fachlich identische Teile prüfen: Skripte, Befehlsaufbau, Abruf-/Build-Logik und Jobverwaltung. Gemeinsamkeiten und notwendige Bereichsunterschiede festhalten.
- [ ] Weitere geeignete Backendteile schrittweise in wiederverwendbare Funktionen, Module oder Skripte überführen und beide Bereiche darauf umstellen. Getrennte Daten-/Jobablagen, RI-Portalzugang und Öffentlichkeitskennzeichnung erhalten und mit gezielten Regressionstests absichern.
- [ ] Dokumentartauswahl für die weitere Nutzung präzisieren; der aktuelle CLI-Abruf übernimmt verlinkte Sitzungs- und TOP-Dokumente einschließlich Einladungen. Umgang mit Sammelunterlagen, Anlagen und Dubletten entscheiden.
- [ ] Zeitgrenze für heutige/laufende, abgesagte und verschobene Sitzungen sowie Nachlauf, Aufbewahrung und Löschfristen verbindlich festlegen.
- [ ] Kontrollierte RI-Bereinigung mit Vorschau und konsistentem Datenbankabgleich umsetzen; entfernte Sitzungen und Nebenartefakte berücksichtigen, BI-Dateien ausschließen.
- [ ] Betriebsmodell und Betriebssystem-Zugriffsrechte einschließlich Sicherung und Wiederherstellung für den regulären RI-Bestand abnehmen; zurückgestellte Neustart-/Ablauf- und Proton-Abmeldeprüfungen bei erweitertem Betrieb nachholen.
- [ ] Verschobene/abgesagte Termine als Kalenderstatus erfassen statt als Uhrzeittext; die alternative Terminansicht `si0050.asp` für 9516/8181 gezielt behandeln und alte/neue Terminzuordnung einschließlich Jahreswechsel prüfen. Den Ersatztermin für 9516 im Januar später erneut abgleichen.
- [ ] Den lokalen RI-Index nach dem inzwischen vollständigen Download von 8176 aktualisieren und 14 indexierte Dokumente verifizieren; aktuell fehlen im Index noch 146339, 146340 und 146087, ein weiterer Dateidownload ist nach der Nachprüfung nicht erforderlich.
- [ ] Verbleibende Export- und Betriebsabnahme durchführen; die RI-Abgrenzung vorhandener öffentlicher Exporte prüfen und bei späteren Exportfunktionen erneut absichern.
