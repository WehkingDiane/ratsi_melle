# Landkreis-Veröffentlichungen abrufen

[Dokumentation](../README.md)

- Landkreis-Bekanntmachungen und Amtsblätter sind eine zweite, getrennte Quelle. `scripts/fetch_landkreis_publications.py` speichert sie unter `data/raw/landkreis/` oder der mit `RATSI_LANDKREIS_DATA_DIR` gesetzten Datenwurzel.

## Ablauf

```bash
python scripts/fetch_landkreis_publications.py --source all
python scripts/build_landkreis_publications_db.py
python scripts/build_landkreis_vector_index.py
```

Für den Vektoraufbau sind vorbereitete Modelle und Qdrant erforderlich; siehe [Indizes](../suche/indizes.md). Der SQLite-Bestand lässt sich zusätzlich durchsuchen:

```bash
python scripts/search_landkreis_publications.py "Melle Genehmigung"
```
