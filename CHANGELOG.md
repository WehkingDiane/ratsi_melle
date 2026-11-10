# Changelog

Diese Übersicht dokumentiert ausgewählte bestehende Änderungen; sie ist keine vollständige Release-Historie. Der aktuelle Funktionsumfang steht im [Ist-Stand](docs/ist_stand.md).

## Dokumentationsstruktur (10.11.2026)

Die Dokumentation ist nach Funktionen in Unterordner gegliedert. Einstieg: [Wegweiser](docs/README.md). Die Anwendungsversion bleibt unverändert, da sich nur die Dokumentation ändert.

## 0.5.63 – Öffentliche SessionNet-Skripte

Seit dieser Version tragen öffentliche SessionNet-Skripte `bi` im Namen; eigene Automatisierungen müssen die neuen Namen verwenden:

| Bisher | Neu |
| --- | --- |
| `fetch_sessions.py` | `fetch_bi_sessions.py` |
| `fetch_session_from_index.py` | `fetch_bi_session_from_index.py` |
| `build_online_index_db.py` | `build_bi_online_index_db.py` |
| `build_local_index.py` | `build_bi_local_index.py` |
| `build_vector_index.py` | `build_bi_vector_index.py` |
| `check_vector_index.py` | `check_bi_vector_index.py` |
| `update_vector_index.py` | `update_bi_vector_index.py` |
| `evaluate_search.py` | `evaluate_bi_search.py` |

Landkreis-Skripte behalten ihre eindeutigen Namen. Gemeinsame Werkzeuge wie `prepare_embedding_models.py`, `migrate_legacy_index.py` und `run_web.py` bleiben neutral benannt. Die Weboberfläche verwendet die neuen Skriptpfade; bestehende Job-Aktionskennungen bleiben erhalten.
