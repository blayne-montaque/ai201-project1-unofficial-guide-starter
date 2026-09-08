from __future__ import annotations

import gradio as gr

from query import ask


def ask_question(question: str):
    """Return user-friendly Gradio outputs without exposing implementation tracebacks."""
    if not question or not question.strip():
        return "Please enter a question first.", "", []

    try:
        result = ask(question, top_k=4)
    except ValueError as exc:
        return str(exc), "", []
    except RuntimeError as exc:
        return str(exc), "", []
    except Exception:
        return "Something unexpected went wrong while answering that question. Please try again.", "", []

    sources = "\n".join(f"- {source}" for source in result["sources"])
    context = [
        {
            "source": chunk["source"],
            "chunk_index": chunk["chunk_index"],
            "file_type": chunk["file_type"],
            "topic": chunk["topic"],
            "distance": round(float(chunk["distance"]), 4),
            "text": chunk["text"],
        }
        for chunk in result["retrieved_chunks"]
    ]
    return result["answer"], sources, context


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

    answer_box = gr.Textbox(label="Answer", lines=8)
    source_box = gr.Textbox(label="Sources", lines=4)
    context_box = gr.JSON(label="Retrieved context")

    submit_btn.click(fn=ask_question, inputs=question_box, outputs=[answer_box, source_box, context_box])
    question_box.submit(fn=ask_question, inputs=question_box, outputs=[answer_box, source_box, context_box])


if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", share=False, show_error=False)
