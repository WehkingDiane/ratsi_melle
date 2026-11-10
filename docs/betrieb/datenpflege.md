# Datenhaltung und Pflege

[Dokumentation](../README.md)

- `data/raw/`, `data/db/`, `data/processed/`, `data/private/`, `data/analysis_requests/`, `data/analysis_outputs/`, `data/models/` und `logs/` sind lokale Laufzeitbereiche und werden nicht eingecheckt. Geheimnisse gehören in den Betriebskontext oder den OS-Schlüsselring, nicht in Git.
- Dokumentpfade und Manifest-Verweise werden auf erlaubte Datenwurzeln begrenzt. SessionNet-Downloads warnen oberhalb von 25 MiB und brechen oberhalb von 100 MiB ab; bei Landkreis-Downloads gilt ein Limit von 25 MiB.

Rohdaten bleiben unverändert; SQLite- und Vektorindizes werden daraus abgeleitet. Nach neuen Downloads den [Indexaufbau](../suche/indizes.md) ausführen. Analyseartefakte beschreibt der [Ausgabevertrag](../analyse/ausgabeformat.md).

Die kanonische Version steht in `VERSION`. Skriptumbenennungen sind im [Changelog](../../CHANGELOG.md) dokumentiert.
