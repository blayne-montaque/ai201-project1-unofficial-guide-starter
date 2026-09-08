# Unofficial Howard Mechanical Engineering Guide

## Domain

This project is a local RAG system for Howard University Mechanical Engineering course and program information. It combines official Howard course and program materials with clearly labeled student-perspective guidance, making course topics, curriculum structure, and practical guidance searchable through natural-language questions. It does not represent every source as a firsthand student review.

## Document Sources

The repository contains 16 Howard Mechanical Engineering source documents: 15 `.txt` files and one Mechanical Engineering Undergraduate Handbook PDF.

| # | Source | Type | File path |
|---|---|---|---|
| 1 | Mechanical Engineering Undergraduate Handbook.pdf | official handbook | documents/Mechanical Engineering Undergraduate Handbook.pdf |
| 2 | thermodynamics.txt | course guide | documents/thermodynamics.txt |
| 3 | applied_thermodynamics.txt | course guide | documents/applied_thermodynamics.txt |
| 4 | fluid_mechanics.txt | course guide | documents/fluid_mechanics.txt |
| 5 | heat_transfer.txt | course guide | documents/heat_transfer.txt |
| 6 | dynamics.txt | course guide | documents/dynamics.txt |
| 7 | solid_mechanics.txt | course guide | documents/solid_mechanics.txt |
| 8 | materials_science.txt | course guide | documents/materials_science.txt |
| 9 | engineering_computations.txt | course guide | documents/engineering_computations.txt |
| 10 | system_dynamics.txt | course guide | documents/system_dynamics.txt |
| 11 | instrumentation.txt | course guide | documents/instrumentation.txt |
| 12 | vibrations.txt | course guide | documents/vibrations.txt |
| 13 | senior_design.txt | course guide | documents/senior_design.txt |
| 14 | mechanical_engineering_program.txt | program overview | documents/mechanical_engineering_program.txt |
| 15 | engineering_survival_guide.txt | student-oriented curriculum guidance | documents/engineering_survival_guide.txt |
| 16 | professor_recommendations.txt | student-perspective course/professor guidance | documents/professor_recommendations.txt |

## Architecture

Documents -> cleaning and paragraph-aware chunking -> `all-MiniLM-L6-v2` embeddings -> ChromaDB -> semantic top-k retrieval -> grounded Groq generation -> programmatic source attribution -> Gradio interface.

## Document Pipeline

[ingest.py](ingest.py) discovers and loads all 16 supported files from `documents/`: 15 UTF-8 text files and one PDF handbook. It preserves useful paragraph boundaries while cleaning text, emits source filename, chunk index, file type, and topic metadata, and validates every output chunk. Metadata-only fragments are merged into nearby substantive text or rejected, so a source line cannot be emitted as a standalone retrieval chunk.

The validated ingestion run produced 127 chunks. Run it with:

```powershell
.\.venv\Scripts\python.exe ingest.py
```

## Chunking Strategy

The chunker is paragraph-aware, targets roughly 800 characters, and keeps about 150 characters of overlap. It combines short related paragraphs where possible and sentence- or word-splits long paragraphs. This preserves coherent course descriptions while retaining enough focus for semantic retrieval.

- Target chunk size: 800 characters
- Overlap: 150 characters
- Validated corpus: 16 documents and 127 chunks
- Validation: no empty, whitespace-only, or metadata-only chunks

### Sample Chunks

These are five deterministic samples from the validated current corpus.

#### Chunk 1 — `applied_thermodynamics.txt`

```text
SOURCE: Howard University Undergraduate Catalogue
COURSE: MEEG-306 Applied Thermodynamics
CREDITS: 3

MEEG-306 Applied Thermodynamics builds on the introductory Thermodynamics course and focuses on applications of thermodynamic principles.

Major subjects include mixtures, combustion, power cycles, gas turbines, compressors, reciprocating engines, refrigeration, and reactive systems.

The course also introduces Onsager relations and direct energy conversion. Laboratory work is included as part of the course.

Within the Howard Mechanical Engineering curriculum, Applied Thermodynamics is normally taken during the second semester of the junior year.

It follows MEEG-304 Thermodynamics and is part of the thermal and energy side of the Mechanical Engineering curriculum.
```

#### Chunk 2 — `dynamics.txt`

```text
SOURCE: Howard University College of Engineering and Architecture
COURSE: CIEG-302 Dynamics
CREDITS: 3

CIEG-302 Dynamics studies the motion of particles, systems of particles, rigid bodies, and simple deformable mass systems.

Major topics include rectilinear and curvilinear kinematics, Newton's laws of motion and gravitation, work-energy methods, impulse-momentum methods, and conservation laws for energy and momentum.

The course also provides an introduction to vibrations and includes computer-aided engineering applications.

Within the Howard Mechanical Engineering curriculum, Dynamics is taken during the second semester of the sophomore year.
```

#### Chunk 3 — `engineering_computations.txt`

```text
SOURCE: Howard University College of Engineering and Architecture
COURSE: MEEG-207 Introduction to Engineering Computations
CREDITS: 3

MEEG-207 Introduction to Engineering Computations introduces computer programming in the context of engineering problem solving.

The course covers procedural thinking, algorithm development, and methods for developing computational solutions to engineering problems.

Software packages such as MATLAB are used as engineering computation tools.

The purpose of the course is therefore not only to teach programming syntax, but also to teach students how to translate engineering problems into algorithms that can be solved computationally.
```

#### Chunk 4 — `engineering_survival_guide.txt`

```text
SOURCE: Howard University Mechanical Engineering Undergraduate Program Materials
TOPIC: Navigating the Howard Mechanical Engineering Curriculum

Howard University's Mechanical Engineering curriculum progresses from foundational mathematics, science, computing, and mechanics courses into more specialized mechanical engineering subjects.

Early coursework includes Calculus, Physics, Chemistry, Introduction to Engineering, Computer Aided Design, Statics, Engineering Computations, Dynamics, Solid Mechanics, and Materials Science.
```

#### Chunk 5 — `fluid_mechanics.txt`

```text
SOURCE: Howard University College of Engineering and Architecture
SOURCE PAGE: Mechanical Engineering Course Descriptions
COURSE: MEEG-307 Fluid Mechanics
CREDITS: 3

MEEG-307 Fluid Mechanics introduces the fundamental principles used to analyze the behavior of fluids.

The course covers fluid properties and fluid statics, including pressure variation and forces exerted by fluids. It also introduces the basic principles governing fluids in motion.

Major topics include conservation of mass, momentum, and energy as applied to fluid systems. These principles are used to analyze fluid flow and engineering systems involving liquids and gases.
```

## Embeddings and Vector Store

[vector_store.py](vector_store.py) embeds the 127 validated chunks locally with `sentence-transformers/all-MiniLM-L6-v2` and persists them in ChromaDB at `chroma_db/`. The collection is named `howard_meche_guide`; each record retains its original text, source, chunk index, file type, and topic. A rebuild verifies that 127 records were stored.

`all-MiniLM-L6-v2` is a practical local choice for this small corpus because it is lightweight and fast. A production system should compare retrieval accuracy, latency, model size, domain performance, multilingual needs, and operating cost before selecting a larger local or hosted embedding model.

## Retrieval

Retrieval uses semantic top-k search with `top_k = 4`. The following real retrieval checks were made against the rebuilt 127-record collection.

### Instrumentation query

**Question:** Which course in the document collection focuses on instruments, sensors, experimental error, and uncertainty analysis?

| Rank | Source | Chunk index | Distance |
|---|---|---:|---:|
| 1 | instrumentation.txt | 0 | 0.3548 |
| 2 | instrumentation.txt | 1 | 0.4252 |
| 3 | Mechanical Engineering Undergraduate Handbook.pdf | 57 | 0.5354 |
| 4 | solid_mechanics.txt | 1 | 0.5515 |

The expected course source is ranked first. Its chunk explicitly names MEEG-316 Instrumentation and Experimentation and the measurement topics.

### Heat Transfer query

**Question:** What three major modes of heat transfer should a student expect to study in Heat Transfer?

| Rank | Source | Chunk index | Distance |
|---|---|---:|---:|
| 1 | heat_transfer.txt | 0 | 0.3100 |
| 2 | heat_transfer.txt | 1 | 0.3998 |
| 3 | professor_recommendations.txt | 0 | 0.4841 |
| 4 | professor_recommendations.txt | 1 | 0.5127 |

The rank-1 chunk explicitly states conduction, convection, and radiation.

### Senior Project query

**Question:** How is Howard Mechanical Engineering Senior Project structured across the senior year?

| Rank | Source | Chunk index | Distance |
|---|---|---:|---:|
| 1 | senior_design.txt | 1 | 0.3011 |
| 2 | senior_design.txt | 0 | 0.3193 |
| 3 | Mechanical Engineering Undergraduate Handbook.pdf | 1 | 0.4139 |
| 4 | Mechanical Engineering Undergraduate Handbook.pdf | 21 | 0.4226 |

The first two results describe the MEEG-441/MEEG-442 sequence and that Senior Project II continues the work begun in Senior Project I.

## Grounded Generation and Attribution

[query.py](query.py) uses the Groq Python SDK and the configured `openai/gpt-oss-20b` model. The project previously tested a Llama model, but the active account returned a model-availability error; this working runtime model is therefore documented instead.

Grounding works as follows:

1. Semantic retrieval returns the top four chunks with metadata.
2. `query.py` formats those chunks as the model context.
3. The system prompt permits only claims supported by that context and forbids outside knowledge or unsupported inference.
4. Groq generates a concise answer from the retrieved context.
5. If Groq returns an empty completion, the same generation request is retried once. A second empty completion remains an explicit runtime failure rather than a fabricated refusal.
6. Source filenames are derived programmatically from chunks that share at least three meaningful terms with the final answer; the model does not invent citations.
7. When context is insufficient, the answer is exactly `I don't have enough information in the provided documents to answer that.` and the source list is empty.

### Real Example Responses

**Query:** Which course explicitly teaches programming and software such as MATLAB?

**Answer:** The course that explicitly teaches programming and software such as MATLAB is **MEEG-207 Introduction to Engineering Computations**.

**Sources:** `engineering_computations.txt`

**Query:** What three major modes of heat transfer should a student expect to study in Heat Transfer?

**Answer:** Conduction, convection, and radiation.

**Sources:** `heat_transfer.txt`

**Query:** What are the best restaurants near the engineering building?

**Answer:** I don't have enough information in the provided documents to answer that.

**Sources:** *(none — insufficient-information refusal)*

## Query Interface

[app.py](app.py) provides a local Gradio interface with a question textbox, Ask button, Enter-to-submit behavior, an answer field, a source display, and retrieved-context JSON. It displays concise errors instead of Python tracebacks and is not publicly hosted.

Run it with:

```powershell
.\.venv\Scripts\python.exe app.py
```

The final validation launched the app at `http://127.0.0.1:7862` and confirmed that the port accepted a local TCP connection.

**Sample interaction:** Asking the Heat Transfer question above returned `Conduction, convection, and radiation.` with source `heat_transfer.txt`.

## Evaluation Report

[evaluate.py](evaluate.py) runs the five questions defined in [planning.md](planning.md), prints each actual response with the top-four retrieval results, assigns a concept-level judgment, and writes [evaluation_results.json](evaluation_results.json) from that runtime output.

| # | Question | Expected answer | Actual response | Sources | Judgment |
|---|---|---|---|---|---|
| 1 | What topics are listed for MEEG-304 Thermodynamics in the guide? | Laws of thermodynamics, pure substances, entropy, and availability | I don't have enough information in the provided documents to answer that. | None | Inaccurate |
| 2 | Which course focuses on instruments, sensors, experimental error, and uncertainty analysis? | MEEG-316 Instrumentation and Experimentation plus the listed measurement topics | MEEG-316 Instrumentation & Experimentation Lab | instrumentation.txt | Partially Accurate |
| 3 | What three major modes of heat transfer should a student expect to study in Heat Transfer? | Conduction, convection, and radiation | The three major modes of heat transfer covered are conduction, convection, and radiation. | heat_transfer.txt | Accurate |
| 4 | How is Howard Mechanical Engineering Senior Project structured across the senior year? | MEEG-441 and MEEG-442 two-course sequence; II continues I | A two-course, year-long sequence; MEEG-442 continues the MEEG-441 design work | senior_design.txt; Mechanical Engineering Undergraduate Handbook.pdf | Accurate |
| 5 | According to the guide, which course is mainly about designing aircraft wings? | Exact insufficient-information refusal | REQUEST FAILED: The generation service returned an empty response. Please try again. | None | Inaccurate (runtime failure) |

The evaluation report was generated from a live run. Question 2 is partially accurate because the system identifies the correct course and source but omits the requested instruments/sensors, experimental-error, and uncertainty details. Question 1 is inaccurate because the correct MEEG-304 description was not retrieved in the top-four context; the model correctly refused rather than inventing an answer. Question 5 exhausted the one empty-response retry and therefore did not evaluate the RAG refusal behavior; it is recorded as an explicit runtime failure rather than as a fabricated refusal. Question 1 remains the primary documented pipeline failure because it is reproducibly caused by retrieval ranking.

## Failure Case Analysis

**Question that struggled:** What topics are listed for MEEG-304 Thermodynamics in the guide?

**Observed retrieval behavior:** The top result was `applied_thermodynamics.txt` chunk 0 at distance 0.3044. The four retrieved chunks were that Applied Thermodynamics chunk plus handbook chunks 56, 53, and 55. The direct `thermodynamics.txt` chunk appeared at rank 6 at distance 0.3593 when the same query was checked with `--top-k 10`.

**Actual generated response:** `I don't have enough information in the provided documents to answer that.`

**Pipeline stage responsible:** Retrieval ranking. The MiniLM embedding recognized strong semantic similarity between the query and Applied Thermodynamics, so the related MEEG-306 material ranked above the direct MEEG-304 description. The default top-k cutoff of 4 excluded the chunk containing the required laws, pure-substance, entropy, and availability content. Grounded generation therefore had no valid evidence to use and refused.

**Future improvement:** A hybrid lexical-plus-semantic ranker, metadata filtering, reranking, or a justified top-k adjustment could improve this exact-course query. None of those stretch features is implemented in this milestone.

## Spec Reflection

**How the specification helped:** The staged milestone structure required retrieval to be tested before generation. That separation exposed the Thermodynamics ranking problem independently of the language model and prevented a fluent generated answer from hiding a retrieval weakness.

**How the implementation diverged:** The corpus includes a PDF handbook in addition to text documents, and the implementation adds validation for metadata-only fragments. Source attribution is also derived programmatically from supporting retrieved chunks instead of relying on the language model to compose citations. These additions preserve the required pipeline while making its evidence and failures easier to inspect.

## AI Usage

### Instance 1 — ingestion and chunking

- **What I gave the AI:** The project requirements, corpus layout, and the paragraph-aware 800-character / 150-character-overlap plan.
- **What it produced:** Python scaffolding for document discovery, text/PDF loading, cleaning, chunk construction, and chunk metadata.
- **What I reviewed and changed:** I inspected the ingestion output after a metadata-only source fragment appeared, then directed changes that merge metadata with substantive prose or reject it. I reran ingestion to verify that all 16 documents load and the final 127 chunks contain no empty or metadata-only records.

### Instance 2 — retrieval, generation, and attribution

- **What I gave the AI:** The requirements for local MiniLM embeddings, ChromaDB retrieval, strict context-only Groq generation, and source attribution.
- **What it produced:** Vector-store/query wiring, a grounded prompt, CLI output, and Gradio integration.
- **What I reviewed and changed:** I tested retrieval outputs and live generation responses, observed that top-k filenames could expose irrelevant sources, and changed attribution so only chunks that substantively support the answer contribute a source. I also verified that insufficient-information refusals return no source list.

### Instance 3 — evaluation and documentation

- **What I gave the AI:** The existing planning evaluation questions and actual terminal results.
- **What it produced:** A small reproducible evaluator and README organization.
- **What I reviewed and changed:** I preserved the planning questions, reran them against the live system, retained the inaccurate Thermodynamics result, and based the report and failure analysis on the saved runtime data rather than predicted outputs.

## Running the Project

From the repository root, use the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe ingest.py
.\.venv\Scripts\python.exe vector_store.py --rebuild
.\.venv\Scripts\python.exe query.py "Which course explicitly teaches programming and software such as MATLAB?" --retrieve-only
.\.venv\Scripts\python.exe query.py "Which course explicitly teaches programming and software such as MATLAB?"
.\.venv\Scripts\python.exe evaluate.py
.\.venv\Scripts\python.exe app.py
```

## Demo Video

Demo video: [ADD LINK AFTER RECORDING]

### Demo Checklist

Keep the recording to 3–5 minutes and show:

1. The Gradio interface and the MATLAB query, including the MEEG-207 answer and `engineering_computations.txt` source.
2. The Heat Transfer query, including conduction, convection, radiation, and `heat_transfer.txt`.
3. The Thermodynamics weakness: show that related content ranks highly while the direct MEEG-304 chunk falls outside top-k 4.
4. The out-of-scope restaurant query to demonstrate the exact refusal with no sources.
5. The evaluation report and its documented judgments.
