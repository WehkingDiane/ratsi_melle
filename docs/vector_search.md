# Semantische Suche (Vector Search)

Dieses Dokument beschreibt die Architektur und Funktionsweise der semantischen Suchfunktion, die auf Basis von Vektor-Embeddings und einer lokalen Qdrant-Datenbank arbeitet.

## Überblick

Die semantische Suche ermöglicht es, Dokumente aus dem Ratsinformationssystem inhaltlich zu finden – ohne dass exakte Schlüsselwörter im Titel oder Text vorkommen müssen. Stattdessen wird die *Bedeutung* einer Suchanfrage mit der *Bedeutung* der Dokumentinhalte verglichen.

**Beispiel:** Eine Suche nach „Schulfinanzierung" findet auch Dokumente mit Titeln wie „Haushaltsmittel Bildungsbereich" oder „Beschlussvorlage Ganztagesbetreuung", sofern deren Inhalt thematisch passt.

---

## Architektur

```
SQLite (local_index.sqlite)
    ↓  session_path + local_path
PDF-Dateien (data/raw/)
    ↓  pypdf Textextraktion (max. 10 Seiten)
Harrier Embedding-Modell (microsoft/harrier-oss-v1-0.6b)
    ↓  1024-dimensionaler Vektor pro Dokument
Qdrant Local Store (data/db/qdrant/)
    ↓  Nearest-Neighbour-Suche (Cosine Similarity)
Suchergebnisse mit doc_id → Metadaten aus SQLite
```

### Komponenten

| Komponente | Datei | Aufgabe |
|---|---|---|
| Embedding-Service | `src/analysis/embeddings.py` | Lädt Harrier, erzeugt Vektoren für Dokumente und Anfragen |
| Vector Store | `src/analysis/vector_store.py` | Qdrant-Wrapper: Collection anlegen, upsert, suchen |
| Indexierungsskript | `scripts/build_vector_index.py` | Liest SQLite, extrahiert PDF-Text, schreibt Vektoren nach Qdrant |

---

## Embedding-Modell: Harrier

Das Modell [`microsoft/harrier-oss-v1-0.6b`](https://huggingface.co/microsoft/harrier-oss-v1-0.6b) ist ein mehrsprachiges Text-Embedding-Modell von Microsoft.

| Eigenschaft | Wert |
|---|---|
| Parameter | 0,6 Milliarden |
| Embedding-Dimension | 1.024 |
| Maximale Kontextlänge | 32.768 Token |
| Sprachen | 94 inkl. Deutsch |
| Pooling | Last-token + L2-Normalisierung |

Das Modell wird beim ersten Aufruf automatisch von HuggingFace heruntergeladen (~1,2 GB) und danach lokal gecacht. Eine Internetverbindung ist nur beim ersten Start erforderlich.

### Unterschied Dokument- vs. Anfragen-Embedding

Dokumente werden ohne Präfix eingebettet. Suchanfragen erhalten einen Instruction-Präfix, der das Modell auf Retrieval ausrichtet:

```
Instruct: Retrieve semantically similar municipal council documents
Query: <Suchanfrage>
```

---

## Vektor-Datenbank: Qdrant

Qdrant läuft vollständig lokal im Dateimodus – kein Server, kein Docker erforderlich.

**Speicherort:** `data/db/qdrant/`  
**Collection:** `ratsi_documents`  
**Distanzmaß:** Cosine Similarity  

Jeder Eintrag enthält:
- Den 1024-dimensionalen Vektor
- Payload mit Metadaten: `session_id`, `title`, `document_type`, `agenda_item`, `date`, `committee`, `url`, `local_path`

---

## Indexierung

### Erstmalig

```bash
# Abhängigkeiten installieren (einmalig)
pip install sentence-transformers qdrant-client
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Index aufbauen
python scripts/build_vector_index.py
```

### Inkrementell

Das Skript ist idempotent: Bereits indexierte Dokument-IDs werden übersprungen. Neue Dokumente (nach `fetch_sessions` + `build_local_index`) können jederzeit nachindexiert werden:

```bash
python scripts/build_vector_index.py
```

### Vollständiger Neuaufbau

```bash
# Qdrant-Verzeichnis löschen und neu aufbauen
# Windows:
Remove-Item -Recurse -Force data/db/qdrant
# Linux/Mac:
rm -rf data/db/qdrant

python scripts/build_vector_index.py
```

Ein Neuaufbau ist nötig wenn sich die Textextraktion oder das Embedding-Modell geändert hat.

### Parameter

```
python scripts/build_vector_index.py --help

--db          Pfad zur SQLite-Datenbank (Standard: data/db/local_index.sqlite)
--qdrant-dir  Pfad zum Qdrant-Verzeichnis (Standard: data/db/qdrant/)
--limit N     Nur die ersten N Dokumente indexieren (für Tests)
```

---

## Textextraktion

Pro Dokument wird folgender Text eingebettet:

1. **PDF-Volltext** – via `pypdf` aus der lokalen PDF-Datei (max. 10 Seiten). Der `local_path` in SQLite ist relativ zum Session-Ordner (`session_path`); beide werden kombiniert um den absoluten Pfad aufzulösen.
2. **Fallback** – wenn keine lokale Datei vorhanden oder der Text leer ist: `Titel + Dokumenttyp`

Dokumente mit reinen Scan-PDFs (keine eingebettete Textebene) fallen ebenfalls auf den Fallback zurück. Eine OCR-Integration ist perspektivisch über `src/analysis/extraction_pipeline.py` möglich.

---

## Score-Interpretation

Die Suche gibt einen Cosine-Similarity-Score zwischen 0 und 1 zurück (angezeigt als Prozent):

| Score | Bedeutung |
|---|---|
| ≥ 70 % | Starke inhaltliche Übereinstimmung |
| 45–69 % | Thematisch verwandt |
| < 45 % | Schwache Übereinstimmung, meist nicht relevant |

**Wichtig:** Ein Wert von 70 % bedeutet bei semantischer Suche einen guten Treffer – nicht wie bei Keyword-Suche, wo 100 % der Normalfall wäre. Die Skala verhält sich grundlegend anders, weil Vektoren nie identisch sind, solange der Text nicht fast wortgleich ist.

---

## Abhängigkeiten

```
sentence-transformers>=3.0   # Harrier-Integration
qdrant-client>=1.12          # Lokaler Vektorspeicher
torch                        # Laufzeitumgebung für das Modell
                             # Installation: pip install torch --index-url https://download.pytorch.org/whl/cpu
```

`torch` wird nicht in `requirements.txt` eingetragen, da die CPU-Variante über einen eigenen Index-URL installiert werden muss und die Dateigröße (~2 GB) bewusst eine manuelle Entscheidung erfordert.

---

## Aktuelle Einschränkungen

- **Keine GPU-Beschleunigung konfiguriert** – das Modell läuft auf CPU, die Indexierung dauert je nach Dokumentanzahl mehrere Minuten.
- **OCR nicht integriert** – Scan-PDFs ohne Textebene werden nur über Titel eingebettet.
- **Keine Hybridsuche** – Keyword-Treffer (exakte Namen wie „CDU-Fraktion") werden nicht gesondert behandelt. Eine Kombination mit SQLite FTS5 ist als Erweiterung vorgesehen.
- **UI vorläufig** – die aktuelle Suchoberfläche in der Streamlit-UI ist ein erster Prototyp und wird in einer späteren Version überarbeitet.
