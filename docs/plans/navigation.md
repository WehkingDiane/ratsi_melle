# Navigation: Ist-Stand und Vorschlag

Stand: 27.10.2026. Die Diagramme beschreiben die aktuelle Navigation und einen Entwurf einschließlich des [RI-Vorhabens](ri_ratsbereich_plan.md). Die App-Navigation ist damit noch nicht geändert.

- [Aktuelle Navigation als PlantUML](navigation_ist.puml): Hauptpunkte und sichtbare Untermenüs aus `web/core/templates/base.html`.
- [Vorgeschlagene Navigation als PlantUML](navigation_ziel.puml): Seitenstruktur für die öffentliche Recherche und den geplanten Ratsbereich. Unterknoten zeigen Funktionen und Seiten; sie verlangen keine mehrstufigen Dropdown-Menüs.

## Vorgeschlagene Änderungen

Die Hauptnavigation lautet **Übersicht · Bürgerinformation · Ratsbereich · Landkreis · Erweiterungen · Einstellungen**. Die Übersicht enthält einen gemeinsamen Sitzungskalender und den Datenstatus. Pro Sitzung werden die verfügbaren Einstiege „Bürgerinformationen öffnen“ und „Ratsinformationen öffnen“ angeboten; der RI-Einstieg setzt die entsprechende Berechtigung voraus. Eine Sitzung erhält nach geprüfter Zuordnung der Quellen einen gemeinsamen Kalendereintrag. Ausschließlich intern bekannte Termine und interne Metadaten sind nur für berechtigte Nutzer sichtbar.

„Veröffentlichung“ entfällt aus der Navigation. „Analyse“ wird unter „Erweiterungen“ gebündelt. Bürgerinformation und Ratsbereich enthalten jeweils Sitzungen, Dokumentensuche und Datenpflege. Landkreis-Unterlagen erhalten einen eigenen Bereich mit Suche und Datenpflege. „Service“ wird in „Einstellungen“ umbenannt und bündelt Konfiguration, Wartung und Wartungsjobs. Datenjobs bleiben bei der jeweiligen Quelle. Als erster Schritt können die vorhandenen öffentlichen Seiten über die neue Menüstruktur erreichbar gemacht werden; die vollständige Trennung der gemeinsamen Such- und Datenseiten folgt mit der Umsetzung.

## Ergänzungen für RI

Der orange markierte Ratsbereich erhält Sitzungen, Dokumente, Suche und Datenpflege. Der gemeinsame Kalender bleibt auf der Übersicht; ein zweiter RI-Kalender ist nicht vorgesehen. Eine klare Kennzeichnung bleibt beim Navigieren sichtbar. Der Zeitablauf macht interne Unterlagen nicht öffentlich.

Öffentliche Suche und öffentliche Datenpflege bleiben auf ihre bestehenden Bestände begrenzt. RI-Dokumente verwenden ihre eigene Datenbank und ihren eigenen Suchindex. Die Kennzeichnung Ö / N / unklar ist eine Information zum Dokument und keine automatische Freigabe. Analyse unter „Erweiterungen“ bietet zunächst nur öffentliche Quellen an.

Die Anmeldung am RI-Portal dient dem Abruf. Der Schutz lokal gespeicherter Dateien, Suchtreffer und Jobdetails benötigt zusätzlich eine Zugriffskontrolle in der App; ein Menüpunkt mit Schloss genügt dafür nicht. Loginablauf und Betriebsmodell werden nach Erhalt der Zugangsdaten geprüft. Der Ratsbereich wird erst mit wirksamem Zugriffsschutz für echte RI-Inhalte aktiviert.

Die Umsetzung dieses Entwurfs gehört zur Oberflächenphase des RI-Plans. Das Entfernen des Veröffentlichung-Menüs bedeutet zunächst keine Löschung vorhandener Analyseartefakte oder Backend-Funktionen.
