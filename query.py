from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from vector_store import retrieve

load_dotenv()

DEFAULT_TOP_K = 4
# The originally planned Llama model returned HTTP 404 for this Groq account;
# this available instruction model is used for the validated runtime path.
GROQ_MODEL = "openai/gpt-oss-20b"
INSUFFICIENT_INFORMATION_RESPONSE = "I don't have enough information in the provided documents to answer that."
SYSTEM_INSTRUCTION = f"""You are answering a question using only the retrieved document context provided below.

Rules:
1. Use only information explicitly supported by the provided context.
2. Do not use outside knowledge, assumptions, or general background knowledge.
3. If the context does not contain enough information to answer, respond with exactly:
{INSUFFICIENT_INFORMATION_RESPONSE}
4. Do not invent facts.
5. Do not infer course requirements, professor behavior, dates, prerequisites, opinions, or policies unless they are supported by the provided context.
6. Keep the answer concise and directly tied to the question.
7. Do not add a source list to the answer; the application provides sources separately from retrieval metadata."""


def get_api_key() -> str:
    """Return the configured Groq key without exposing it in errors or output."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_key_here":
        raise ValueError("GROQ_API_KEY is not configured. Add it to your .env file before running generation.")
    return api_key


def unique_sources(retrieval_results: list[dict[str, Any]]) -> list[str]:
    """Derive a stable, deduplicated source list from retrieval metadata."""
    return list(dict.fromkeys(str(result["source"]) for result in retrieval_results))


def build_prompt(question: str, retrieval_results: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Build a strict grounding prompt that includes source identifiers for each chunk."""
    context_blocks = []
    for result in retrieval_results:
        context_blocks.append(
            "\n".join(
                [
                    f"SOURCE: {result['source']}",
                    f"CHUNK INDEX: {result['chunk_index']}",
                    f"FILE TYPE: {result['file_type']}",
                    f"TOPIC: {result['topic']}",
                    "CONTENT:",
                    result["text"],
                ]
            )
        )

    context = "\n\n---\n\n".join(context_blocks) or "No retrieved document context is available."
    return [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {
            "role": "user",
            "content": f"Question: {question}\n\nRetrieved document context:\n{context}",
        },
    ]


def ask(question: str, top_k: int = DEFAULT_TOP_K) -> dict[str, Any]:
    """Retrieve evidence, call Groq, and return a grounded answer with code-derived sources."""
    if not question or not question.strip():
        raise ValueError("Please enter a question first.")

    retrieval_results = retrieve(question.strip(), top_k=top_k)
    sources = unique_sources(retrieval_results)
    if not retrieval_results:
        return {
            "answer": INSUFFICIENT_INFORMATION_RESPONSE,
            "sources": [],
            "retrieved_chunks": [],
        }

    client = Groq(api_key=get_api_key())
    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=build_prompt(question.strip(), retrieval_results),
            temperature=0.0,
            max_tokens=300,
        )
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        error_label = exc.__class__.__name__
        status_detail = f" (status {status_code})" if status_code else ""
        raise RuntimeError(
            f"The generation request failed ({error_label}{status_detail}). Please try again."
        ) from exc

    answer = (completion.choices[0].message.content or "").strip()
    if not answer:
        raise RuntimeError("The generation service returned an empty response. Please try again.")

    return {
        "answer": answer,
        "sources": sources,
        "retrieved_chunks": retrieval_results,
    }


def answer_question(question: str, top_k: int = DEFAULT_TOP_K) -> dict[str, Any]:
    """Backward-compatible name used by the Gradio interface."""
    return ask(question, top_k=top_k)


def print_retrieval_results(question: str, retrieval_results: list[dict[str, Any]]) -> None:
    """Print full retrieval-only results in a README-friendly format."""
    print("QUESTION")
    print(question)
    print("\nRETRIEVED CHUNKS")
    for rank, chunk in enumerate(retrieval_results, start=1):
        print(f"\nRank: {rank}")
        print(f"Source: {chunk['source']}")
        print(f"Chunk Index: {chunk['chunk_index']}")
        print(f"File Type: {chunk['file_type']}")
        print(f"Topic: {chunk['topic']}")
        print(f"Distance: {chunk['distance']:.4f}\n")
        print(chunk["text"])
        print("-" * 50)


def print_answer_result(question: str, result: dict[str, Any]) -> None:
    """Print normal generation-mode output without relying on model-provided citations."""
    print("QUESTION")
    print(question)
    print("\nANSWER")
    print(result["answer"])
    print("\nSOURCES")
    for source in result["sources"]:
        print(f"- {source}")
    print("\nRETRIEVED CONTEXT")
    for rank, chunk in enumerate(result["retrieved_chunks"], start=1):
        print(
            f"{rank}. source={chunk['source']} | chunk_index={chunk['chunk_index']} | "
            f"distance={chunk['distance']:.4f}"
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Ask a grounded question against the Howard Mechanical Engineering corpus.")
    parser.add_argument("question", nargs="?", help="Question to ask the ChromaDB retrieval pipeline.")
    parser.add_argument("--retrieve-only", action="store_true", help="Only retrieve the top chunks and do not call Groq.")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="How many chunks to retrieve.")
    args = parser.parse_args()

    if not args.question:
        parser.error("A question is required.")

    try:
        if args.retrieve_only:
            print_retrieval_results(args.question, retrieve(args.question, top_k=args.top_k))
            return
        print_answer_result(args.question, ask(args.question, top_k=args.top_k))
    except (ValueError, RuntimeError) as exc:
        print(f"REQUEST FAILED: {exc}")


if __name__ == "__main__":
    main()
