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

The ingestion pipeline in [ingest.py](ingest.py) loads all 16 documents from `documents/`: 15 `.txt` files and one `.pdf` handbook. It cleans text while preserving useful paragraph boundaries, then creates paragraph-aware chunks near 800 characters with about 150 characters of overlap. This fits the course guides, student recommendations, and longer handbook sections because it keeps related ideas together while still producing focused chunks for later retrieval. Each chunk keeps its source filename, index, file type, and topic metadata. Validation merges metadata-only fragments into nearby substantive text and rejects any that remain standalone.

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

**Model used:** `all-MiniLM-L6-v2` via `sentence-transformers`
**Execution:** Local; no embedding API key or hosted embedding service is used.
**Production tradeoff reflection:** This model is a practical local choice for a 127-chunk student project because it is lightweight and fast. For a larger or higher-stakes corpus, I would compare domain-specific retrieval accuracy, latency, multilingual needs, model size, and operating cost before choosing a larger local or hosted embedding model.

## Vector Store and Retrieval

The vector store is built in [vector_store.py](vector_store.py) using ChromaDB with persistent local storage in `chroma_db/`. The validated build embeds all 127 ingestion chunks and stores the original chunk text plus `source`, `chunk_index`, `file_type`, and `topic` metadata. Retrieval uses semantic top-k search with a default value of 4. The collection is named `howard_meche_guide` and can be recreated safely with `--rebuild`.

Example command:

python vector_store.py --rebuild
python query.py "Which course in the document collection focuses on instruments, sensors, experimental error, and uncertainty analysis?" --retrieve-only

## Retrieval Test Results

The following results came from the rebuilt 127-record ChromaDB collection using `all-MiniLM-L6-v2` and `top_k=4`.

### Query 1

**Question:** Which course in the document collection focuses on instruments, sensors, experimental error, and uncertainty analysis?

| Rank | Source | Chunk index | Distance |
|---|---|---:|---:|
| 1 | instrumentation.txt | 0 | 0.3548 |
| 2 | instrumentation.txt | 1 | 0.4252 |
| 3 | Mechanical Engineering Undergraduate Handbook.pdf | 57 | 0.5354 |
| 4 | solid_mechanics.txt | 1 | 0.5515 |

Relevance: The first chunk explicitly names MEEG-316 Instrumentation and Experimentation and includes instruments, sensors, experimental error, and uncertainty analysis. The expected source is rank 1, so this test passes.

### Query 2

**Question:** What three major modes of heat transfer should a student expect to study in Heat Transfer?

| Rank | Source | Chunk index | Distance |
|---|---|---:|---:|
| 1 | heat_transfer.txt | 0 | 0.3100 |
| 2 | heat_transfer.txt | 1 | 0.3998 |
| 3 | professor_recommendations.txt | 0 | 0.4841 |
| 4 | professor_recommendations.txt | 1 | 0.5127 |

Relevance: The rank-1 chunk is the MEEG-403 Heat Transfer description and directly states conduction, convection, and radiation. The expected source is rank 1, so this test passes.

### Query 3

**Question:** How is Howard Mechanical Engineering Senior Project structured across the senior year?

| Rank | Source | Chunk index | Distance |
|---|---|---:|---:|
| 1 | senior_design.txt | 1 | 0.3011 |
| 2 | senior_design.txt | 0 | 0.3193 |
| 3 | Mechanical Engineering Undergraduate Handbook.pdf | 1 | 0.4139 |
| 4 | Mechanical Engineering Undergraduate Handbook.pdf | 21 | 0.4226 |

Relevance: The first two chunks state that MEEG-441 and MEEG-442 form a two-course sequence, with Senior Project II continuing the work begun in Senior Project I. The expected source is rank 1, so this test passes.

### Diagnostic ranking limitation

The current evaluation question, “What topics are listed for MEEG-304 Thermodynamics in the guide?”, returned `applied_thermodynamics.txt` chunk 0 at rank 1 (distance 0.3044). The expected `thermodynamics.txt` chunk 0 appeared at rank 6 (distance 0.3593), outside the default top 4. The collection was freshly rebuilt with 127 records and the query used the same MiniLM model as indexing, so this is recorded as an embedding-ranking limitation for this wording rather than a storage or chunking failure.

## Grounded Generation

The grounded generation path is implemented in [query.py](query.py) with the Groq Python SDK. The runtime model is `openai/gpt-oss-20b`; the originally planned Llama model was unavailable to the configured Groq account. The system prompt permits only claims explicitly supported by the four retrieved chunks, forbids outside knowledge and inference, and requires this exact refusal when the context is insufficient: `I don't have enough information in the provided documents to answer that.`

Retrieved context is labeled with its source filename, chunk index, file type, and topic. The returned `sources` list is selected programmatically: a source is included only when its retrieved chunk shares at least three meaningful terms with the generated answer. The exact insufficient-information refusal always returns an empty source list.

## Example Responses

### Supported question: Engineering Computations

**Query:** Which course explicitly teaches programming and software such as MATLAB?

**Answer:** The course that explicitly teaches programming and software such as MATLAB is **MEEG‑207 Introduction to Engineering Computations**.

**Sources:** `engineering_computations.txt`

### Supported question: Heat Transfer

**Query:** What three major modes of heat transfer should a student expect to study in Heat Transfer?

**Answer:** Conduction, convection, and radiation.

**Sources:** `heat_transfer.txt`

### Out-of-scope question

**Query:** What are the best restaurants near the engineering building?

**Answer:** I don't have enough information in the provided documents to answer that.

**Sources:** *(none — insufficient-information refusal)*

## Query Interface

The application in [app.py](app.py) uses Gradio. It provides a question textbox, an Ask button, Enter-to-submit behavior, and separate Answer, Sources, and Retrieved context outputs. It displays concise errors for empty input, missing configuration, retrieval problems, and Groq failures instead of tracebacks.

Launch the interface with:

```powershell
.\.venv\Scripts\python.exe app.py
```

The validated local launch URL was `http://127.0.0.1:7861`.

**Sample interaction transcript**

> **User:** What three major modes of heat transfer should a student expect to study in Heat Transfer?
>
> **System:** Conduction, convection, and radiation.
>
> **Sources:** `heat_transfer.txt`

## Evaluation Report

Milestone 6 evaluation is pending. The completed Milestone 4 retrieval evidence and Milestone 5 grounded-generation examples are recorded above; final accuracy judgments and failure analysis will be added during the evaluation milestone.

## Document Ingestion

The local ingestion pipeline scans 16 source documents: 15 `.txt` files and one PDF handbook. It cleans and chunks the content while keeping source filename, chunk index, file type, and topic metadata for retrieval and attribution.

## Running the Project

From the repository root, use the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe ingest.py
.\.venv\Scripts\python.exe vector_store.py --rebuild
.\.venv\Scripts\python.exe query.py "Which course explicitly teaches programming and software such as MATLAB?" --retrieve-only
.\.venv\Scripts\python.exe query.py "What three modes of heat transfer are covered in MEEG-403 Heat Transfer?"
.\.venv\Scripts\python.exe app.py
```

## Demo Video

[ADD DEMO VIDEO LINK AFTER RECORDING THE FINAL PRESENTATION]

## AI Usage

This project uses AI-assisted implementation. The assistant helped build the ingestion, ChromaDB retrieval, strict grounding prompt, CLI, and Gradio wiring. Runtime examples in this README were captured from the current local corpus and configured Groq account; no API key is stored in the repository or this document.
