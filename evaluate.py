from __future__ import annotations

from query import answer_question


EVALUATION_CASES = [
    {
        "question": "What do students say about Thermodynamics?",
        "expected_answer": "TBD — fill in after the final corpus is selected and reviewed.",
    },
    {
        "question": "What should I expect from Fluid Mechanics?",
        "expected_answer": "TBD — fill in after the final corpus is selected and reviewed.",
    },
    {
        "question": "Which classes involve MATLAB?",
        "expected_answer": "TBD — fill in after the final corpus is selected and reviewed.",
    },
    {
        "question": "What is Senior Design like?",
        "expected_answer": "TBD — fill in after the final corpus is selected and reviewed.",
    },
    {
        "question": "Which courses are especially math-heavy?",
        "expected_answer": "TBD — fill in after the final corpus is selected and reviewed.",
    },
]


def run_evaluation() -> None:
    for index, item in enumerate(EVALUATION_CASES, start=1):
        print(f"\n=== Evaluation {index} ===")
        print(f"Question: {item['question']}")
        print(f"Expected answer: {item['expected_answer']}")
        try:
            result = answer_question(item["question"], top_k=4)
            print("System response:")
            print(result["answer"])
            print("Sources:")
            for source in result["sources"]:
                print(f"- {source}")
            print("Retrieved chunks:")
            for chunk in result["retrieved_chunks"]:
                print(f"- source={chunk['source']} | chunk_index={chunk['chunk_index']} | distance={chunk['distance']:.4f}")
                print(chunk["text"])
                print("--")
        except ValueError as exc:
            print(f"Skipped because runtime configuration is incomplete: {exc}")


if __name__ == "__main__":
    run_evaluation()
