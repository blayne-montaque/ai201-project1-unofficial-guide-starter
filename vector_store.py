from __future__ import annotations

import argparse
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from ingest import load_chunks, validate_chunks

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
COLLECTION_NAME = "howard_meche_guide"
DB_PATH = Path("chroma_db")
DEFAULT_TOP_K = 4
EXPECTED_CHUNK_COUNT = 127
RRF_K = 60
RETRIEVAL_MODES = {"semantic", "bm25", "hybrid"}
FILTERABLE_METADATA_FIELDS = {"source", "file_type", "topic", "chunk_index"}
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Load the local embedding model once per Python process."""
    return SentenceTransformer(EMBEDDING_MODEL)


def get_client() -> chromadb.PersistentClient:
    """Open the project's persistent ChromaDB directory."""
    return chromadb.PersistentClient(path=str(DB_PATH))


def _collection_names(client: chromadb.PersistentClient) -> set[str]:
    """Support the collection-list return type used by installed Chroma versions."""
    return {str(getattr(collection, "name", collection)) for collection in client.list_collections()}


def get_collection(rebuild: bool = False):
    """Return the baseline semantic collection, optionally rebuilding only it."""
    client = get_client()
    if rebuild and COLLECTION_NAME in _collection_names(client):
        client.delete_collection(name=COLLECTION_NAME)

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def chunk_id(chunk: dict[str, Any]) -> str:
    """Create a deterministic, unique ChromaDB ID for one ingestion chunk."""
    return f"{chunk['source']}::{chunk['chunk_index']}"


def chunk_metadata(chunk: dict[str, Any]) -> dict[str, Any]:
    """Keep the ingestion metadata needed for retrieval and later attribution."""
    return {
        "source": chunk["source"],
        "chunk_index": int(chunk["chunk_index"]),
        "file_type": chunk["file_type"],
        "topic": chunk["topic"],
    }


def verify_collection(collection, chunks: list[dict[str, Any]], ids: list[str]) -> dict[str, Any]:
    """Confirm stored count and one representative record match ingestion output."""
    record_count = collection.count()
    if record_count != len(chunks):
        raise ValueError(
            f"ChromaDB record count ({record_count}) does not match ingestion chunk count ({len(chunks)}). "
            "Run 'python vector_store.py --rebuild' to recreate this collection."
        )

    stored = collection.get(ids=[ids[0]], include=["documents", "metadatas"])
    stored_documents = stored.get("documents") or []
    stored_metadatas = stored.get("metadatas") or []
    if not stored_documents or not stored_documents[0] or not stored_metadatas:
        raise ValueError("ChromaDB validation failed: the first stored record is missing text or metadata.")

    expected = chunks[0]
    metadata = stored_metadatas[0]
    if (
        stored_documents[0] != expected["text"]
        or metadata.get("source") != expected["source"]
        or int(metadata.get("chunk_index", -1)) != expected["chunk_index"]
    ):
        raise ValueError("ChromaDB validation failed: the first stored record does not match ingestion output.")

    return {
        "source": metadata["source"],
        "chunk_index": int(metadata["chunk_index"]),
        "file_type": metadata.get("file_type", "unknown"),
        "topic": metadata.get("topic", "unknown"),
        "text_length": len(stored_documents[0]),
    }


def index_documents(rebuild: bool = False) -> dict[str, Any]:
    """Embed every validated ingestion chunk and store it in persistent ChromaDB."""
    chunks = load_chunks()
    validate_chunks(chunks)
    if len(chunks) != EXPECTED_CHUNK_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_CHUNK_COUNT} validated ingestion chunks, but found {len(chunks)}. "
            "Fix the ingestion pipeline before building the vector store."
        )

    ids = [chunk_id(chunk) for chunk in chunks]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate deterministic chunk IDs were generated from ingestion metadata.")

    documents = [chunk["text"] for chunk in chunks]
    metadatas = [chunk_metadata(chunk) for chunk in chunks]
    model = get_embedding_model()
    embeddings = model.encode(documents, show_progress_bar=False, convert_to_numpy=True)

    collection = get_collection(rebuild=rebuild)
    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings.tolist(),
    )
    sample_record = verify_collection(collection, chunks, ids)

    return {
        "embedding_model": EMBEDDING_MODEL,
        "chunks_loaded": len(chunks),
        "chunks_embedded": len(embeddings),
        "records_stored": collection.count(),
        "collection_name": COLLECTION_NAME,
        "persistence_directory": str(DB_PATH),
        "sample_record": sample_record,
    }


def tokenize(text: str) -> list[str]:
    """Tokenize text consistently for the lexical BM25 index."""
    return TOKEN_PATTERN.findall(text.lower())


def _validate_filters(filters: dict[str, Any] | None) -> dict[str, Any]:
    """Validate equality filters against real persisted chunk metadata fields."""
    if not filters:
        return {}
    unknown_fields = set(filters) - FILTERABLE_METADATA_FIELDS
    if unknown_fields:
        raise ValueError(f"Unsupported metadata filter field(s): {', '.join(sorted(unknown_fields))}.")
    if any(value is None or value == "" for value in filters.values()):
        raise ValueError("Metadata filter values must be non-empty.")
    return dict(filters)


def _chroma_where(filters: dict[str, Any]) -> dict[str, Any] | None:
    """Build a Chroma equality filter for one or more metadata constraints."""
    if not filters:
        return None
    clauses = [{field: value} for field, value in filters.items()]
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def _metadata_matches(chunk: dict[str, Any], filters: dict[str, Any]) -> bool:
    return all(chunk.get(field) == value for field, value in filters.items())


def _semantic_hits(query: str, limit: int, filters: dict[str, Any]) -> list[dict[str, Any]]:
    """Return semantic candidates, including ranks and Chroma cosine distances."""
    collection = get_collection(rebuild=False)
    record_count = collection.count()
    if record_count == 0:
        raise ValueError("The ChromaDB collection is empty. Run 'python vector_store.py --rebuild' first.")

    model = get_embedding_model()
    query_embedding = model.encode([query], show_progress_bar=False, convert_to_numpy=True)
    result = collection.query(
        query_embeddings=query_embedding.tolist(),
        n_results=min(limit, record_count),
        where=_chroma_where(filters),
        include=["distances", "documents", "metadatas"],
    )

    hits: list[dict[str, Any]] = []
    for rank, (record_id, text, metadata, distance) in enumerate(
        zip(result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]),
        start=1,
    ):
        hits.append(
            {
                "id": record_id,
                "text": text,
                "source": metadata.get("source", "unknown"),
                "chunk_index": int(metadata.get("chunk_index", 0)),
                "file_type": metadata.get("file_type", "unknown"),
                "topic": metadata.get("topic", "unknown"),
                "rank": rank,
                "semantic_rank": rank,
                "distance": float(distance),
                "bm25_rank": None,
                "bm25_score": None,
                "rrf_score": None,
            }
        )
    return hits


@lru_cache(maxsize=1)
def _bm25_corpus() -> tuple[tuple[dict[str, Any], ...], BM25Okapi]:
    """Build a process-local BM25 index over the same validated ingestion chunks."""
    chunks = load_chunks()
    validate_chunks(chunks)
    if len(chunks) != EXPECTED_CHUNK_COUNT:
        raise ValueError(f"Expected {EXPECTED_CHUNK_COUNT} chunks for BM25, but found {len(chunks)}.")
    corpus = tuple(chunks)
    return corpus, BM25Okapi([tokenize(str(chunk["text"])) for chunk in corpus])


def _bm25_hits(query: str, limit: int, filters: dict[str, Any]) -> list[dict[str, Any]]:
    """Return lexical BM25 candidates over the current ingestion corpus."""
    corpus, bm25 = _bm25_corpus()
    scores = bm25.get_scores(tokenize(query))
    candidates = [
        (position, chunk, float(scores[position]))
        for position, chunk in enumerate(corpus)
        if _metadata_matches(chunk, filters)
    ]
    candidates.sort(key=lambda item: (-item[2], str(item[1]["source"]), int(item[1]["chunk_index"])))

    hits: list[dict[str, Any]] = []
    for rank, (_position, chunk, score) in enumerate(candidates[:limit], start=1):
        hits.append(
            {
                "id": chunk_id(chunk),
                "text": chunk["text"],
                "source": chunk["source"],
                "chunk_index": int(chunk["chunk_index"]),
                "file_type": chunk["file_type"],
                "topic": chunk["topic"],
                "rank": rank,
                "semantic_rank": None,
                "distance": None,
                "bm25_rank": rank,
                "bm25_score": score,
                "rrf_score": None,
            }
        )
    return hits


def _hybrid_hits(query: str, top_k: int, filters: dict[str, Any]) -> list[dict[str, Any]]:
    """Fuse complete semantic and BM25 rankings with reciprocal rank fusion."""
    corpus, _bm25 = _bm25_corpus()
    candidate_count = sum(_metadata_matches(chunk, filters) for chunk in corpus)
    if not candidate_count:
        return []

    semantic_hits = _semantic_hits(query, candidate_count, filters)
    bm25_hits = _bm25_hits(query, candidate_count, filters)
    semantic_by_id = {hit["id"]: hit for hit in semantic_hits}
    bm25_by_id = {hit["id"]: hit for hit in bm25_hits}
    fused: list[dict[str, Any]] = []

    for record_id in semantic_by_id.keys() | bm25_by_id.keys():
        semantic_hit = semantic_by_id.get(record_id)
        bm25_hit = bm25_by_id.get(record_id)
        semantic_rank = semantic_hit["semantic_rank"] if semantic_hit else None
        bm25_rank = bm25_hit["bm25_rank"] if bm25_hit else None
        rrf_score = (
            (1 / (RRF_K + semantic_rank) if semantic_rank else 0)
            + (1 / (RRF_K + bm25_rank) if bm25_rank else 0)
        )
        base = semantic_hit or bm25_hit
        fused.append(
            {
                **base,
                "semantic_rank": semantic_rank,
                "distance": semantic_hit["distance"] if semantic_hit else None,
                "bm25_rank": bm25_rank,
                "bm25_score": bm25_hit["bm25_score"] if bm25_hit else None,
                "rrf_score": rrf_score,
            }
        )

    fused.sort(
        key=lambda hit: (
            -float(hit["rrf_score"]),
            hit["semantic_rank"] or candidate_count + 1,
            hit["bm25_rank"] or candidate_count + 1,
            str(hit["id"]),
        )
    )
    for rank, hit in enumerate(fused[:top_k], start=1):
        hit["rank"] = rank
    return fused[:top_k]


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    mode: str = "semantic",
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve current chunks using independent semantic, BM25, or RRF hybrid ranking."""
    if not query or not query.strip():
        raise ValueError("A non-empty query is required for retrieval.")
    if top_k <= 0:
        raise ValueError("top_k must be positive.")
    if mode not in RETRIEVAL_MODES:
        raise ValueError(f"Unsupported retrieval mode '{mode}'. Choose from {', '.join(sorted(RETRIEVAL_MODES))}.")

    validated_filters = _validate_filters(filters)
    if mode == "semantic":
        return _semantic_hits(query.strip(), top_k, validated_filters)
    if mode == "bm25":
        return _bm25_hits(query.strip(), top_k, validated_filters)
    return _hybrid_hits(query.strip(), top_k, validated_filters)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Howard Mechanical Engineering ChromaDB index.")
    parser.add_argument("--rebuild", action="store_true", help="Recreate only this project's ChromaDB collection.")
    args = parser.parse_args()

    result = index_documents(rebuild=args.rebuild)
    print(f"Embedding model: {result['embedding_model']}")
    print(f"Chunks loaded from ingestion: {result['chunks_loaded']}")
    print(f"Chunks embedded: {result['chunks_embedded']}")
    print(f"Records stored in ChromaDB: {result['records_stored']}")
    print(f"Collection: {result['collection_name']}")
    print(f"Persistence directory: {result['persistence_directory']}")
    print(
        "Validated stored record: "
        f"source={result['sample_record']['source']} | "
        f"chunk_index={result['sample_record']['chunk_index']} | "
        f"file_type={result['sample_record']['file_type']} | "
        f"topic={result['sample_record']['topic']} | "
        f"text_length={result['sample_record']['text_length']}"
    )


if __name__ == "__main__":
    main()
