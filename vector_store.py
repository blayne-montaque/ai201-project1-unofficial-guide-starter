from __future__ import annotations

import argparse
from pathlib import Path

from sentence_transformers import SentenceTransformer

from ingest import load_chunks

import chromadb

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
COLLECTION_NAME = "howard_meche_guide"
DB_PATH = Path("chroma_db")


def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL)


def get_collection(rebuild: bool = False):
    client = chromadb.PersistentClient(path=str(DB_PATH))

    if rebuild:
        try:
            client.delete_collection(name=COLLECTION_NAME)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    return collection


def index_documents(rebuild: bool = False) -> dict:
    chunks = load_chunks()
    if not chunks:
        raise ValueError("No valid chunks found in documents/. Add source .txt files and rerun.")

    collection = get_collection(rebuild=rebuild)
    model = get_embedding_model()

    ids = [f"{item['source']}::{item['chunk_index']}" for item in chunks]
    documents = [item["text"] for item in chunks]
    metadatas = [{"source": item["source"], "chunk_index": item["chunk_index"]} for item in chunks]
    embeddings = model.encode(documents, show_progress_bar=False)

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings.tolist(),
    )

    return {
        "collection_name": COLLECTION_NAME,
        "document_count": len(chunks),
        "ids": ids[:5],
    }


def retrieve(query: str, top_k: int = 4) -> list[dict]:
    collection = get_collection(rebuild=False)
    model = get_embedding_model()
    query_embedding = model.encode([query], show_progress_bar=False).tolist()

    result = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
        include=["distances", "documents", "metadatas"],
    )

    hits = []
    for text, metadata, distance in zip(result["documents"][0], result["metadatas"][0], result["distances"][0]):
        hits.append(
            {
                "text": text,
                "source": metadata.get("source", "unknown"),
                "chunk_index": int(metadata.get("chunk_index", 0)),
                "distance": float(distance),
            }
        )
    return hits


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or rebuild the Howard Mechanical Engineering ChromaDB index.")
    parser.add_argument("--rebuild", action="store_true", help="Delete and rebuild the collection.")
    args = parser.parse_args()

    result = index_documents(rebuild=args.rebuild)
    print(f"Collection: {result['collection_name']}")
    print(f"Indexed documents/chunks: {result['document_count']}")
    print(f"Sample IDs: {result['ids']}")


if __name__ == "__main__":
    main()
