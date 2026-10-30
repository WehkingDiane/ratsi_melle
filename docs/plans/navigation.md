# Navigation: Ist-Stand und Vorschlag

Stand: 30.10.2026. Die Diagramme beschreiben die aktuelle Navigation und einen Entwurf einschließlich des [RI-Vorhabens](ri_ratsbereich_plan.md). Schritt 1a ist umgesetzt: Navigation, getrennte öffentliche Einstiege, RI-Platzhalter und vertikaler Seitenaufbau sind vorhanden. Das Zielbild enthält zusätzlich die spätere echte RI-Anbindung.

- [Aktuelle Navigation als PlantUML](navigation_ist.puml): Hauptpunkte und sichtbare Untermenüs aus `web/core/templatetags/navigation.py`, ergänzt um ausgewählte Seitencontainer und Inhaltslinks aus den Templates. Dieselben Farben und Textpräfixe wie im Zielbild kennzeichnen Seiten, Container, Einträge und Links. Im aktuellen Dashboard führt „Unterlagen öffnen“ zu lokalen Unterlagen; nur wenn diese fehlen, erscheint gegebenenfalls „Im Ratsinfo ansehen“ als Link zur öffentlichen Quelle. Fehlen beide Möglichkeiten, erscheint ein Texthinweis statt eines Links.
- [Vorgeschlagene Navigation als PlantUML](navigation_ziel.puml): Seiten und Menügruppen sowie ausgewählte Container, Einträge und Links innerhalb der Seiten. Blau kennzeichnet Seiten, Grün Container und Sitzungseinträge, Grau Menügruppen und Gelb Links. Die Textpräfixe erklären die Bedeutung zusätzlich zur Farbe. `[RI]` kennzeichnet geschützte Inhalte. Menügruppen verlangen keine mehrstufigen Dropdown-Menüs; Sitzungsdetailseiten werden über Links erreicht.

## Navigation und weitere Zielstruktur

Die Hauptnavigation lautet **Übersicht · Bürgerinformation · Ratsbereich · Landkreis · Erweiterungen · Einstellungen**. Das Dashboard behält seine bisherige Aufteilung: Container für kommende Sitzungen, vergangene Sitzungen und Datenstatus. Jede Sitzung erscheint einmal. Innerhalb ihres bestehenden Eintrags stehen die Links „Öffentliche Unterlagen“ und, sofern verfügbar und berechtigt, „Ratsunterlagen“. Sie führen im selben Browserfenster zu den jeweiligen Unterlagen derselben Sitzung innerhalb der App. Es entsteht keine zusätzliche Kalenderseite. Die Zuordnung beider Quellen wird geprüft; ausschließlich intern bekannte Termine und interne Metadaten sind nur für berechtigte Nutzer sichtbar.

„Veröffentlichung“ entfällt aus der Navigation. „Analyse“ wird unter „Erweiterungen“ gebündelt. Bürgerinformation und Ratsbereich enthalten jeweils Sitzungen, Dokumentensuche und Datenpflege. Landkreis-Unterlagen erhalten einen eigenen Bereich mit Suche und Datenpflege. „Service“ wird in „Einstellungen“ umbenannt und bündelt Konfiguration, Wartung und Wartungsjobs. Datenjobs bleiben bei der jeweiligen Quelle. Öffentliche Suche und Datenpflege haben bereits quellengebundene Einstiege; die alten gemeinsamen URLs bleiben für vorhandene Links erreichbar.

## Ergänzungen für RI

Der mit `[RI]` markierte Ratsbereich erhält Sitzungen, Dokumente, Suche und Datenpflege. Die gemeinsamen Sitzungslisten bleiben im vorhandenen Dashboard. Eine klare Kennzeichnung bleibt beim Navigieren sichtbar. Der Zeitablauf macht interne Unterlagen nicht öffentlich.

Öffentliche Suche und öffentliche Datenpflege bleiben auf ihre bestehenden Bestände begrenzt. RI-Dokumente verwenden ihre eigene Datenbank und ihren eigenen Suchindex. Die Kennzeichnung Ö / N / unklar ist eine Information zum Dokument und keine automatische Freigabe. Analyse unter „Erweiterungen“ bietet zunächst nur öffentliche Quellen an.

Die Anmeldung am RI-Portal dient dem Abruf. Der Schutz lokal gespeicherter Dateien, Suchtreffer und Jobdetails benötigt zusätzlich eine Zugriffskontrolle in der App; ein Menüpunkt mit Schloss genügt dafür nicht. Loginablauf und Betriebsmodell werden nach Erhalt der Zugangsdaten geprüft. Der Ratsbereich wird erst mit wirksamem Zugriffsschutz für echte RI-Inhalte aktiviert.

## Vorgezogene Umsetzung ohne RI-Zugang

Schritt 1a des RI-Plans zieht Navigation und Seitenaufbau auf `codex/feature/ri-navigation-vorbereitung` vor. Die vorhandenen öffentlichen Seiten sind zugeordnet und die Menüstruktur ist umgestellt. RI-Seiten enthalten aufrufbare Platzhalter mit Zweckbeschreibung und dem Hinweis „Ratsbereich noch nicht eingerichtet“. Das Ziel-Diagramm zeigt weiterhin den vollständigen späteren Funktionsumfang; ein dort vorgesehener RI-Link bedeutet keine bereits aktive Funktion. Insbesondere Dashboard-Links zu Ratsunterlagen warten auf verfügbare Inhalte und geprüfte Berechtigungen.

Eigenständige Hauptcontainer stehen auf allen Seiten untereinander, in der Reihenfolge Überschrift, Hauptaufgabe, Ergebnisse und ergänzende Informationen. Dies gilt auch für Datenpflege, Suche, Analyse und Einstellungen. Zusammengehörige Felder, Tabellen und Bediengruppen innerhalb eines Containers können ihren fachlich passenden Aufbau behalten. Bestehende Leser- und Vergleichsansichten werden bei der Template-Inventur gesondert auf ihre Bedienbarkeit geprüft. Das WBS-Diagramm stellt die inhaltliche Hierarchie dar, keine räumlichen Spalten.

Die vorbereitende Phase verarbeitet keine RI-Zugangsdaten, startet keine RI-Jobs und verwendet keine internen Daten. Die spätere Oberflächenphase bindet nach den Entscheidungen zu Datenhaltung und Zugriffsschutz echte RI-Funktionen an. Das Entfernen des Veröffentlichung-Menüs bedeutet keine Löschung vorhandener Analyseartefakte oder Backend-Funktionen. Das Ist-Diagramm und die UI-Regeln beschreiben diesen Zwischenstand. Unbekannte RI-Sitzungsdetails liefern 404; sie zeigen keine erfundenen Sitzungsdaten.
