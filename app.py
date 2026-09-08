from __future__ import annotations

import gradio as gr

from query import ask


def ask_question(question: str, history: list[dict] | None):
    """Answer one turn while retaining only prior user turns for follow-up resolution."""
    if not question or not question.strip():
        return "Please enter a question first.", "", [], history or []

    try:
        result = ask(question, top_k=4, history=history or [])
    except ValueError as exc:
        return str(exc), "", [], history or []
    except RuntimeError as exc:
        return str(exc), "", [], history or []
    except Exception:
        return "Something unexpected went wrong while answering that question. Please try again.", "", [], history or []

    sources = "\n".join(f"- {source}" for source in result["sources"])
    context = [
        {
            "source": chunk["source"],
            "chunk_index": chunk["chunk_index"],
            "file_type": chunk["file_type"],
            "topic": chunk["topic"],
            "distance": round(float(chunk["distance"]), 4) if chunk["distance"] is not None else None,
            "bm25_score": round(float(chunk["bm25_score"]), 4) if chunk["bm25_score"] is not None else None,
            "rrf_score": round(float(chunk["rrf_score"]), 6) if chunk["rrf_score"] is not None else None,
            "text": chunk["text"],
        }
        for chunk in result["retrieved_chunks"]
    ]
    updated_history = [
        *(history or []),
        {"question": question.strip(), "retrieval_query": result["retrieval_query"]},
    ]
    return result["answer"], sources, context, updated_history


with gr.Blocks(title="Unofficial Howard Mechanical Engineering Guide") as demo:
    gr.Markdown(
        "# Unofficial Howard Mechanical Engineering Guide\n"
        "Ask questions about Howard Mechanical Engineering courses and program information using the project's document collection."
    )

    question_box = gr.Textbox(
        label="Question",
        placeholder="What three modes of heat transfer are covered in MEEG-403 Heat Transfer?",
        lines=3,
    )
    submit_btn = gr.Button("Ask", variant="primary")
    history_state = gr.State([])

    answer_box = gr.Textbox(label="Answer", lines=8)
    source_box = gr.Textbox(label="Sources", lines=4)
    context_box = gr.JSON(label="Retrieved context")

    outputs = [answer_box, source_box, context_box, history_state]
    submit_btn.click(fn=ask_question, inputs=[question_box, history_state], outputs=outputs)
    question_box.submit(fn=ask_question, inputs=[question_box, history_state], outputs=outputs)


if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", share=False, show_error=False)
