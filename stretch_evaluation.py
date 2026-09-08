from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from ingest import load_chunks, validate_chunks
from query import ask
from vector_store import get_embedding_model, retrieve


COMPARISON_CASES = [
    {
        "name": "Thermodynamics topics",
        "query": "What topics are listed for MEEG-304 Thermodynamics in the guide?",
        "expected_source": "thermodynamics.txt",
    },
    {
        "name": "MATLAB",
        "query": "Which course explicitly teaches programming and software such as MATLAB?",
        "expected_source": "engineering_computations.txt",
    },
    {
        "name": "Heat Transfer",
        "query": "What three major modes of heat transfer should a student expect to study in Heat Transfer?",
        "expected_source": "heat_transfer.txt",
    },
]

MEMORY_DEMOS = [
    [
        "What three modes of heat transfer are covered in MEEG-403 Heat Transfer?",
        "What are its prerequisites?",
    ],
    [
        "Tell me about MEEG-207 Introduction to Engineering Computations.",
        "What software does that course use?",
    ],
]


def compact_hit(hit: dict[str, Any], include_preview: bool = False) -> dict[str, Any]:
    """Serialize useful ranking evidence without duplicating complete corpus text."""
    result = {
        "rank": int(hit["rank"]),
        "source": hit["source"],
        "chunk_index": int(hit["chunk_index"]),
        "distance": round(float(hit["distance"]), 4) if hit.get("distance") is not None else None,
        "bm25_score": round(float(hit["bm25_score"]), 4) if hit.get("bm25_score") is not None else None,
        "rrf_score": round(float(hit["rrf_score"]), 6) if hit.get("rrf_score") is not None else None,
    }
    if include_preview:
        result["text_preview"] = str(hit["text"])[:260]
    return result


def expected_rank(hits: list[dict[str, Any]], expected_source: str) -> int | None:
    """Return the first top-k rank from the expected source, if present."""
    return next((int(hit["rank"]) for hit in hits if hit["source"] == expected_source), None)


def hybrid_comparison() -> list[dict[str, Any]]:
    """Compare semantic, BM25, and RRF hybrid rankings on the same three queries."""
    rows: list[dict[str, Any]] = []
    for case in COMPARISON_CASES:
        modes = {mode: retrieve(case["query"], top_k=4, mode=mode) for mode in ("semantic", "bm25", "hybrid")}
        rows.append(
            {
                **case,
                "methods": {
                    mode: {
                        "expected_source_rank": expected_rank(hits, case["expected_source"]),
                        "top_k": [compact_hit(hit) for hit in hits],
                    }
                    for mode, hits in modes.items()
                },
            }
        )
    return rows


def in_memory_semantic_hits(query: str, chunks: list[dict[str, Any]], top_k: int = 4) -> list[dict[str, Any]]:
    """Benchmark chunk configurations locally without changing the persisted baseline index."""
    model = get_embedding_model()
    embeddings = model.encode([str(chunk["text"]) for chunk in chunks], show_progress_bar=False, convert_to_numpy=True)
    query_embedding = model.encode([query], show_progress_bar=False, convert_to_numpy=True)[0]
    normalized_documents = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    normalized_query = query_embedding / np.linalg.norm(query_embedding)
    distances = 1 - normalized_documents @ normalized_query
    ranked_indices = np.argsort(distances)[:top_k]
    return [
        {
            **chunk,
            "rank": rank,
            "distance": float(distances[index]),
            "bm25_score": None,
            "rrf_score": None,
        }
        for rank, index in enumerate(ranked_indices, start=1)
        for chunk in [chunks[int(index)]]
    ]


def chunking_comparison() -> dict[str, Any]:
    """Compare baseline 800/150 chunks with a 400/75 in-memory benchmark."""
    strategies = {
        "paragraph_800_overlap_150": load_chunks(target_size=800, overlap=150),
        "paragraph_400_overlap_75": load_chunks(target_size=400, overlap=75),
    }
    for chunks in strategies.values():
        validate_chunks(chunks)

    results: dict[str, Any] = {}
    for name, chunks in strategies.items():
        rows = []
        for case in COMPARISON_CASES:
            hits = in_memory_semantic_hits(case["query"], chunks)
            rows.append(
                {
                    **case,
                    "expected_source_rank": expected_rank(hits, case["expected_source"]),
                    "top_k": [compact_hit(hit, include_preview=True) for hit in hits],
                }
            )
        results[name] = {"chunk_count": len(chunks), "queries": rows}
    return results


def metadata_filter_demo() -> dict[str, Any]:
    """Show existing Chroma metadata filters changing results for real query constraints."""
    thermo_query = COMPARISON_CASES[0]["query"]
    heat_query = COMPARISON_CASES[2]["query"]
    return {
        "thermodynamics_topic_filter": {
            "metadata": {"topic": "thermodynamics"},
            "query": thermo_query,
            "unfiltered": [compact_hit(hit) for hit in retrieve(thermo_query, top_k=4, mode="semantic")],
            "filtered": [
                compact_hit(hit)
                for hit in retrieve(thermo_query, top_k=4, mode="semantic", filters={"topic": "thermodynamics"})
            ],
        },
        "heat_source_filter": {
            "metadata": {"source": "heat_transfer.txt"},
            "query": heat_query,
            "unfiltered": [compact_hit(hit) for hit in retrieve(heat_query, top_k=4, mode="semantic")],
            "filtered": [
                compact_hit(hit)
                for hit in retrieve(heat_query, top_k=4, mode="semantic", filters={"source": "heat_transfer.txt"})
            ],
        },
    }


def memory_demo() -> list[list[dict[str, Any]]]:
    """Run live multi-turn examples; history resolves references but is never model evidence."""
    transcripts: list[list[dict[str, Any]]] = []
    for questions in MEMORY_DEMOS:
        history: list[dict[str, Any]] = []
        transcript: list[dict[str, Any]] = []
        for question in questions:
            try:
                result = ask(question, top_k=4, history=history)
            except RuntimeError as exc:
                transcript.append({"question": question, "runtime_error": str(exc)})
                break
            transcript.append(
                {
                    "question": question,
                    "retrieval_query": result["retrieval_query"],
                    "answer": result["answer"],
                    "sources": result["sources"],
                    "top_k": [compact_hit(hit) for hit in result["retrieved_chunks"]],
                }
            )
            history.append({"question": question, "retrieval_query": result["retrieval_query"]})
        transcripts.append(transcript)
    return transcripts


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local, reproducible Project 1 stretch retrieval benchmarks.")
    parser.add_argument("--output", default="stretch_results.json", help="JSON evidence output path.")
    parser.add_argument("--include-memory", action="store_true", help="Also run live Groq multi-turn memory demonstrations.")
    args = parser.parse_args()

    results = {
        "hybrid_comparison": hybrid_comparison(),
        "chunking_comparison": chunking_comparison(),
        "metadata_filter_demo": metadata_filter_demo(),
    }
    if args.include_memory:
        results["memory_demo"] = memory_demo()
    output_path = Path(args.output)
    output_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))
    print(f"\nSaved stretch benchmark results to {output_path}.")


if __name__ == "__main__":
    main()
