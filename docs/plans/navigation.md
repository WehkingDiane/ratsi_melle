# Navigation: Ist-Stand und Vorschlag

Stand: 27.10.2026. Die Diagramme beschreiben die aktuelle Navigation und einen Entwurf einschließlich des [RI-Vorhabens](ri_ratsbereich_plan.md). Die App-Navigation ist damit noch nicht geändert.

- [Aktuelle Navigation als PlantUML](navigation_ist.puml): Hauptpunkte und sichtbare Untermenüs aus `web/core/templates/base.html`.
- [Vorgeschlagene Navigation als PlantUML](navigation_ziel.puml): Seitenstruktur für die öffentliche Recherche und den geplanten Ratsbereich. Unterknoten zeigen Funktionen und Seiten; sie verlangen keine mehrstufigen Dropdown-Menüs.

## Vorgeschlagene Änderungen

Die Hauptnavigation lautet **Übersicht · Sitzungen · Suche · Daten · Ratsbereich · Erweiterungen · Einstellungen**. Übersicht, Sitzungen und Suche stehen vorne, weil sie den täglichen Rechercheablauf bilden. Übersicht und Suche öffnen direkt ihre Seite; ein zusätzliches Untermenü mit nur „öffnen“ entfällt.

„Veröffentlichung“ entfällt aus der Navigation. „Analyse“ wird unter „Erweiterungen“ gebündelt. Die Sitzungsübersicht erhält einen eigenen Hauptpunkt, damit sie unabhängig von der Analyse erreichbar ist. „Service“ wird in „Einstellungen“ umbenannt und bündelt Konfiguration, Wartung und Wartungsjobs. Datenjobs bleiben bei „Daten“.

## Ergänzungen für RI

Der orange markierte Ratsbereich erhält eine eigene Übersicht, Sitzungen, Dokumente, Suche und Datenpflege. Eine klare Kennzeichnung bleibt beim Navigieren sichtbar. Seine Termine umfassen kommende und vergangene RI-Sitzungen: Der Zeitablauf macht interne Unterlagen nicht öffentlich.

Öffentliche Suche und öffentliche Datenpflege bleiben auf ihre bestehenden Bestände begrenzt. RI-Dokumente verwenden ihre eigene Datenbank und ihren eigenen Suchindex. Die Kennzeichnung Ö / N / unklar ist eine Information zum Dokument und keine automatische Freigabe. Analyse unter „Erweiterungen“ bietet zunächst nur öffentliche Quellen an.

Die Anmeldung am RI-Portal dient dem Abruf. Der Schutz lokal gespeicherter Dateien, Suchtreffer und Jobdetails benötigt zusätzlich eine Zugriffskontrolle in der App; ein Menüpunkt mit Schloss genügt dafür nicht. Loginablauf und Betriebsmodell werden nach Erhalt der Zugangsdaten geprüft. Der Ratsbereich wird erst mit wirksamem Zugriffsschutz für echte RI-Inhalte aktiviert.

Die Umsetzung dieses Entwurfs gehört zur Oberflächenphase des RI-Plans. Das Entfernen des Veröffentlichung-Menüs bedeutet zunächst keine Löschung vorhandener Analyseartefakte oder Backend-Funktionen.
