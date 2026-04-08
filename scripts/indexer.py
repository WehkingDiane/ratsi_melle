"""Indexer: Extract text from PDFs, embed and store chunks in Qdrant.

Reads all unindexed PDF documents from the local SQLite database
(data/db/local_index.sqlite), extracts text with pdfplumber, splits
text into ~500-word chunks with 50-word overlap, creates sentence
embeddings (microsoft/harrier-oss-v1-0.6b) and upserts each chunk as
a point into the Qdrant collection 'ratsdokumente' (localhost:6333).
Successfully indexed documents are flagged with indiziert=1 so that
subsequent runs skip them.
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.paths import LOCAL_INDEX_DB

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

CHUNK_SIZE = 500       # words per chunk
CHUNK_OVERLAP = 50     # words of overlap between consecutive chunks
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "ratsdokumente"
EMBEDDING_MODEL = "microsoft/harrier-oss-v1-0.6b"


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

def ensure_indiziert_column(conn: sqlite3.Connection) -> None:
    """Add 'indiziert' column to documents if it doesn't exist yet."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(documents)").fetchall()}
    if "indiziert" not in columns:
        conn.execute("ALTER TABLE documents ADD COLUMN indiziert INTEGER DEFAULT 0")
        conn.commit()
        logger.info("Added 'indiziert' column to documents table.")


def fetch_unindexed_documents(conn: sqlite3.Connection) -> list[dict]:
    """Return all unindexed PDF documents joined with their session metadata."""
    rows = conn.execute(
        """
        SELECT
            d.id,
            d.title,
            d.local_path,
            d.content_type,
            s.date  AS sitzungsdatum,
            s.committee AS gremium
        FROM documents d
        JOIN sessions s ON d.session_id = s.session_id
        WHERE (d.indiziert IS NULL OR d.indiziert = 0)
          AND (
              LOWER(COALESCE(d.content_type, '')) LIKE '%pdf%'
              OR LOWER(COALESCE(d.local_path,  '')) LIKE '%.pdf'
          )
        """
    ).fetchall()
    columns = ["id", "title", "local_path", "content_type", "sitzungsdatum", "gremium"]
    return [dict(zip(columns, row)) for row in rows]


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def resolve_pdf_path(local_path: str | None) -> Path | None:
    """Try to resolve a stored local_path to an existing file.

    The path stored in SQLite may be absolute or relative to the repo root.
    """
    if not local_path:
        return None
    for candidate in (Path(local_path), REPO_ROOT / local_path):
        if candidate.is_file():
            return candidate
    return None


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def extract_text_pdfplumber(pdf_path: Path) -> str:
    """Extract plain text from a PDF using pdfplumber."""
    try:
        import pdfplumber  # noqa: PLC0415
    except ImportError:
        logger.error("pdfplumber not installed – run: pip install pdfplumber")
        return ""

    try:
        pages: list[str] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(text)
        return "\n\n".join(pages)
    except Exception as exc:  # noqa: BLE001
        logger.warning("pdfplumber extraction failed for %s: %s", pdf_path.name, exc)
        return ""


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split *text* into word-based chunks with *overlap* words of context.

    Each chunk contains at most *chunk_size* words.  Consecutive chunks
    share the last *overlap* words of the preceding chunk.
    """
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    step = chunk_size - overlap
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        if end >= len(words):
            break
        start += step
    return chunks


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def load_model():
    """Load the SentenceTransformer model; exit on missing dependency."""
    try:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415
    except ImportError:
        logger.error("sentence-transformers not installed – run: pip install sentence-transformers")
        sys.exit(1)

    logger.info("Loading embedding model '%s' …", EMBEDDING_MODEL)
    return SentenceTransformer(EMBEDDING_MODEL)


# ---------------------------------------------------------------------------
# Qdrant helpers
# ---------------------------------------------------------------------------

def get_or_create_collection(client, vector_size: int) -> None:
    """Create Qdrant collection if it does not already exist."""
    from qdrant_client.models import Distance, VectorParams  # noqa: PLC0415

    existing = {col.name for col in client.get_collections().collections}
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        logger.info("Created Qdrant collection '%s' (dim=%d).", COLLECTION_NAME, vector_size)
    else:
        logger.info("Qdrant collection '%s' already exists.", COLLECTION_NAME)


# ---------------------------------------------------------------------------
# Main routine
# ---------------------------------------------------------------------------

def index_documents() -> None:
    """Run the full indexing pipeline."""
    try:
        from qdrant_client import QdrantClient  # noqa: PLC0415
        from qdrant_client.models import PointStruct  # noqa: PLC0415
    except ImportError:
        logger.error("qdrant-client not installed – run: pip install qdrant-client")
        sys.exit(1)

    if not LOCAL_INDEX_DB.exists():
        logger.error("SQLite database not found: %s", LOCAL_INDEX_DB)
        sys.exit(1)

    model = load_model()
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    # Determine vector dimension from a single test encoding.
    test_vec = model.encode("test", convert_to_numpy=True)
    vector_size = len(test_vec)
    get_or_create_collection(client, vector_size)

    with sqlite3.connect(LOCAL_INDEX_DB) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        ensure_indiziert_column(conn)
        docs = fetch_unindexed_documents(conn)

    logger.info("Found %d unindexed PDF document(s) to process.", len(docs))
    if not docs:
        logger.info("Nothing to index – all documents are already indexed.")
        return

    indexed_docs = 0
    total_chunks = 0

    with sqlite3.connect(LOCAL_INDEX_DB) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        for doc in docs:
            doc_id: int = doc["id"]
            title: str = doc["title"] or ""
            sitzungsdatum: str = doc["sitzungsdatum"] or ""
            gremium: str = doc["gremium"] or ""

            pdf_path = resolve_pdf_path(doc["local_path"])
            if pdf_path is None:
                logger.warning(
                    "PDF file not found for doc_id=%d (path=%s) – skipping.",
                    doc_id,
                    doc["local_path"],
                )
                continue

            text = extract_text_pdfplumber(pdf_path)
            if not text.strip():
                logger.warning(
                    "No text extracted from doc_id=%d (%s) – skipping.",
                    doc_id,
                    pdf_path.name,
                )
                continue

            chunks = split_into_chunks(text)
            if not chunks:
                logger.warning("No chunks for doc_id=%d – skipping.", doc_id)
                continue

            logger.info(
                "Indexing doc_id=%d '%s': %d chunk(s) …",
                doc_id,
                title[:60],
                len(chunks),
            )

            embeddings = model.encode(chunks, convert_to_numpy=True, show_progress_bar=False)

            points = [
                PointStruct(
                    id=doc_id * 100_000 + chunk_idx,
                    vector=embedding.tolist(),
                    payload={
                        "doc_id": doc_id,
                        "chunk_index": chunk_idx,
                        "text": chunk_text,
                        "sitzungsdatum": sitzungsdatum,
                        "gremium": gremium,
                        "titel": title,
                    },
                )
                for chunk_idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings))
            ]

            client.upsert(collection_name=COLLECTION_NAME, points=points)
            total_chunks += len(points)

            conn.execute("UPDATE documents SET indiziert = 1 WHERE id = ?", (doc_id,))
            conn.commit()
            indexed_docs += 1

    logger.info(
        "Indexing complete: %d document(s), %d chunk(s) stored in Qdrant.",
        indexed_docs,
        total_chunks,
    )


if __name__ == "__main__":
    index_documents()
