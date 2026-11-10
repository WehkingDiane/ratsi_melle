# Ist-Stand des Projekts

Stand: 10.11.2026. Diese Übersicht beschreibt die vorhandene Implementierung. Der [Dokumentationswegweiser](README.md) führt zu Bedienung und technischen Einzelheiten.

| Bereich | Aktueller Umfang |
| --- | --- |
| [Datenabruf](datenabruf/README.md) | Öffentliche SessionNet-Sitzungen und Landkreis-Veröffentlichungen, getrennte Rohdaten. |
| [Suche](suche/README.md) | SQLite-Indizes und semantische Suche mit getrennten Vektorbeständen. |
| [Oberfläche](oberflaeche/README.md) | Lokale Django-Oberfläche, Sitzungsübersicht, Filter und Datenjobs. |
| [Analyse](analyse/README.md) | Vorlagen, vorbereitete Jobs, Provider-Ausführung und Antwortansicht. |
| [RI-Zugang](ri/README.md) | Lokale Tokenablage und manuelle Anmeldung bestätigt; kein RI-Dokumentabruf, Index oder geschützter Webzugang. |
| [Betrieb](betrieb/einrichtung.md) | Lokale Entwicklungsumgebung ohne Benutzeranmeldung; Laufzeitdaten bleiben außerhalb von Git. |

Das einzige aktuelle Ausbauvorhaben ist der [geschützte Ratsbereich](plans/ri_ratsbereich_plan.md). Die [Aufgabenliste](plans/project_tasks.md) enthält dessen aktuelle Arbeitspakete. Versionsbezogene Änderungen stehen im [Changelog](../CHANGELOG.md).
