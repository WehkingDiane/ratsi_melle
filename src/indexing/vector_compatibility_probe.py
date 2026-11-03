"""Read-only sample evidence for library upgrades; never releases an index."""

from hashlib import sha256
import heapq
import math

from src.indexing.legacy_index_inspection import (
    LegacyInspectionError, _check_hints, _check_schema, _compare_vectors, _sparse_pairs,
)

COLLECTION = "ratsi_passages"


def unit(vector):
    """Validate and normalize a dense vector."""
    values = [float(v) for v in vector]
    norm = math.hypot(*values)
    if not math.isfinite(norm) or norm == 0:
        raise ValueError("Dense vector must have finite, nonzero norm")
    return [v / norm for v in values]


def vector_metrics(stored, candidate, dimension):
    """Measure both vector families with the existing migration tolerances."""
    old, new = stored["harrier"], candidate["dense_vector"]
    if len(old) != dimension or len(new) != dimension:
        raise ValueError("Unexpected dense dimension")
    a, b = unit(old), unit(new)
    sparse_old = dict(_sparse_pairs(stored["bm25"]))
    sparse_new = dict(_sparse_pairs(candidate["sparse_vector"]))
    try:
        _compare_vectors(stored, candidate, dimension)
        mismatch = None
    except LegacyInspectionError as exc:
        mismatch = exc.code
    return {
        "strict_match": mismatch is None, "mismatch": mismatch,
        "dense_cosine": max(-1.0, min(1.0, sum(x*y for x, y in zip(a, b, strict=True)))),
        "dense_max_abs_delta": max(abs(float(x)-y) for x, y in zip(old, b, strict=True)),
        "sparse_indices_equal": sparse_old.keys() == sparse_new.keys(),
        "sparse_max_abs_delta": max((abs(sparse_old.get(i, 0)-sparse_new.get(i, 0))
                                     for i in sparse_old.keys() | sparse_new.keys()), default=0),
    }


def _ranking(ids, vectors, query, k):
    dense_query = unit(query["dense_vector"])
    sparse_query = dict(_sparse_pairs(query["sparse_vector"]))
    dense, sparse = {}, {}
    for point_id, vector in zip(ids, vectors, strict=True):
        dense[point_id] = sum(a*b for a, b in zip(unit(vector["harrier"]), dense_query, strict=True))
        sparse[point_id] = sum(sparse_query.get(i, 0)*v for i, v in _sparse_pairs(vector["bm25"]))
    ranks = [sorted(ids, key=lambda i: (-scores[i], i)) for scores in (dense, sparse)]
    fused = {i: 0.0 for i in ids}
    for ranking in ranks:
        for rank, point_id in enumerate(ranking, 1):
            fused[point_id] += 1 / (60 + rank)
    return sorted(ids, key=lambda i: (-fused[i], i))[:k]


def probe(client, stored_contract, candidate_contract, vectorizer, queries, encode_query,
          *, sample_size=128, batch_size=4, top_k=10):
    """Compare a deterministic stratified sample and offline query rankings."""
    if min(sample_size, batch_size, top_k) < 1:
        raise ValueError("Sample size, batch size and top-k must be positive")
    differences = {k: {"stored": v, "candidate": candidate_contract.as_dict()[k]}
                   for k, v in stored_contract.as_dict().items()
                   if candidate_contract.as_dict()[k] != v}
    if set(differences) - {"manifest_sha256"}:
        raise ValueError("Probe requires identical model revisions, dimension and pipeline")
    _check_schema(client.get_collection(COLLECTION), stored_contract)
    before_count = client.count(collection_name=COLLECTION, exact=True).count
    pools = {name: [] for name in ("short", "long", "ocr", "numbers", "umlauts", "other")}

    def scan():
        offset, seen, signature = None, set(), sha256()
        while True:
            records, next_offset = client.scroll(collection_name=COLLECTION, limit=256,
                                                 offset=offset, with_payload=True, with_vectors=False)
            for record in records:
                if type(record.id) is not int or record.id in seen:
                    raise ValueError("Invalid or duplicate point ID")
                seen.add(record.id)
                payload = record.payload
                _check_hints(payload, stored_contract)
                text = payload.get("text")
                if payload.get("committed") is not True or not isinstance(text, str) or not text:
                    raise ValueError("Passage lacks committed original text")
                signature.update(f"{record.id}:".encode() + sha256(text.encode()).digest())
                yield record.id, payload, text
            if next_offset is None:
                break
            if not records or next_offset == offset:
                raise ValueError("Incomplete scroll")
            offset = next_offset
        scan.count, scan.digest = len(seen), signature.hexdigest()

    for point_id, payload, text in scan():
        tags = ["short" if len(text) < 300 else "long" if len(text) > 2000 else "other"]
        if "ocr" in str(payload.get("extraction_method", "")).lower():
            tags.append("ocr")
        if any(c.isdigit() for c in text):
            tags.append("numbers")
        if any(c in text for c in "äöüÄÖÜß"):
            tags.append("umlauts")
        score = int.from_bytes(sha256(f"probe-v1:{point_id}".encode()).digest(), "big")
        for tag in tags:
            heapq.heappush(pools[tag], (-score, point_id))
            if len(pools[tag]) > sample_size:
                heapq.heappop(pools[tag])
    if not scan.count or scan.count != before_count:
        raise ValueError("Empty or changing collection")
    before_digest = scan.digest
    ordered = {tag: [i for _, i in sorted(pool, reverse=True)] for tag, pool in pools.items()}
    selected = []
    for row in range(sample_size):
        for items in ordered.values():
            if row < len(items) and items[row] not in selected and len(selected) < sample_size:
                selected.append(items[row])
    records = client.retrieve(collection_name=COLLECTION, ids=selected, with_payload=True, with_vectors=True)
    by_id = {r.id: r for r in records}
    if set(by_id) != set(selected):
        raise ValueError("Sample incomplete")
    results, new_vectors = [], []
    for start in range(0, len(selected), batch_size):
        batch = selected[start:start+batch_size]
        texts = [by_id[i].payload["text"] for i in batch]
        calculated = vectorizer.encode_documents(texts)
        for point_id, candidate in zip(batch, calculated, strict=True):
            _check_hints(by_id[point_id].payload, stored_contract)
            metrics = vector_metrics(by_id[point_id].vector, candidate, stored_contract.vector_dimension)
            results.append({"point_id": point_id, **metrics})
            new_vectors.append({"harrier": candidate["dense_vector"], "bm25": candidate["sparse_vector"]})
    comparisons = []
    for query in queries:
        encoded = encode_query(query)
        old = _ranking(selected, [by_id[i].vector for i in selected], encoded, top_k)
        new = _ranking(selected, new_vectors, encoded, top_k)
        comparisons.append({"query": query, "stored_top_ids": old, "candidate_top_ids": new,
                            "top_k_overlap": len(set(old) & set(new)) / len(old),
                            "same_order": old == new})
    after = client.retrieve(collection_name=COLLECTION, ids=selected, with_payload=True, with_vectors=True)
    if {r.id: r for r in after} != by_id:
        raise ValueError("Sample changed during probe")
    for _ in scan():
        pass
    if scan.digest != before_digest or client.count(collection_name=COLLECTION, exact=True).count != before_count:
        raise ValueError("Collection changed during probe")
    matches = sum(r["strict_match"] for r in results)
    stable_queries = sum(q["same_order"] for q in comparisons)
    return {
        "result": "sample_matches" if matches == len(results) and stable_queries == len(comparisons) else "differences_found",
        "summary": {"sample_size": len(results), "strict_matches": matches,
                    "minimum_dense_cosine": min(r["dense_cosine"] for r in results),
                    "maximum_dense_abs_delta": max(r["dense_max_abs_delta"] for r in results),
                    "queries": len(comparisons), "queries_with_same_order": stable_queries},
        "migration_authorized": False, "collection": COLLECTION, "point_count": before_count,
        "source_texts_sha256": before_digest,
        "stored_contract": stored_contract.as_dict(), "candidate_contract": candidate_contract.as_dict(),
        "contract_differences": differences, "sample": results, "queries": comparisons,
        "sample_selection": "deterministic hash, round-robin short/long/OCR/numbers/umlauts/other",
        "limitations": ["Sample evidence only; no automatic release or proof for every document.",
                        "Candidate query embeddings against stored and recalculated sample vectors.",
                        "Offline sample RRF (constant 60), not production search or an old-query baseline.",
                        "Pause concurrent writes; drift checks are not a database snapshot."],
    }
