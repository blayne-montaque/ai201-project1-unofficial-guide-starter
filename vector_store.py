from __future__ import annotations

import argparse
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer

from ingest import load_chunks, validate_chunks

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
COLLECTION_NAME = "howard_meche_guide"
DB_PATH = Path("chroma_db")
DEFAULT_TOP_K = 4
EXPECTED_CHUNK_COUNT = 127


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
    """Return the project collection, optionally deleting only that collection first."""
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


def retrieve(query: str, top_k: int = DEFAULT_TOP_K) -> list[dict[str, Any]]:
    """Return the top semantic matches for a query using the same local model."""
    if not query or not query.strip():
        raise ValueError("A non-empty query is required for retrieval.")
    if top_k <= 0:
        raise ValueError("top_k must be positive.")

    collection = get_collection(rebuild=False)
    record_count = collection.count()
    if record_count == 0:
        raise ValueError("The ChromaDB collection is empty. Run 'python vector_store.py --rebuild' first.")

    model = get_embedding_model()
    query_embedding = model.encode([query], show_progress_bar=False, convert_to_numpy=True)
    result = collection.query(
        query_embeddings=query_embedding.tolist(),
        n_results=min(top_k, record_count),
        include=["distances", "documents", "metadatas"],
    )

    hits: list[dict[str, Any]] = []
    for text, metadata, distance in zip(
        result["documents"][0], result["metadatas"][0], result["distances"][0]
    ):
        hits.append(
            {
                "text": text,
                "source": metadata.get("source", "unknown"),
                "chunk_index": int(metadata.get("chunk_index", 0)),
                "file_type": metadata.get("file_type", "unknown"),
                "topic": metadata.get("topic", "unknown"),
                "distance": float(distance),
            }
        )
    return hits


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
