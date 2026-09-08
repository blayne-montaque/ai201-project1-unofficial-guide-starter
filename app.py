from __future__ import annotations

from typing import Any

import gradio as gr

from ingest import load_chunks
from query import DEFAULT_RETRIEVAL_MODE, ask


MODE_CHOICES = [
    ("Hybrid (Recommended)", "hybrid"),
    ("Semantic", "semantic"),
    ("BM25", "bm25"),
]
EXAMPLE_QUESTIONS = [
    "What topics are covered in MEEG-304 Thermodynamics?",
    "Which course teaches MATLAB?",
    "What are the three modes of heat transfer?",
    "How is Senior Project structured?",
]


def _metadata_choices() -> tuple[list[str], list[str]]:
    """Build filter choices from the same validated chunks used by retrieval."""
    chunks = load_chunks()
    topics = sorted({str(chunk["topic"]) for chunk in chunks})
    sources = sorted({str(chunk["source"]) for chunk in chunks})
    return topics, sources


TOPIC_CHOICES, SOURCE_CHOICES = _metadata_choices()


def _filters_from_controls(topic: str, source: str) -> dict[str, str] | None:
    filters = {
        key: value
        for key, value in {"topic": topic, "source": source}.items()
        if value and value != "All"
    }
    return filters or None


def _source_markup(sources: list[str]) -> str:
    """Keep programmatic sources compact in the visible conversation."""
    if not sources:
        return ""
    labels = " &nbsp;•&nbsp; ".join(f"`{source}`" for source in sources)
    return f"\n\n---\n**Sources**  {labels}"


def _retrieval_details(result: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    """Return compact, inspectable evidence without exposing it in the main chat."""
    return [
        {
            "rank": chunk["rank"],
            "source": chunk["source"],
            "chunk_index": chunk["chunk_index"],
            "topic": chunk["topic"],
            "distance": round(float(chunk["distance"]), 4) if chunk["distance"] is not None else None,
            "bm25_score": round(float(chunk["bm25_score"]), 4) if chunk["bm25_score"] is not None else None,
            "rrf_score": round(float(chunk["rrf_score"]), 6) if chunk["rrf_score"] is not None else None,
            "retrieval_mode": mode,
        }
        for chunk in result["retrieved_chunks"]
    ]


def ask_question(
    question: str,
    chat_history: list[dict[str, str]] | None,
    memory_history: list[dict[str, str]] | None,
    mode: str,
    topic: str,
    source: str,
):
    """Add a grounded response to the chat while preserving user-turn memory."""
    cleaned_question = (question or "").strip()
    messages = list(chat_history or [])
    memory = list(memory_history or [])
    if not cleaned_question:
        return messages, "", memory, []

    messages.append({"role": "user", "content": cleaned_question})
    try:
        result = ask(
            cleaned_question,
            top_k=4,
            mode=mode,
            filters=_filters_from_controls(topic, source),
            history=memory,
        )
        assistant_message = result["answer"] + _source_markup(result["sources"])
        details = _retrieval_details(result, mode)
        memory.append(
            {"question": cleaned_question, "retrieval_query": result["retrieval_query"]}
        )
    except ValueError as exc:
        assistant_message = str(exc)
        details = []
    except RuntimeError:
        assistant_message = "I couldn’t reach the answer service just now. Please try again."
        details = []
    except Exception:
        assistant_message = "Something unexpected went wrong. Please try again."
        details = []

    messages.append({"role": "assistant", "content": assistant_message})
    return messages, "", memory, details


def clear_conversation():
    """Clear both rendered messages and the history used for follow-up resolution."""
    return [], "", [], []


CSS = """
:root {
  --howard-blue: #12355b;
  --howard-blue-soft: #eaf1f8;
  --howard-red: #bf2539;
  --ink: #162333;
  --muted: #657386;
  --line: #dce4ed;
  --card: rgba(255, 255, 255, 0.94);
}

body, .gradio-container {
  background: #f5f7fa !important;
  color: var(--ink);
}

.gradio-container {
  max-width: none !important;
  padding: 0 1.25rem 2.5rem !important;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}

#app-shell { max-width: 1040px; margin: 0 auto; }
#hero {
  margin: 1.25rem 0 1.4rem;
  padding: 1.65rem 1.8rem;
  background: var(--howard-blue);
  color: white;
  border-radius: 18px;
  box-shadow: 0 12px 30px rgba(18, 53, 91, 0.16);
}
#hero h1 { margin: 0; font-size: clamp(1.8rem, 4vw, 2.55rem); letter-spacing: -0.04em; }
#hero p { max-width: 700px; margin: 0.45rem 0 0; color: #e4edf7; font-size: 1.03rem; }
#hero .eyebrow { color: #f4bec6; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.085em; text-transform: uppercase; }
#hero .disclaimer { margin-top: 0.9rem; color: #c9d9e8; font-size: 0.8rem; }

.surface, #chat-card, #about-card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 16px;
  box-shadow: 0 4px 16px rgba(25, 45, 69, 0.05);
}
#chat-card { padding: 0.8rem; }
#chatbot { border: 0 !important; background: transparent !important; }
#chatbot .message { border-radius: 14px !important; }
#chatbot .message.user { background: var(--howard-blue) !important; }
#chatbot .message.bot { border: 1px solid var(--line) !important; }

#composer { margin-top: 0.85rem; }
#question-input textarea { min-height: 54px !important; }
#send-button { min-width: 90px; background: var(--howard-red) !important; border-color: var(--howard-red) !important; }
#clear-button { border-color: #bcc9d6 !important; color: #455569 !important; }

.section-label { margin: 1.15rem 0 0.45rem; color: var(--muted); font-size: 0.8rem; font-weight: 700; letter-spacing: 0.055em; text-transform: uppercase; }
.example-button { border-radius: 999px !important; border-color: #cbd7e4 !important; color: var(--howard-blue) !important; background: white !important; font-size: 0.82rem !important; }
.example-button:hover { border-color: var(--howard-blue) !important; background: var(--howard-blue-soft) !important; }

#controls, #about-card { padding: 0.85rem 1rem; }
#controls { margin-top: 1rem; }
#controls .wrap { gap: 0.8rem !important; }
#about-card { margin-top: 1rem; color: var(--muted); font-size: 0.87rem; }
#about-card strong { color: var(--ink); }
#about-card p { margin: 0.35rem 0; }
.gradio-container .accordion { border: 1px solid var(--line) !important; border-radius: 12px !important; background: var(--card) !important; }

@media (max-width: 700px) {
  .gradio-container { padding: 0 0.7rem 1.5rem !important; }
  #hero { margin-top: 0.7rem; padding: 1.3rem 1.15rem; }
  #composer { gap: 0.5rem !important; }
  #send-button, #clear-button { min-width: 0; }
}

@media (prefers-color-scheme: dark) {
  body, .gradio-container { background: #101824 !important; }
  .surface, #chat-card, #about-card, .gradio-container .accordion { background: #172332 !important; border-color: #304154 !important; }
  #about-card, .section-label { color: #b4c0ce; }
  #about-card strong { color: #eef4fb; }
  .example-button { background: #172332 !important; color: #d5e5f5 !important; border-color: #43576c !important; }
}
"""


with gr.Blocks(title="Howard ME Guide") as demo:
    with gr.Column(elem_id="app-shell"):
        gr.HTML(
            """
            <section id="hero">
              <div class="eyebrow">AI201 Project 1 · The Unofficial Guide</div>
              <h1>Howard ME Guide</h1>
              <p>Ask questions about Howard Mechanical Engineering courses, curriculum, and student guidance.</p>
              <div class="disclaimer">Unofficial student project. Answers are grounded in the included document collection.</div>
            </section>
            """
        )

        chat_history_state = gr.State([])
        memory_state = gr.State([])
        with gr.Group(elem_id="chat-card"):
            chatbot = gr.Chatbot(
                value=[],
                layout="bubble",
                height=440,
                placeholder="Start with a course, curriculum, or study-guidance question.",
                elem_id="chatbot",
                show_label=False,
            )
            with gr.Row(elem_id="composer"):
                question_box = gr.Textbox(
                    placeholder="Ask about a course, requirement, or topic…",
                    lines=1,
                    max_lines=4,
                    show_label=False,
                    elem_id="question-input",
                    scale=8,
                )
                send_button = gr.Button("Send", variant="primary", elem_id="send-button", scale=1)
                clear_button = gr.Button("Clear", elem_id="clear-button", scale=1)

        gr.HTML('<div class="section-label">Try an example</div>')
        with gr.Row():
            example_buttons = [
                gr.Button(question, elem_classes="example-button") for question in EXAMPLE_QUESTIONS
            ]

        with gr.Group(elem_id="controls"):
            with gr.Row():
                mode_box = gr.Dropdown(
                    choices=MODE_CHOICES,
                    value=DEFAULT_RETRIEVAL_MODE,
                    label="Retrieval mode",
                    info="Hybrid combines semantic similarity and BM25 using Reciprocal Rank Fusion.",
                    scale=1,
                )
                with gr.Accordion("Advanced filters", open=False):
                    topic_box = gr.Dropdown(
                        choices=["All", *TOPIC_CHOICES], value="All", label="Topic filter"
                    )
                    source_box = gr.Dropdown(
                        choices=["All", *SOURCE_CHOICES], value="All", label="Source filter"
                    )

        with gr.Accordion("Sources & retrieval details", open=False):
            gr.Markdown("The latest turn’s retrieved chunks. Supporting sources also appear directly below each answer.")
            retrieval_details = gr.JSON(label="Latest retrieval details", value=[])

        with gr.Accordion("About this system", open=False):
            gr.HTML(
                """
                <div id="about-card">
                  <p><strong>Retrieval:</strong> Hybrid by default, with semantic and BM25 comparison modes.</p>
                  <p><strong>Embedding model:</strong> all-MiniLM-L6-v2 &nbsp; · &nbsp; <strong>Corpus:</strong> 16 documents, 127 chunks</p>
                  <p>Conversation memory resolves follow-up course references; retrieved documents remain the only factual source.</p>
                </div>
                """
            )

        event_inputs = [question_box, chat_history_state, memory_state, mode_box, topic_box, source_box]
        event_outputs = [chatbot, question_box, memory_state, retrieval_details]
        send_button.click(fn=ask_question, inputs=event_inputs, outputs=event_outputs).then(
            fn=lambda messages: messages, inputs=chatbot, outputs=chat_history_state
        )
        question_box.submit(fn=ask_question, inputs=event_inputs, outputs=event_outputs).then(
            fn=lambda messages: messages, inputs=chatbot, outputs=chat_history_state
        )
        clear_button.click(
            fn=clear_conversation,
            outputs=[chatbot, question_box, memory_state, retrieval_details],
        ).then(fn=lambda messages: messages, inputs=chatbot, outputs=chat_history_state)

        for prompt, button in zip(EXAMPLE_QUESTIONS, example_buttons, strict=True):
            button.click(fn=lambda value=prompt: value, outputs=question_box)


if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", share=False, show_error=False, css=CSS)
