from __future__ import annotations

import argparse
import os
from collections import OrderedDict

from dotenv import load_dotenv
from groq import Groq

from vector_store import retrieve

load_dotenv()

DEFAULT_TOP_K = 4
SYSTEM_INSTRUCTION = (
    "You are answering questions using only the provided retrieved documents. Do not use outside knowledge. "
    "If the provided context does not contain enough information to answer the question, say that you do not have enough information. "
    "Do not invent facts. Cite the relevant source filenames in your response."
)


def build_prompt(question: str, retrieval_results: list[dict]) -> list[dict]:
    if not retrieval_results:
        return [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": f"Question: {question}\n\nNo retrieved documents were found, so I must respond that there is not enough information."},
        ]

    context_blocks = []
    for index, result in enumerate(retrieval_results, start=1):
        context_blocks.append(
            f"[Document {index}] Source: {result['source']} | Chunk: {result['chunk_index']} | Distance: {result['distance']:.4f}\n{result['text']}"
        )

    context_text = "\n\n".join(context_blocks)
    user_message = (
        f"Question: {question}\n\nUse only the following retrieved documents to answer. "
        f"If they do not contain enough information, say that you do not have enough information.\n\n{context_text}"
    )
    return [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "user", "content": user_message},
    ]


def answer_question(question: str, top_k: int = DEFAULT_TOP_K) -> dict:
    retrieval_results = retrieve(question, top_k=top_k)
    sources = []
    seen = set()
    for result in retrieval_results:
        if result["source"] not in seen:
            sources.append(result["source"])
            seen.add(result["source"])

    if not retrieval_results:
        return {
            "answer": "I don't have enough information in the provided documents to answer that question.",
            "sources": [],
            "retrieved_chunks": [],
        }

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_key_here":
        raise ValueError("GROQ_API_KEY is missing or still set to the placeholder value. Add it to a local .env file and restart the app.")

    client = Groq(api_key=api_key)
    prompt = build_prompt(question, retrieval_results)
    completion = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=prompt,
        temperature=0.1,
        max_tokens=500,
    )
    answer = completion.choices[0].message.content.strip()

    return {
        "answer": answer,
        "sources": sources,
        "retrieved_chunks": retrieval_results,
    }


def print_result(question: str, result: dict) -> None:
    print("QUESTION")
    print(question)
    print("\nRETRIEVED CHUNKS")
    for index, chunk in enumerate(result["retrieved_chunks"], start=1):
        print(f"{index}. source={chunk['source']} | chunk_index={chunk['chunk_index']} | distance={chunk['distance']:.4f}")
        print(chunk["text"])
        print("-" * 60)

    print("\nANSWER")
    print(result["answer"])
    print("\nSOURCES")
    for source in result["sources"]:
        print(f"- {source}")


def print_retrieval_results(question: str, retrieval_results: list[dict]) -> None:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask a question against the Howard Mechanical Engineering corpus.")
    parser.add_argument("question", nargs="?", help="Question to ask the ChromaDB retrieval pipeline.")
    parser.add_argument("--retrieve-only", action="store_true", help="Only retrieve the top chunks and do not call Groq.")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="How many chunks to retrieve.")
    args = parser.parse_args()

    if not args.question:
        parser.error("A question is required unless using --retrieve-only with a query string.")

    retrieval_results = retrieve(args.question, top_k=args.top_k)
    if args.retrieve_only:
        print_retrieval_results(args.question, retrieval_results)
        return

    try:
        response = answer_question(args.question, top_k=args.top_k)
        print_result(args.question, response)
    except ValueError as exc:
        print(f"Runtime configuration error: {exc}")
        print("\nRetrieved chunks for debugging:")
        for idx, chunk in enumerate(retrieval_results, start=1):
            print(f"{idx}. {chunk['source']} | chunk_index={chunk['chunk_index']} | distance={chunk['distance']:.4f}")


if __name__ == "__main__":
    main()
