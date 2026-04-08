"""Semantic search over indexed council documents in Qdrant.

Usage:
    python scripts/suche.py "Bauantrag Schulstraße"

The script embeds the query with the microsoft/harrier-oss-v1-0.6b model
using the 'web_search_query' prompt, retrieves the 5 most similar chunks
from the Qdrant collection 'ratsdokumente' and prints each result with
title, date, committee and the matching text excerpt.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "ratsdokumente"
EMBEDDING_MODEL = "microsoft/harrier-oss-v1-0.6b"
TOP_K = 5
EXCERPT_LENGTH = 300  # characters shown per result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Search query string")
    parser.add_argument(
        "--top",
        type=int,
        default=TOP_K,
        metavar="N",
        help=f"Number of results to return (default: {TOP_K})",
    )
    return parser.parse_args()


def load_model():
    """Load the SentenceTransformer model; exit on missing dependency."""
    try:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415
    except ImportError:
        print("ERROR: sentence-transformers not installed – run: pip install sentence-transformers", file=sys.stderr)
        sys.exit(1)

    return SentenceTransformer(EMBEDDING_MODEL)


def embed_query(model, query: str) -> list[float]:
    """Embed *query* using the web_search_query prompt for asymmetric retrieval."""
    vector = model.encode(
        query,
        prompt_name="web_search_query",
        convert_to_numpy=True,
    )
    return vector.tolist()


def search(query: str, top_k: int) -> None:
    """Embed query, search Qdrant and print formatted results."""
    try:
        from qdrant_client import QdrantClient  # noqa: PLC0415
    except ImportError:
        print("ERROR: qdrant-client not installed – run: pip install qdrant-client", file=sys.stderr)
        sys.exit(1)

    model = load_model()
    query_vector = embed_query(model, query)

    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k,
        with_payload=True,
    )

    if not results:
        print("Keine Ergebnisse gefunden.")
        return

    print(f"\nSuchergebnisse für: \"{query}\"\n{'=' * 60}")
    for rank, hit in enumerate(results, start=1):
        payload = hit.payload or {}
        titel = payload.get("titel") or "(kein Titel)"
        datum = payload.get("sitzungsdatum") or "(unbekannt)"
        gremium = payload.get("gremium") or "(unbekannt)"
        text = payload.get("text") or ""
        score = hit.score

        # Shorten text to a readable excerpt
        excerpt = text[:EXCERPT_LENGTH].strip()
        if len(text) > EXCERPT_LENGTH:
            excerpt += " …"

        print(f"\n[{rank}] Score: {score:.4f}")
        print(f"    Titel:   {titel}")
        print(f"    Datum:   {datum}")
        print(f"    Gremium: {gremium}")
        print(f"    Auszug:  {excerpt}")

    print()


def main() -> None:
    args = parse_args()
    search(args.query, args.top)


if __name__ == "__main__":
    main()
