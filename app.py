from __future__ import annotations

import json

import gradio as gr

from query import answer_question


def ask_question(question: str):
    if not question or not question.strip():
        return "Please enter a question first.", "", []

    try:
        result = answer_question(question, top_k=4)
    except ValueError as exc:
        return str(exc), "", []

    sources = "\n".join(f"- {source}" for source in result["sources"])
    context = [
        {
            "source": chunk["source"],
            "chunk_index": chunk["chunk_index"],
            "distance": round(float(chunk["distance"]), 4),
            "text": chunk["text"],
        }
        for chunk in result["retrieved_chunks"]
    ]
    return result["answer"], sources, json.dumps(context, indent=2)


with gr.Blocks(title="Unofficial Howard Mechanical Engineering Guide") as demo:
    gr.Markdown(
        "# Unofficial Howard Mechanical Engineering Guide\n"
        "Answers are generated from the student-source documents in this project and include source attribution."
    )

    with gr.Row():
        question_box = gr.Textbox(
            label="Question",
            placeholder="What do students say about Thermodynamics?",
            lines=3,
            scale=4,
        )
        submit_btn = gr.Button("Ask", variant="primary", scale=1)

    answer_box = gr.Textbox(label="Answer", lines=12)
    source_box = gr.Textbox(label="Sources", lines=4)
    context_box = gr.JSON(label="Retrieved context")

    submit_btn.click(fn=ask_question, inputs=[question_box], outputs=[answer_box, source_box, context_box])
    question_box.submit(fn=ask_question, inputs=[question_box], outputs=[answer_box, source_box, context_box])

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", share=False)
