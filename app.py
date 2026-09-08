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
    ("Thermodynamics", "What topics are covered in MEEG-304?"),
    ("MATLAB", "Which course teaches MATLAB?"),
    ("Heat Transfer", "What are the three modes of heat transfer?"),
    ("Senior Project", "How is Senior Project structured?"),
]


def _metadata_choices() -> tuple[list[str], list[str]]:
    """Build filter choices from the same validated chunks used by retrieval."""
    chunks = load_chunks()
    return (
        sorted({str(chunk["topic"]) for chunk in chunks}),
        sorted({str(chunk["source"]) for chunk in chunks}),
    )


TOPIC_CHOICES, SOURCE_CHOICES = _metadata_choices()


def _filters_from_controls(topic: str, source: str) -> dict[str, str] | None:
    filters = {
        key: value
        for key, value in {"topic": topic, "source": source}.items()
        if value and value != "All"
    }
    return filters or None


def _source_markup(sources: list[str]) -> str:
    """Attach the already-programmatic source list to its supporting answer."""
    if not sources:
        return ""
    labels = " &middot; ".join(f"`{source}`" for source in sources)
    return f"\n\n---\n<small><strong>Sources:</strong> {labels}</small>"


def _retrieval_details(result: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    """Expose concise latest-turn evidence only in the collapsed details panel."""
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
    """Add one grounded response without changing the underlying RAG flow."""
    cleaned_question = (question or "").strip()
    messages = list(chat_history or [])
    memory = list(memory_history or [])
    if not cleaned_question:
        return gr.update(value=messages), "", memory, [], gr.update()

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
    return gr.update(value=messages, visible=True), "", memory, details, gr.update(visible=False)


def clear_conversation():
    """Clear rendered messages and the user-turn state used for follow-up resolution."""
    return gr.update(value=[], visible=False), "", [], [], gr.update(visible=True)


CSS = """
:root {
  --navy: #102f55;
  --navy-soft: #eaf1f8;
  --red: #b3374b;
  --ink: #182535;
  --muted: #657184;
  --line: #e2e7ee;
  --canvas: #f8f8f5;
  --surface: #ffffff;
}

html, body, .gradio-container {
  color-scheme: light !important;
  background: var(--canvas) !important;
  color: var(--ink) !important;
}

.gradio-container {
  --body-background-fill: var(--canvas) !important;
  --body-text-color: var(--ink) !important;
  --background-fill-primary: var(--surface) !important;
  --background-fill-secondary: #f4f6f8 !important;
  --block-background-fill: var(--surface) !important;
  --block-border-color: var(--line) !important;
  --input-background-fill: var(--surface) !important;
  --input-border-color: var(--line) !important;
  --input-border-color-focus: #8aa3c0 !important;
  --border-color-primary: var(--line) !important;
  --color-accent: var(--navy) !important;
  max-width: none !important;
  min-height: 100vh;
  padding: 0 1.25rem 2rem !important;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}

.gradio-container *, .gradio-container input, .gradio-container textarea {
  color: var(--ink);
}

#app-shell { max-width: 1000px; margin: 0 auto; }
footer { display: none !important; }

#app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.35rem 0 1.05rem;
}
.brand { display: flex; align-items: center; gap: 0.75rem; }
.brand-mark {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 1px solid #c8d6e6;
  border-radius: 10px;
  background: var(--navy-soft);
  color: var(--navy);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.03em;
}
.brand-title { margin: 0; color: var(--navy); font-size: 1.08rem; font-weight: 750; letter-spacing: -0.02em; }
.brand-subtitle { margin-top: 0.1rem; color: var(--muted); font-size: 0.8rem; }
.status-badge {
  flex: none;
  border: 1px solid #dce5ee;
  border-radius: 999px;
  background: #fff;
  color: #526276;
  font-size: 0.76rem;
  font-weight: 650;
  padding: 0.38rem 0.65rem;
}
.status-badge::before { color: var(--red); content: "●"; font-size: 0.62rem; margin-right: 0.36rem; vertical-align: 0.04rem; }

#top-actions {
  flex: 0 0 220px !important;
  min-width: 220px !important;
  align-items: center !important;
  justify-content: flex-end !important;
  gap: 0.55rem !important;
}
#top-actions > * { flex: 0 0 auto !important; min-width: auto !important; }
#clear-button {
  min-width: auto !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  color: #6a7787 !important;
  font-size: 0.78rem !important;
  padding: 0.35rem 0.5rem !important;
  white-space: nowrap !important;
}
#clear-button:hover { color: var(--navy) !important; background: #eef3f8 !important; }

#settings-panel, #source-panel, #about-panel {
  margin: 0 0 0.65rem !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
}
#settings-panel > button, #source-panel > button, #about-panel > button {
  min-height: 28px !important;
  border: 0 !important;
  background: transparent !important;
  color: #617084 !important;
  font-size: 0.78rem !important;
  font-weight: 650 !important;
  padding: 0.25rem 0 !important;
}
#settings-panel > button:hover, #source-panel > button:hover, #about-panel > button:hover { color: var(--navy) !important; }
#settings-panel .wrap, #source-panel .wrap, #about-panel .wrap {
  margin-top: 0.35rem;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #fff !important;
  box-shadow: 0 4px 16px rgba(16, 47, 85, 0.04);
}
#settings-panel .wrap { padding: 0.7rem 0.8rem; }
#settings-panel label { color: #657184 !important; font-size: 0.74rem !important; }

#conversation-shell {
  overflow: hidden;
  min-height: 520px;
  border: 1px solid var(--line) !important;
  border-radius: 18px !important;
  background: var(--surface) !important;
  box-shadow: 0 10px 30px rgba(18, 40, 67, 0.055);
}

#empty-state {
  display: flex;
  min-height: 450px;
  align-items: center;
  justify-content: center;
  padding: 2.2rem 1.7rem 1.5rem;
  background: var(--surface) !important;
}
.empty-copy { max-width: 700px; margin: 0 auto 1.6rem; text-align: center; }
.empty-copy h1 { margin: 0; color: var(--navy); font-size: clamp(1.85rem, 4vw, 2.6rem); letter-spacing: -0.045em; }
.empty-copy h2 { margin: 0.4rem 0 0; color: var(--ink); font-size: 1.12rem; font-weight: 600; letter-spacing: -0.015em; }
.empty-copy p { margin: 0.55rem 0 0; color: var(--muted); font-size: 0.92rem; }

#suggestion-grid { gap: 0.7rem !important; }
.suggestion-card {
  min-height: 94px !important;
  border: 1px solid #dde5ee !important;
  border-radius: 13px !important;
  background: #fff !important;
  box-shadow: none !important;
  color: var(--ink) !important;
  font-size: 0.84rem !important;
  line-height: 1.38 !important;
  padding: 0.8rem 0.9rem !important;
  text-align: left !important;
  white-space: pre-line !important;
  transition: border-color 140ms ease, box-shadow 140ms ease, transform 140ms ease !important;
}
.suggestion-card:hover {
  border-color: #9db2ca !important;
  background: #fbfdff !important;
  box-shadow: 0 8px 18px rgba(16, 47, 85, 0.08) !important;
  transform: translateY(-1px);
}

#chatbot, #chatbot .wrap, #chatbot .bubble-wrap, #chatbot .message-wrap {
  background: var(--surface) !important;
}
#chatbot { min-height: 465px !important; padding: 1.1rem 1.15rem 0.5rem !important; }
#chatbot .message { box-shadow: none !important; }
#chatbot .message.user, #chatbot [data-testid="user"] {
  border: 1px solid #d9e5f1 !important;
  background: var(--navy-soft) !important;
  color: var(--navy) !important;
}
#chatbot .message.bot, #chatbot [data-testid="bot"] {
  border: 0 !important;
  background: transparent !important;
  color: var(--ink) !important;
}
#chatbot .message p, #chatbot .message li, #chatbot .message strong { color: inherit !important; }
#chatbot .message code { border: 1px solid #e0e6ed; border-radius: 5px; background: #f4f6f8; color: #33465e; padding: 0.08rem 0.24rem; }

#composer {
  align-items: center !important;
  gap: 0.55rem !important;
  margin: 0.5rem 0.7rem 0.7rem !important;
  padding: 0.42rem !important;
  border: 1px solid #cad7e4 !important;
  border-radius: 14px !important;
  background: #fff !important;
  box-shadow: 0 4px 14px rgba(16, 47, 85, 0.04);
}
#composer .wrap, #composer .form { background: #fff !important; }
#question-input, #question-input .wrap, #question-input textarea { background: transparent !important; box-shadow: none !important; }
#question-input textarea { min-height: 28px !important; color: var(--ink) !important; font-size: 0.92rem !important; padding: 0.45rem 0.55rem !important; }
#question-input textarea::placeholder { color: #8a97a7 !important; }
#send-button {
  min-width: 78px !important;
  min-height: 38px !important;
  border: 1px solid var(--navy) !important;
  border-radius: 10px !important;
  background: var(--navy) !important;
  color: #fff !important;
  box-shadow: none !important;
  font-size: 0.84rem !important;
}
#send-button:hover { background: #17416f !important; }

#source-panel { margin-top: 0.2rem !important; }
#source-panel .wrap { padding: 0.45rem 0.7rem !important; }
#source-panel label { color: #657184 !important; font-size: 0.75rem !important; }
#source-panel textarea, #source-panel pre, #source-panel code { font-size: 0.75rem !important; }
#about-panel { margin-top: 0.6rem !important; }
#about-panel .wrap { padding: 0.7rem 0.9rem !important; color: var(--muted) !important; font-size: 0.8rem !important; }

@media (max-width: 700px) {
  .gradio-container { padding: 0 0.75rem 1rem !important; }
  #app-header { align-items: flex-start; }
  .status-badge { font-size: 0.7rem; }
  #conversation-shell { min-height: 500px; border-radius: 14px !important; }
  #empty-state { min-height: 430px; padding: 1.5rem 1rem 1rem; }
  #suggestion-grid { gap: 0.5rem !important; }
  .suggestion-card { min-height: 86px !important; font-size: 0.78rem !important; }
  #chatbot { min-height: 440px !important; padding: 0.85rem !important; }
  #composer { margin: 0.45rem !important; }
}
"""


with gr.Blocks(title="Howard ME Guide") as demo:
    with gr.Column(elem_id="app-shell"):
        with gr.Row(elem_id="app-header"):
            gr.HTML(
                """
                <div class="brand">
                  <div class="brand-mark">ME</div>
                  <div>
                    <div class="brand-title">Howard ME Guide</div>
                    <div class="brand-subtitle">Unofficial AI course &amp; curriculum assistant</div>
                  </div>
                </div>
                """
            )
            with gr.Row(elem_id="top-actions", scale=0):
                gr.HTML('<div class="status-badge">16 documents</div>')
                clear_button = gr.Button("Clear conversation", size="sm", elem_id="clear-button")

        with gr.Accordion("Retrieval settings", open=False, elem_id="settings-panel"):
            with gr.Row():
                mode_box = gr.Dropdown(
                    choices=MODE_CHOICES,
                    value=DEFAULT_RETRIEVAL_MODE,
                    label="Retrieval mode",
                    info="Hybrid combines semantic similarity and BM25.",
                )
                topic_box = gr.Dropdown(choices=["All", *TOPIC_CHOICES], value="All", label="Topic")
                source_box = gr.Dropdown(choices=["All", *SOURCE_CHOICES], value="All", label="Source")

        chat_history_state = gr.State([])
        memory_state = gr.State([])
        with gr.Group(elem_id="conversation-shell"):
            with gr.Column(elem_id="empty-state", visible=True) as empty_state:
                gr.HTML(
                    """
                    <div class="empty-copy">
                      <h1>Howard ME Guide</h1>
                      <h2>What can I help you find?</h2>
                      <p>Ask about courses, prerequisites, curriculum, professors, or student guidance.</p>
                    </div>
                    """
                )
                suggestion_buttons = []
                for first, second in ((0, 1), (2, 3)):
                    with gr.Row(elem_id="suggestion-grid"):
                        for position in (first, second):
                            title, question = EXAMPLE_QUESTIONS[position]
                            suggestion_buttons.append(
                                gr.Button(f"{title}\n{question}", elem_classes="suggestion-card")
                            )

            chatbot = gr.Chatbot(
                value=[],
                layout="bubble",
                height=465,
                visible=False,
                elem_id="chatbot",
                show_label=False,
            )
            with gr.Row(elem_id="composer"):
                question_box = gr.Textbox(
                    placeholder="Ask about a course, prerequisite, or topic…",
                    lines=1,
                    max_lines=4,
                    show_label=False,
                    elem_id="question-input",
                    scale=8,
                )
                send_button = gr.Button("Send", variant="primary", elem_id="send-button", scale=1)

        with gr.Accordion("Latest sources & retrieval details", open=False, elem_id="source-panel"):
            retrieval_details = gr.JSON(label="Latest retrieved chunks", value=[])

        with gr.Accordion("About this guide", open=False, elem_id="about-panel"):
            gr.HTML(
                "16 documents &middot; 127 validated chunks &middot; all-MiniLM-L6-v2 embeddings &middot; "
                "Hybrid BM25 + semantic retrieval. Answers are grounded only in the included document collection."
            )

        event_inputs = [question_box, chat_history_state, memory_state, mode_box, topic_box, source_box]
        event_outputs = [chatbot, question_box, memory_state, retrieval_details, empty_state]
        send_event = send_button.click(fn=ask_question, inputs=event_inputs, outputs=event_outputs)
        send_event.then(fn=lambda messages: messages, inputs=chatbot, outputs=chat_history_state)
        submit_event = question_box.submit(fn=ask_question, inputs=event_inputs, outputs=event_outputs)
        submit_event.then(fn=lambda messages: messages, inputs=chatbot, outputs=chat_history_state)
        clear_event = clear_button.click(
            fn=clear_conversation,
            outputs=[chatbot, question_box, memory_state, retrieval_details, empty_state],
        )
        clear_event.then(fn=lambda messages: messages, inputs=chatbot, outputs=chat_history_state)

        for (_title, prompt), button in zip(EXAMPLE_QUESTIONS, suggestion_buttons, strict=True):
            example_event = button.click(fn=lambda value=prompt: value, outputs=question_box)
            example_event.then(fn=ask_question, inputs=event_inputs, outputs=event_outputs).then(
                fn=lambda messages: messages, inputs=chatbot, outputs=chat_history_state
            )


if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1",
        share=False,
        show_error=False,
        css=CSS,
        theme=gr.themes.Base(),
    )
