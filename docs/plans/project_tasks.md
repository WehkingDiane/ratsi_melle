# Aktuelle Projektaufgabe

Stand: 17.11.2026. Aktuelles Vorhaben ist der geschützte Ratsbereich für SessionNet
`/ri/`. Der [Hauptplan](ri_ratsbereich_plan.md) führt Schutzgrenzen und offene
Entscheidungen; die [RI-Übersicht](../ri/README.md) beschreibt den vorhandenen Umfang.

## Kontext

Anmeldung, Onlineindex, Dokumentabruf und lokaler Dokumentindex wurden im
Testbereich praktisch erprobt und mit 0.7.0 ins Projekt übernommen. Der reguläre
Bestand liegt unter `data/ri/`. Die Bedienung steht ausschließlich in der
[CLI-Anleitung](../ri/datenablauf.md). Die Untergrenze November 2026 ist konfiguriert;
BI-Verlinkung bestimmt `öffentlich` oder `nicht öffentlich`. Ein fehlender Nachweis
ergibt `nicht öffentlich`. Die bisher vorbereitete Webnavigation bleibt ein
Platzhalter und liest keine RI-Daten ein.

Die weitere Richtung ist ein temporärer Arbeitsbestand zur Sitzungsvorbereitung
ohne RI-Volltext-/Vektorindex. Ein Zeitfilter für heutige/künftige Sitzungen,
Nachlauf und Löschfristen sind noch offen. Die einzelne entfernte
Proton-Abmeldewarnung bleibt sichtbar; unbeaufsichtigter Betrieb ist nicht abgenommen.

## RI-Vorhaben

#### Konkrete Aufgaben

- [ ] Verwaltungsausschuss anhand von HTML-Struktur und Dokumentmetadaten als priorisierte Bedarfsstichprobe prüfen; bisherige Sitzungen ersetzen diese Prüfung nicht.
- [ ] Dokumentartauswahl für die weitere Nutzung präzisieren; der aktuelle CLI-Abruf übernimmt verlinkte Sitzungs- und TOP-Dokumente einschließlich Einladungen. Umgang mit Sammelunterlagen, Anlagen und Dubletten entscheiden.
- [ ] Zeitgrenze für heutige/laufende, abgesagte und verschobene Sitzungen sowie Nachlauf, Aufbewahrung und Löschfristen verbindlich festlegen.
- [ ] Kontrollierte RI-Bereinigung mit Vorschau und konsistentem Datenbankabgleich umsetzen; entfernte Sitzungen und Nebenartefakte berücksichtigen, BI-Dateien ausschließen.
- [ ] Betriebsmodell und Betriebssystem-Zugriffsrechte einschließlich Sicherung und Wiederherstellung für den regulären RI-Bestand abnehmen; zurückgestellte Neustart-/Ablauf- und Proton-Abmeldeprüfungen bei erweitertem Betrieb nachholen.
- [ ] CLI-Datenjobs und lokalen Dokumentbestand in den geschützten Ratsbereich der Django-Oberfläche integrieren; serverseitige Berechtigungen und Dateiauslieferung umsetzen.
- [ ] Web- und Exporttrennung zwischen öffentlichem und internem Bestand mit Negativtests und einer begrenzten lokalen RI-Stichprobe abnehmen.
