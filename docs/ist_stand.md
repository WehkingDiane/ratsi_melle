# Ist-Stand des Projekts

Stand: 27.10.2026. Diese Übersicht beschreibt die vorhandene Implementierung. Sie ist keine Liste geplanter Funktionen. Der einzige aktuelle Ausbau steht im [RI-Plan](plans/ri_ratsbereich_plan.md).

## Datenquellen und Abruf

- SessionNet `/bi/` liefert öffentliche Sitzungen, Tagesordnungspunkte und Dokumente. `scripts/fetch_sessions.py` lädt nach Jahr und Monaten; `scripts/fetch_session_from_index.py` lädt einzelne Sitzungen anhand des gespeicherten Online-Index. Beide nutzen `src/fetching/sessionnet_client.py`.
- `scripts/build_online_index_db.py` baut den Kalender- und Metadatenindex in `data/db/online_session_index.sqlite`. Angekündigte Termine ohne Detailseite werden über die Kalender-ID erfasst.
- SessionNet-Rohdaten liegen unter `data/raw/YYYY/MM/`. Gespeicherte HTML-Seiten und Dokumente bleiben beim Indexaufbau unverändert. Ein Sitzungsmanifest und eine Tagesordnungsübersicht halten Metadaten zum Download fest.
- Landkreis-Bekanntmachungen und Amtsblätter sind eine zweite, getrennte Quelle. `scripts/fetch_landkreis_publications.py` speichert sie unter `data/raw/landkreis/` oder der mit `RATSI_LANDKREIS_DATA_DIR` gesetzten Datenwurzel.
- Ein authentifizierter Abruf aus SessionNet `/ri/` existiert derzeit nicht. Es gibt auch noch keine RI-Datenbank und keinen geschützten Ratsbereich.

## Datenbanken und Suche

- `scripts/build_local_index.py` baut `data/db/local_index.sqlite` aus den öffentlichen SessionNet-Rohdaten. `session_detail.html` ist die maßgebliche Quelle für aktuelle TOP- und Dokumentmetadaten im Index.
- `scripts/build_landkreis_publications_db.py` baut `data/db/landkreis_publications.sqlite` getrennt vom SessionNet-Index.
- `scripts/prepare_embedding_models.py` bereitet lokale Suchmodelle vor. `scripts/build_vector_index.py` baut den Ratsinfo-Index in Qdrant; `scripts/build_landkreis_vector_index.py` baut die getrennte Landkreis-Collection. Der Ratsinfo-Abschnittsindex heißt `ratsi_passages`; `ratsi_documents` ist der ältere Dokumentindex und kann je nach lokalem Migrationsstand noch aktiv sein.
- Standardmäßig wird Qdrant unter `http://127.0.0.1:6333` angesprochen. `RATSI_QDRANT_URL` wählt einen anderen Server; `RATSI_QDRANT_MODE=local` nutzt lokalen Speicher unter `data/db/qdrant/`, sofern keine URL gesetzt ist. Datenbank, Modelle und Suchindex müssen zur gleichen lokalen Umgebung gehören.
- `/suche/` bietet semantische Suche in Ratsinfo- und Landkreis-Unterlagen mit Datumsfiltern und, für Ratsinfo, Gremium und Dokumenttyp. Der Landkreisbestand kann zusätzlich per `scripts/search_landkreis_publications.py` in SQLite durchsucht werden.

## Oberfläche und Analyse

- Die aktive Oberfläche ist Django unter `web/`, gestartet mit `python scripts/run_web.py` auf `127.0.0.1:8000`.
- Das Dashboard zeigt kommende und vergangene Termine aus den gespeicherten Indizes. Unter `/daten/` lassen sich Fetch-, SQLite- und Vektorjobs starten und deren Status prüfen. `/service/` bündelt Wartung und Einstellungen.
- Unter `/analyse/` gibt es Sitzungsansichten, Vorlagen für Prompts, vorbereitete Analysejobs, die Provider-Ausführung und eine Antwort-Leseansicht. Workflow-Zustand liegt in `data/db/analysis_workflow.sqlite`, Ausgabedateien in `data/analysis_outputs/`, private Prompt-Dateien in `data/private/`. Der vorhandene Analysepfad wird im RI-Vorhaben zunächst nicht erweitert.
- `/veroeffentlichung/` zeigt derzeit einen Platzhalter „Noch nicht umgesetzt“; die Anwendung veröffentlicht keine Inhalte automatisch auf externen Seiten.
- Die aktuelle Django-Konfiguration ist eine lokale Entwicklungsoberfläche mit `DEBUG=True`, festem Entwicklungsschlüssel und ohne Benutzeranmeldung. Sie ist noch keine Zugangskontrolle für interne Ratsunterlagen.

## Betrieb und Datenpflege

- `data/raw/`, `data/db/`, `data/processed/`, `data/private/`, `data/analysis_requests/`, `data/analysis_outputs/`, `data/models/` und `logs/` sind lokale Laufzeitbereiche und werden nicht eingecheckt. Geheimnisse gehören in den Betriebskontext oder den OS-Schlüsselring, nicht in Git.
- Dokumentpfade und Manifest-Verweise werden auf erlaubte Datenwurzeln begrenzt. SessionNet-Downloads warnen oberhalb von 25 MiB und brechen oberhalb von 100 MiB ab; bei Landkreis-Downloads gilt ein Limit von 25 MiB.
- Die reguläre Testsuite läuft mit `python -m pytest`; `live` ist standardmäßig ausgeschlossen. Für Änderungen am Code zuerst `python -m pytest -m "not integration and not live"`, bei betroffenen Workflows zusätzlich `python -m pytest -m "integration and not live"`.
- Die kanonische Version steht in `VERSION`. Das Entfernen der alten Streamlit-Konfiguration und diese Dokumentationsbereinigung ändern keine Anwendungsfunktion.
