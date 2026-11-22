# Aktuelle Projektaufgabe

Stand: 22.11.2026. Aktuelles Vorhaben ist der geschützte Ratsbereich für SessionNet
`/ri/`. Der [Hauptplan](ri_ratsbereich_plan.md) führt Schutzgrenzen und offene
Entscheidungen; die [RI-Übersicht](../ri/README.md) beschreibt den vorhandenen Umfang.

## Kontext

Anmeldung, Onlineindex, Dokumentabruf und lokaler Dokumentindex wurden im
Testbereich praktisch erprobt und mit 0.7.0 ins Projekt übernommen. Der reguläre
Bestand liegt unter `data/ri/`. Die CLI-Bedienung steht in der
[CLI-Anleitung](../ri/datenablauf.md). Die Untergrenze November 2026 ist konfiguriert;
BI-Verlinkung bestimmt `öffentlich` oder `nicht öffentlich`. Ein fehlender Nachweis
ergibt `nicht öffentlich`. Seit 0.8.0 steuert die [lokale Web-Datenpflege](../ri/oberflaeche.md) die Skripte und zeigt eigene Jobausgaben. Der lokale Einzelplatzbetrieb benötigt keine Web-Anmeldung. Seit 0.9.0 sind Sitzungslisten, TOP-Details und sitzungsgebundene lokale PDFs angebunden; Listen-/Detailtemplates und Filterlogik werden mit BI geteilt.

Die weitere Richtung ist ein temporärer Arbeitsbestand zur Sitzungsvorbereitung
ohne RI-Volltext-/Vektorindex. Ein Zeitfilter für heutige/künftige Sitzungen,
Nachlauf und Löschfristen sind noch offen. Die einzelne entfernte
Proton-Abmeldewarnung bleibt sichtbar; unbeaufsichtigter Betrieb ist nicht abgenommen.

Der Stand der RI-Webanbindung wird als erster funktionsfähiger Prototyp übernommen. Formularraster, Statuspanels und Jobausgabe sind gestalterisch an BI angeglichen. Die weitere gemeinsame Nutzung geeigneter Komponenten bleibt eine Aufgabe für Frontend und Backend.

## RI-Vorhaben

#### Konkrete Aufgaben

- [ ] BI und RI systematisch auf fachlich identische Teile prüfen: im Frontend Seitenaufbau, Templates, Formulare, Status- und Ausgabeansichten; im Backend Skripte, Befehlsaufbau, Abruf-/Build-Logik und Jobverwaltung. Gemeinsamkeiten und notwendige Bereichsunterschiede festhalten.
- [ ] Geeignete gemeinsame Teile schrittweise in wiederverwendbare Objekte, Funktionen, Module oder Skripte überführen und beide Bereiche darauf umstellen. Getrennte Daten-/Jobablagen, RI-Portalzugang und Öffentlichkeitskennzeichnung erhalten; Frontend und Backend mit gezielten Regressionstests absichern.
- [ ] Verwaltungsausschuss anhand von HTML-Struktur und Dokumentmetadaten als priorisierte Bedarfsstichprobe prüfen; bisherige Sitzungen ersetzen diese Prüfung nicht.
- [ ] Dokumentartauswahl für die weitere Nutzung präzisieren; der aktuelle CLI-Abruf übernimmt verlinkte Sitzungs- und TOP-Dokumente einschließlich Einladungen. Umgang mit Sammelunterlagen, Anlagen und Dubletten entscheiden.
- [ ] Zeitgrenze für heutige/laufende, abgesagte und verschobene Sitzungen sowie Nachlauf, Aufbewahrung und Löschfristen verbindlich festlegen.
- [ ] Kontrollierte RI-Bereinigung mit Vorschau und konsistentem Datenbankabgleich umsetzen; entfernte Sitzungen und Nebenartefakte berücksichtigen, BI-Dateien ausschließen.
- [ ] Betriebsmodell und Betriebssystem-Zugriffsrechte einschließlich Sicherung und Wiederherstellung für den regulären RI-Bestand abnehmen; zurückgestellte Neustart-/Ablauf- und Proton-Abmeldeprüfungen bei erweitertem Betrieb nachholen.
- [ ] Web- und Exporttrennung der angebundenen Sitzungs-/Dateiansichten mit einer begrenzten lokalen RI-Stichprobe abnehmen; Offline-Negativtests für Daten-/Pfadtrennung sind vorhanden. Den echten Skriptablauf über die vorhandenen Webformulare im lokalen Betrieb prüfen.
