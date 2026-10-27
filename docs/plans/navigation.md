# Navigation: Ist-Stand und Vorschlag

Stand: 27.10.2026. Die Diagramme beschreiben die aktuelle Navigation und einen Entwurf einschließlich des [RI-Vorhabens](ri_ratsbereich_plan.md). Die App-Navigation ist damit noch nicht geändert.

- [Aktuelle Navigation als PlantUML](navigation_ist.puml): Hauptpunkte und sichtbare Untermenüs aus `web/core/templates/base.html`, ergänzt um ausgewählte Seitencontainer und Inhaltslinks aus den Templates. Dieselben Farben und Textpräfixe wie im Zielbild kennzeichnen Seiten, Container, Einträge und Links. Im aktuellen Dashboard führt „Unterlagen öffnen“ zu lokalen Unterlagen; nur wenn diese fehlen, erscheint gegebenenfalls „Im Ratsinfo ansehen“ als Link zur öffentlichen Quelle. Fehlen beide Möglichkeiten, erscheint ein Texthinweis statt eines Links.
- [Vorgeschlagene Navigation als PlantUML](navigation_ziel.puml): Seiten und Menügruppen sowie ausgewählte Container, Einträge und Links innerhalb der Seiten. Blau kennzeichnet Seiten, Grün Container und Sitzungseinträge, Grau Menügruppen und Gelb Links. Die Textpräfixe erklären die Bedeutung zusätzlich zur Farbe. `[RI]` kennzeichnet geschützte Inhalte. Menügruppen verlangen keine mehrstufigen Dropdown-Menüs; Sitzungsdetailseiten werden über Links erreicht.

## Vorgeschlagene Änderungen

Die Hauptnavigation lautet **Übersicht · Bürgerinformation · Ratsbereich · Landkreis · Erweiterungen · Einstellungen**. Das Dashboard behält seine bisherige Aufteilung: Container für kommende Sitzungen, vergangene Sitzungen und Datenstatus. Jede Sitzung erscheint einmal. Innerhalb ihres bestehenden Eintrags stehen die Links „Öffentliche Unterlagen“ und, sofern verfügbar und berechtigt, „Ratsunterlagen“. Sie führen im selben Browserfenster zu den jeweiligen Unterlagen derselben Sitzung innerhalb der App. Es entsteht keine zusätzliche Kalenderseite. Die Zuordnung beider Quellen wird geprüft; ausschließlich intern bekannte Termine und interne Metadaten sind nur für berechtigte Nutzer sichtbar.

„Veröffentlichung“ entfällt aus der Navigation. „Analyse“ wird unter „Erweiterungen“ gebündelt. Bürgerinformation und Ratsbereich enthalten jeweils Sitzungen, Dokumentensuche und Datenpflege. Landkreis-Unterlagen erhalten einen eigenen Bereich mit Suche und Datenpflege. „Service“ wird in „Einstellungen“ umbenannt und bündelt Konfiguration, Wartung und Wartungsjobs. Datenjobs bleiben bei der jeweiligen Quelle. Als erster Schritt können die vorhandenen öffentlichen Seiten über die neue Menüstruktur erreichbar gemacht werden; die vollständige Trennung der gemeinsamen Such- und Datenseiten folgt mit der Umsetzung.

## Ergänzungen für RI

Der mit `[RI]` markierte Ratsbereich erhält Sitzungen, Dokumente, Suche und Datenpflege. Die gemeinsamen Sitzungslisten bleiben im vorhandenen Dashboard. Eine klare Kennzeichnung bleibt beim Navigieren sichtbar. Der Zeitablauf macht interne Unterlagen nicht öffentlich.

Öffentliche Suche und öffentliche Datenpflege bleiben auf ihre bestehenden Bestände begrenzt. RI-Dokumente verwenden ihre eigene Datenbank und ihren eigenen Suchindex. Die Kennzeichnung Ö / N / unklar ist eine Information zum Dokument und keine automatische Freigabe. Analyse unter „Erweiterungen“ bietet zunächst nur öffentliche Quellen an.

Die Anmeldung am RI-Portal dient dem Abruf. Der Schutz lokal gespeicherter Dateien, Suchtreffer und Jobdetails benötigt zusätzlich eine Zugriffskontrolle in der App; ein Menüpunkt mit Schloss genügt dafür nicht. Loginablauf und Betriebsmodell werden nach Erhalt der Zugangsdaten geprüft. Der Ratsbereich wird erst mit wirksamem Zugriffsschutz für echte RI-Inhalte aktiviert.

Die Umsetzung dieses Entwurfs gehört zur Oberflächenphase des RI-Plans. Das Entfernen des Veröffentlichung-Menüs bedeutet zunächst keine Löschung vorhandener Analyseartefakte oder Backend-Funktionen.
