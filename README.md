# Unofficial Howard Mechanical Engineering Guide

## Domain

This project builds a local RAG system for student-generated knowledge about Howard University Mechanical Engineering courses. The goal is to make course expectations, workload patterns, and technical themes searchable without depending on official catalog wording alone. The knowledge is valuable because it captures student experience and practical expectations that are often scattered across notes, study groups, and informal course discussions.

## Document Sources

The repository contains 16 Howard Mechanical Engineering source documents: 15 `.txt` files and one Mechanical Engineering Undergraduate Handbook PDF. The corpus combines official program information with clearly labeled student-perspective material.

| # | Source | Type | URL or file path |
|---|--------|------|-----------------|
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
| 15 | engineering_survival_guide.txt | curriculum guidance | documents/engineering_survival_guide.txt |
| 16 | professor_recommendations.txt | student perspective | documents/professor_recommendations.txt |

## Architecture

The implemented pipeline is:

Document ingestion -> paragraph-aware chunking -> all-MiniLM-L6-v2 embeddings -> ChromaDB -> top-k retrieval -> Groq grounded generation -> Gradio interface.

## Document Pipeline

The ingestion pipeline in [ingest.py](ingest.py) loads all 16 documents from `documents/`: 15 `.txt` files and one `.pdf` handbook. It cleans text while preserving useful paragraph boundaries, then creates paragraph-aware chunks near 800 characters with about 150 characters of overlap. This fits the course guides, student recommendations, and longer handbook sections because it keeps related ideas together while still producing focused chunks for later retrieval. Each chunk keeps its source filename, index, file type, and topic metadata.

Run it directly with:

python ingest.py

## Chunking Strategy

The current implementation uses a paragraph-aware chunking strategy with a target size of 800 characters and an overlap of 150 characters. The chunking is intentionally not a blind fixed-width split: it first segments the text by paragraph, then composes and slices paragraphs while trying to keep sentence boundaries when possible. This works well for short student notes and keeps the corpus easy to debug and explain in a demo.

**Chunk size:** 800 characters  
**Overlap:** 150 characters  
**Why these choices fit your documents:** Short-to-medium text documents benefit from preserving logical paragraphs while still allowing semantically related content to overlap across chunk boundaries.  
**Final chunk count:** 127 chunks generated from the current 16-document corpus.

## Sample Chunks

These five chunks are deterministic samples produced by running `ingest.py` on the current corpus.

### Chunk 1

**Source:** `applied_thermodynamics.txt`

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

### Chunk 2

**Source:** `dynamics.txt`

```text
SOURCE: Howard University College of Engineering and Architecture
COURSE: CIEG-302 Dynamics
CREDITS: 3

CIEG-302 Dynamics studies the motion of particles, systems of particles, rigid bodies, and simple deformable mass systems.

Major topics include rectilinear and curvilinear kinematics, Newton's laws of motion and gravitation, work-energy methods, impulse-momentum methods, and conservation laws for energy and momentum.

The course also provides an introduction to vibrations and includes computer-aided engineering applications.

Within the Howard Mechanical Engineering curriculum, Dynamics is taken during the second semester of the sophomore year.
```

### Chunk 3

**Source:** `engineering_computations.txt`

```text
SOURCE: Howard University College of Engineering and Architecture
COURSE: MEEG-207 Introduction to Engineering Computations
CREDITS: 3

MEEG-207 Introduction to Engineering Computations introduces computer programming in the context of engineering problem solving.

The course covers procedural thinking, algorithm development, and methods for developing computational solutions to engineering problems.

Software packages such as MATLAB are used as engineering computation tools.

The purpose of the course is therefore not only to teach programming syntax, but also to teach students how to translate engineering problems into algorithms that can be solved computationally.
```

### Chunk 4

**Source:** `engineering_survival_guide.txt`

```text
SOURCE: Howard University Mechanical Engineering Undergraduate Program Materials
TOPIC: Navigating the Howard Mechanical Engineering Curriculum

Howard University's Mechanical Engineering curriculum progresses from foundational mathematics, science, computing, and mechanics courses into more specialized mechanical engineering subjects.

Early coursework includes Calculus, Physics, Chemistry, Introduction to Engineering, Computer Aided Design, Statics, Engineering Computations, Dynamics, Solid Mechanics, and Materials Science.
```

### Chunk 5

**Source:** `fluid_mechanics.txt`

```text
SOURCE: Howard University College of Engineering and Architecture
SOURCE PAGE: Mechanical Engineering Course Descriptions
COURSE: MEEG-307 Fluid Mechanics
CREDITS: 3

MEEG-307 Fluid Mechanics introduces the fundamental principles used to analyze the behavior of fluids.

The course covers fluid properties and fluid statics, including pressure variation and forces exerted by fluids. It also introduces the basic principles governing fluids in motion.

Major topics include conservation of mass, momentum, and energy as applied to fluid systems. These principles are used to analyze fluid flow and engineering systems involving liquids and gases.
```

## Embedding Model

**Model used:** all-MiniLM-L6-v2 via sentence-transformers  
**Production tradeoff reflection:** This model is a practical local choice for a student project because it is lightweight, easy to run offline, and fast enough for small corpora. In a higher-stakes deployment, I would weigh tradeoffs around embedding quality on domain-specific engineering language, larger context windows, multilingual support, latency, and whether a hosted model would provide better retrieval quality at a higher cost.

## Vector Store and Retrieval

The vector store is built in [vector_store.py](vector_store.py) using ChromaDB with persistent local storage in the chroma_db directory. Retrieval is performed with top-k semantic search using the default value of 4. The project supports a retrieval-only workflow so the user can inspect the actual chunks without using Groq.

Example command:

python query.py "What do students say about Thermodynamics?" --retrieve-only

## Retrieval Test Results

These retrieval results are from the current placeholder corpus and reflect the actual output of the system. They should be replaced with real student-source evidence once the corpus is populated.

**Query 1:** What do students say about Thermodynamics?

Top returned chunks:
- thermodynamics.txt | chunk_index=0 | distance=0.3088
- heat_transfer.txt | chunk_index=0 | distance=0.5527
- dynamics.txt | chunk_index=0 | distance=0.5883
- fluid_mechanics.txt | chunk_index=0 | distance=0.6025

Relevance explanation: The top result is the Thermodynamics document itself, which is the expected match. The remaining results are still related engineering courses and show the placeholder corpus is semantically near the same topic family, but not yet rich enough to answer real student opinions.

---

**Query 2:** What should I expect from Fluid Mechanics?

Top returned chunks:
- fluid_mechanics.txt | chunk_index=0 | distance=0.5765
- thermodynamics.txt | chunk_index=0 | distance=0.6750
- vibrations.txt | chunk_index=0 | distance=0.6815
- dynamics.txt | chunk_index=0 | distance=0.7111

Relevance explanation: The Fluid Mechanics document is ranked first, which is consistent with the query. The rest are neighboring engineering-course placeholders and show that the system is retrieving thematically related material without more detailed source content.

---

**Query 3:** Which classes involve MATLAB?

Top returned chunks:
- engineering_survival_guide.txt | chunk_index=0 | distance=0.7505
- vibrations.txt | chunk_index=0 | distance=0.7981
- dynamics.txt | chunk_index=0 | distance=0.8000
- materials_science.txt | chunk_index=0 | distance=0.8061

Relevance explanation: The highest-scoring result references MATLAB in the engineering survival guide placeholder. This demonstrates that the retrieval system can find a likely relevant clue, but the corpus still lacks detailed course-specific information to support a confident answer.

## Grounded Generation

The grounded generation path is implemented in [query.py](query.py). The system prompt is:

You are answering questions using only the provided retrieved documents. Do not use outside knowledge. If the provided context does not contain enough information to answer the question, say that you do not have enough information. Do not invent facts. Cite the relevant source filenames in your response.

Generation is intentionally grounded by passing only the retrieved chunks and their source names into the model. The pipeline also programmatically tracks source filenames and returns a JSON-style structure with the answer, sources, and retrieved chunks so the interface can display attribution clearly. Because the current documents are placeholder text, the model should not be expected to answer with real student claims until the corpus is replaced with authentic course material.

## Example Responses

**Grounded response 1**

Query: What do students say about Thermodynamics?

Response: [Not run with a real Groq key yet; the current documents are placeholders, so there is no authentic student evidence to quote.]

Source attribution: [Not available until valid corpus content and a configured Groq API key are present.]

---

**Grounded response 2**

Query: What should I expect from Fluid Mechanics?

Response: [Not run with a real Groq key yet; the current documents are placeholders, so there is no authentic student evidence to quote.]

Source attribution: [Not available until valid corpus content and a configured Groq API key are present.]

---

**Out-of-scope query**

Query: What are the best campus food options near the engineering building?

System response (refusal): [The project is intentionally scoped to Howard Mechanical Engineering course knowledge. A real answer should be refused unless the dataset includes relevant food-related material.] 

## Query Interface

The application in [app.py](app.py) presents a simple Gradio interface with a single question textbox, an Ask button, and output areas for the answer, sources, and retrieved context JSON. It is designed to be easy to demo locally without extra styling.

**Input fields:** Question text box  
**Output format:** Answer, sources list, retrieved context block

**Sample interaction transcript**

> **User:** What do students say about Thermodynamics?
>
> **System:** This project currently runs on placeholder course documents. Once real student sources are added and a valid Groq API key is configured, the system will answer using only the retrieved context and cite source files.

## Evaluation Report

These five evaluation questions are ready to run once the project has a valid corpus and Groq key. The expected answers remain placeholders because no authentic student-source corpus is present yet.

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 | What do students say about Thermodynamics? | TBD after actual source material is added | [Not run with valid Groq key yet] | Partially relevant | TBD |
| 2 | What should I expect from Fluid Mechanics? | TBD after actual source material is added | [Not run with valid Groq key yet] | Partially relevant | TBD |
| 3 | Which classes involve MATLAB? | TBD after actual source material is added | [Not run with valid Groq key yet] | Partially relevant | TBD |
| 4 | What is Senior Design like? | TBD after actual source material is added | [Not run with valid Groq key yet] | Partially relevant | TBD |
| 5 | Which courses are especially math-heavy? | TBD after actual source material is added | [Not run with valid Groq key yet] | Partially relevant | TBD |

**Retrieval quality:** Relevant / Partially relevant / Off-target  
**Response accuracy:** Accurate / Partially accurate / Inaccurate

## Failure Case Analysis

**Question that failed:** Which classes involve MATLAB?

**What the system returned:** The retrieval system surfaced the engineering_survival_guide placeholder and nearby course documents, but the real answer could not be verified because the corpus had no authentic student text yet.

**Root cause (tied to a specific pipeline stage):** The failure is caused by the document corpus itself: the placeholder files are intentionally generic and do not contain real student-generated evidence. Retrieval still works technically, but it has no domain-grounded content to justify a full answer.

**What you would change to fix it:** Replace placeholder documents with real student notes or summaries, then rerun ingestion and retrieval. After that, validate the top-k results against the source text and confirm the Groq key is configured before generation.

## Spec Reflection

**One way the spec helped you during implementation:** The project specification gave a clear RAG structure and explicit expectations for ingestion, retrieval, source attribution, and a local demo. That helped keep the implementation small, modular, and aligned with the required pipeline.

**One way your implementation diverged from the spec, and why:** The original starter repository provided only templates, so I created the full project from scratch rather than inheriting a prebuilt app. I also kept the corpus intentionally placeholder-based until authentic student documents are supplied, because inventing fake sources would violate the academic requirement.

## AI Usage

**Instance 1**

- *What I gave the AI:* The starter repository structure, the project requirements, and the need for a small local RAG pipeline.
- *What it produced:* Initial Python scaffolding for ingestion, a ChromaDB embedding flow, and the general architecture for query and Gradio code.
- *What I changed or overrode:* I reviewed the generated code, preserved the requested starter structure, adjusted chunking and metadata behavior, and kept the final implementation simple and readable rather than accepting a more abstract or overengineered design.

**Instance 2**

- *What I gave the AI:* The requirements for grounded generation, source attribution, and the command-line query interface.
- *What it produced:* A prompt template and response structure that enforced using only retrieved context and listing sources.
- *What I changed or overrode:* I added explicit runtime checks for missing Groq keys, made the retrieval output copy-friendly for README work, and ensured the answer path fails gracefully when the corpus is not yet populated.

## Document Ingestion

The implementation is fully local and intentionally simple: it scans the documents folder, reads .txt files, cleans them, and emits chunk dictionaries that include the source filename and chunk position. The project is ready for real student sources to be dropped into the same folder.

## Running the Project

From the repository root, run the following commands in the project virtual environment:

python -m venv .venv
.venv\Scripts\Activate.ps1  # PowerShell
python -m pip install -r requirements.txt
python ingest.py
python vector_store.py --rebuild
python query.py "What do students say about Thermodynamics?" --retrieve-only
python app.py

## Demo Video

[ADD DEMO VIDEO LINK AFTER RECORDING THE FINAL PRESENTATION]

## AI Usage

The project was implemented with the assistance of an AI coding assistant in the VS Code environment. The actual code was reviewed and adjusted manually to stay aligned with the project requirements and to avoid fabricating source material or evaluation results.
