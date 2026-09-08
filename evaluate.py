from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from query import INSUFFICIENT_INFORMATION_RESPONSE, answer_question


EVALUATION_CASES = [
    {
        "question": "What topics are listed for MEEG-304 Thermodynamics in the guide?",
        "expected_answer": "The laws of thermodynamics, properties of pure substances, entropy, and availability.",
    },
    {
        "question": "Which course in the document collection focuses on instruments, sensors, experimental error, and uncertainty analysis?",
        "expected_answer": "MEEG-316 Instrumentation and Experimentation, including instruments or sensors, experimental error, and uncertainty analysis.",
    },
    {
        "question": "What three major modes of heat transfer should a student expect to study in Heat Transfer?",
        "expected_answer": "Conduction, convection, and radiation.",
    },
    {
        "question": "How is Howard Mechanical Engineering Senior Project structured across the senior year?",
        "expected_answer": "MEEG-441 Senior Project I and MEEG-442 Senior Project II are a two-course sequence; Project II continues the team design study begun in Project I.",
    },
    {
        "question": "According to the guide, which course is mainly about designing aircraft wings?",
        "expected_answer": "The exact insufficient-information refusal, because the provided documents do not answer this question.",
    },
]


def normalized(text: str) -> str:
    """Normalize text for concept-level, rather than exact-wording, evaluation."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def concept_count(answer: str, concept_groups: list[tuple[str, ...]]) -> int:
    """Count expected concept groups represented in a generated answer."""
    text = normalized(answer)
    return sum(any(normalized(option) in text for option in group) for group in concept_groups)


def judge_answer(case_index: int, answer: str) -> str:
    """Apply the planning document's required concepts to an actual response."""
    if case_index == 5:
        return "Accurate" if answer == INSUFFICIENT_INFORMATION_RESPONSE else "Inaccurate"

    expected_concepts = {
        1: [("laws of thermodynamics",), ("pure substances",), ("entropy",), ("availability",)],
        2: [("meeg 316", "instrumentation and experimentation"), ("instruments", "sensors"), ("experimental error", "uncertainty")],
        3: [("conduction",), ("convection",), ("radiation",)],
        4: [("meeg 441", "senior project i"), ("meeg 442", "senior project ii"), ("two course", "two semester", "continues")],
    }[case_index]
    matched = concept_count(answer, expected_concepts)
    if matched == len(expected_concepts):
        return "Accurate"
    if matched:
        return "Partially Accurate"
    return "Inaccurate"


def compact_retrieval(chunk: dict[str, Any]) -> dict[str, Any]:
    """Keep the source, position, and score needed to reproduce evaluation evidence."""
    return {
        "source": chunk["source"],
        "chunk_index": int(chunk["chunk_index"]),
        "distance": round(float(chunk["distance"]), 4),
    }


def run_evaluation(mode: str = "semantic") -> list[dict[str, Any]]:
    """Run every planned question through retrieval, grounded generation, and judgment."""
    results: list[dict[str, Any]] = []
    for index, case in enumerate(EVALUATION_CASES, start=1):
        try:
            response = answer_question(case["question"], top_k=4, mode=mode)
            retrieved = [compact_retrieval(chunk) for chunk in response["retrieved_chunks"]]
            answer = str(response["answer"])
            result: dict[str, Any] = {
                "number": index,
                "question": case["question"],
                "expected_answer": case["expected_answer"],
                "actual_response": answer,
                "sources": list(response["sources"]),
                "top_retrieval_result": retrieved[0] if retrieved else None,
                "top_retrieval_distance": retrieved[0]["distance"] if retrieved else None,
                "retrieval_top_k": retrieved,
                "judgment": judge_answer(index, answer),
            }
        except (ValueError, RuntimeError) as exc:
            result = {
                "number": index,
                "question": case["question"],
                "expected_answer": case["expected_answer"],
                "actual_response": f"REQUEST FAILED: {exc}",
                "sources": [],
                "top_retrieval_result": None,
                "top_retrieval_distance": None,
                "retrieval_top_k": [],
                "judgment": "Inaccurate",
            }
        results.append(result)
    return results


def print_results(results: list[dict[str, Any]]) -> None:
    """Print a readable report while preserving the same data in JSON."""
    for result in results:
        print(f"\nQUESTION {result['number']}")
        print(f"Question: {result['question']}")
        print(f"Expected: {result['expected_answer']}")
        print(f"Actual: {result['actual_response']}")
        print(f"Sources: {', '.join(result['sources']) or '(none)'}")
        print(f"Top retrieval result: {result['top_retrieval_result']}")
        print(f"Top distance: {result['top_retrieval_distance']}")
        print("Top-k retrieval:")
        for chunk in result["retrieval_top_k"]:
            print(f"- {chunk['source']} | chunk {chunk['chunk_index']} | distance {chunk['distance']:.4f}")
        print(f"Judgment: {result['judgment']}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Evaluate the five questions defined in planning.md.")
    parser.add_argument(
        "--output",
        default="evaluation_results.json",
        help="Path for the JSON report generated from this runtime evaluation.",
    )
    parser.add_argument(
        "--mode",
        choices=["semantic", "bm25", "hybrid"],
        default="semantic",
        help="Retrieval mode; semantic preserves the Milestone 6 baseline.",
    )
    args = parser.parse_args()

    results = run_evaluation(mode=args.mode)
    print_results(results)
    output_path = Path(args.output)
    output_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"\nSaved runtime evaluation results to {output_path}.")


if __name__ == "__main__":
    main()
