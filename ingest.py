from __future__ import annotations

import html
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

DEFAULT_TARGET_CHUNK_SIZE = 800
DEFAULT_OVERLAP = 150
MIN_USEFUL_CHUNK_SIZE = 80
SUPPORTED_FILE_TYPES = {".txt": "txt", ".pdf": "pdf"}
METADATA_LINE_PATTERN = re.compile(
    r"^(?:SOURCE(?:\s+(?:URL|PAGE))?|COURSE|CREDITS|CATEGORY|TOPIC|AUTHOR|NOTE)\s*:",
    re.IGNORECASE,
)


def topic_from_source(source: str) -> str:
    """Create a stable topic identifier from a source filename."""
    stem = Path(source).stem.lower()
    return re.sub(r"[^a-z0-9]+", "_", stem).strip("_")


def clean_text(raw_text: str) -> str:
    """Clean text without removing paragraph boundaries or engineering details."""
    text = html.unescape(raw_text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")

    cleaned_lines: list[str] = []
    previous_line_was_blank = False
    for line in text.split("\n"):
        normalized_line = re.sub(r"[\t ]+", " ", line).strip()
        if normalized_line:
            cleaned_lines.append(normalized_line)
            previous_line_was_blank = False
        elif cleaned_lines and not previous_line_was_blank:
            cleaned_lines.append("")
            previous_line_was_blank = True

    return "\n".join(cleaned_lines).strip()


def normalize_text(raw_text: str) -> str:
    """Backward-compatible name for the project cleaning function."""
    return clean_text(raw_text)


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract readable text from each page of a PDF with pdfplumber."""
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError(
            "PDF support requires pdfplumber. Install dependencies with "
            "'.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt'."
        ) from exc

    page_texts: list[str] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    page_texts.append(page_text)
                else:
                    print(f"WARNING: No extractable text found on page {page_number} of {pdf_path.name}.")
    except Exception as exc:
        raise RuntimeError(f"Could not extract text from PDF '{pdf_path.name}': {exc}") from exc

    extracted_text = "\n\n".join(page_texts)
    if not extracted_text.strip():
        raise ValueError(f"PDF '{pdf_path.name}' did not contain extractable text.")
    return extracted_text


def discover_document_files(doc_dir: str | Path = "documents") -> list[Path]:
    """Return every file in the documents directory in a stable order."""
    folder = Path(doc_dir)
    if not folder.exists():
        raise FileNotFoundError(f"Documents directory does not exist: {folder}")
    if not folder.is_dir():
        raise NotADirectoryError(f"Documents path is not a directory: {folder}")
    return sorted((path for path in folder.iterdir() if path.is_file()), key=lambda path: path.name.lower())


def load_documents(doc_dir: str | Path = "documents") -> list[dict[str, str]]:
    """Load and clean every supported document while retaining source metadata."""
    folder = Path(doc_dir)

    documents: list[dict[str, str]] = []
    for document_path in discover_document_files(doc_dir):

        file_type = SUPPORTED_FILE_TYPES.get(document_path.suffix.lower())
        if file_type is None:
            print(f"WARNING: Unsupported file type ignored: {document_path.name}")
            continue

        if file_type == "txt":
            try:
                raw_text = document_path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(f"Could not decode text document '{document_path.name}' as UTF-8.") from exc
        else:
            raw_text = extract_pdf_text(document_path)

        text = clean_text(raw_text)
        if not text:
            raise ValueError(f"Document '{document_path.name}' is empty after cleaning.")

        documents.append(
            {
                "source": document_path.name,
                "text": text,
                "file_type": file_type,
                "topic": topic_from_source(document_path.name),
            }
        )

    if not documents:
        raise ValueError(f"No supported, non-empty documents found in {folder}.")
    return documents


def split_into_paragraphs(text: str) -> list[str]:
    """Split cleaned text on intentional blank-line paragraph separators."""
    return [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]


def _sentence_boundary(text: str, start: int, end: int) -> int | None:
    """Return the latest useful sentence boundary before an end position."""
    boundaries = [match.end() for match in re.finditer(r"[.!?](?:\s+|$)", text[start:end])]
    if not boundaries:
        return None

    absolute_boundaries = [start + boundary for boundary in boundaries]
    useful_boundaries = [boundary for boundary in absolute_boundaries if boundary > start + 160]
    return useful_boundaries[-1] if useful_boundaries else None


def _overlap_tail(text: str, overlap: int) -> str:
    """Return a sentence-aligned tail for the next paragraph-aware chunk."""
    if overlap <= 0 or len(text) <= overlap:
        return text.strip()

    target_start = len(text) - overlap
    sentence_starts = [0]
    sentence_starts.extend(match.end() for match in re.finditer(r"[.!?]\s+", text))
    suitable_starts = [start for start in sentence_starts if start <= target_start]
    if suitable_starts:
        return text[suitable_starts[-1] :].strip()

    next_space = text.find(" ", target_start)
    if next_space == -1:
        return text[target_start:].strip()
    return text[next_space + 1 :].strip()


def chunk_paragraph(
    paragraph: str,
    target_size: int = DEFAULT_TARGET_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[str]:
    """Split one long paragraph at sentence boundaries, retaining overlap."""
    paragraph = paragraph.strip()
    if not paragraph:
        return []
    if len(paragraph) <= target_size:
        return [paragraph]

    chunks: list[str] = []
    start = 0
    while start < len(paragraph):
        proposed_end = min(start + target_size, len(paragraph))
        end = proposed_end
        if proposed_end < len(paragraph):
            sentence_end = _sentence_boundary(paragraph, start, proposed_end)
            if sentence_end is not None and sentence_end >= start + target_size // 2:
                end = sentence_end
            else:
                word_end = paragraph.rfind(" ", start + target_size // 2, proposed_end)
                if word_end > start:
                    end = word_end

        chunk = paragraph[start:end].strip()
        if not chunk:
            raise ValueError("Chunking produced an empty chunk from a non-empty paragraph.")
        chunks.append(chunk)

        if end >= len(paragraph):
            break

        overlap_start = max(start, end - overlap)
        word_start = paragraph.rfind(" ", start, overlap_start)
        start = word_start + 1 if word_start > start else overlap_start

    return chunks


def chunk_text(
    text: str,
    target_size: int = DEFAULT_TARGET_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[str]:
    """Build paragraph-aware chunks near the target size with useful overlap."""
    if target_size <= 0:
        raise ValueError("target_size must be positive.")
    if overlap < 0 or overlap >= target_size:
        raise ValueError("overlap must be non-negative and smaller than target_size.")

    paragraphs = split_into_paragraphs(text)
    if not paragraphs:
        return []

    chunks: list[str] = []
    current_chunk = ""

    for paragraph in paragraphs:
        if len(paragraph) > target_size:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            chunks.extend(chunk_paragraph(paragraph, target_size, overlap))
            continue

        if not current_chunk:
            current_chunk = paragraph
        elif len(current_chunk) + 2 + len(paragraph) <= target_size:
            current_chunk = f"{current_chunk}\n\n{paragraph}"
        else:
            chunks.append(current_chunk.strip())
            overlap_text = _overlap_tail(current_chunk, overlap)
            candidate = f"{overlap_text}\n\n{paragraph}".strip()
            current_chunk = candidate if len(candidate) <= target_size + overlap else paragraph

    if current_chunk:
        chunks.append(current_chunk.strip())

    return [chunk for chunk in chunks if chunk and chunk.strip()]


def is_low_information_chunk(text: str) -> bool:
    """Identify empty or metadata-only chunks without discarding short factual prose."""
    if not text or not text.strip():
        return True

    content_lines: list[str] = []
    for line in text.splitlines():
        cleaned_line = line.strip()
        if not cleaned_line or re.fullmatch(r"[-=_]{3,}", cleaned_line):
            continue
        if METADATA_LINE_PATTERN.match(cleaned_line):
            continue
        content_lines.append(cleaned_line)

    content = " ".join(content_lines)
    return not bool(re.search(r"[A-Za-z]{3,}", content))


def merge_low_information_chunks(document_chunks: list[str], source: str) -> list[str]:
    """Attach metadata-only fragments to nearby substantive chunks or fail clearly."""
    merged_chunks: list[str] = []
    leading_metadata: list[str] = []

    for chunk in document_chunks:
        cleaned_chunk = chunk.strip()
        if is_low_information_chunk(cleaned_chunk):
            if merged_chunks:
                merged_chunks[-1] = f"{merged_chunks[-1]}\n\n{cleaned_chunk}".strip()
            else:
                leading_metadata.append(cleaned_chunk)
            continue

        if leading_metadata:
            cleaned_chunk = "\n\n".join([*leading_metadata, cleaned_chunk])
            leading_metadata = []
        merged_chunks.append(cleaned_chunk)

    if leading_metadata:
        if merged_chunks:
            metadata_block = "\n\n".join(leading_metadata)
            merged_chunks[-1] = f"{merged_chunks[-1]}\n\n{metadata_block}".strip()
        else:
            raise ValueError(f"Document '{source}' contains metadata but no substantive content.")
    return merged_chunks


def build_chunks(
    documents: list[dict[str, str]],
    target_size: int = DEFAULT_TARGET_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[dict[str, Any]]:
    """Convert loaded documents into reusable text chunks and metadata records."""
    chunks: list[dict[str, Any]] = []
    for document in documents:
        document_chunks = merge_low_information_chunks(
            chunk_text(document["text"], target_size=target_size, overlap=overlap),
            document["source"],
        )
        if not document_chunks:
            raise ValueError(f"Document '{document['source']}' produced no chunks.")

        for chunk_index, chunk in enumerate(document_chunks):
            chunks.append(
                {
                    "text": chunk.strip(),
                    "source": document["source"],
                    "chunk_index": chunk_index,
                    "file_type": document["file_type"],
                    "topic": document["topic"],
                }
            )
    return chunks


def load_chunks(
    doc_dir: str | Path = "documents",
    target_size: int = DEFAULT_TARGET_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[dict[str, Any]]:
    """Convenience function retained for later retrieval milestones."""
    return build_chunks(load_documents(doc_dir), target_size=target_size, overlap=overlap)


def validate_documents(documents: list[dict[str, str]]) -> None:
    """Raise clear errors for missing document metadata or empty content."""
    required_fields = {"source", "text", "file_type", "topic"}
    errors: list[str] = []
    for index, document in enumerate(documents):
        missing = [field for field in required_fields if not document.get(field)]
        if missing:
            errors.append(f"Document {index} is missing metadata: {', '.join(sorted(missing))}.")
        elif not document["text"].strip():
            errors.append(f"Document '{document['source']}' contains only whitespace.")
    if errors:
        raise ValueError("Document validation failed:\n- " + "\n- ".join(errors))


def validate_chunks(chunks: list[dict[str, Any]]) -> list[str]:
    """Raise errors for invalid chunks and return warnings for unusually small chunks."""
    if not chunks:
        raise ValueError("Chunk validation failed: no chunks were produced.")

    required_fields = {"source", "text", "chunk_index", "file_type", "topic"}
    errors: list[str] = []
    warnings: list[str] = []
    for index, chunk in enumerate(chunks):
        missing = [field for field in required_fields if field not in chunk or chunk[field] in (None, "")]
        if missing:
            errors.append(f"Chunk {index} is missing metadata: {', '.join(sorted(missing))}.")
            continue
        if not str(chunk["text"]).strip():
            errors.append(f"Chunk {index} from '{chunk['source']}' is empty or whitespace-only.")
            continue
        if is_low_information_chunk(str(chunk["text"])):
            errors.append(
                f"Chunk {index} from '{chunk['source']}' contains only metadata or no meaningful content."
            )
            continue
        if len(str(chunk["text"])) < MIN_USEFUL_CHUNK_SIZE:
            warnings.append(
                f"Suspiciously tiny chunk: {chunk['source']} #{chunk['chunk_index']} "
                f"is {len(str(chunk['text']))} characters."
            )

    if errors:
        raise ValueError("Chunk validation failed:\n- " + "\n- ".join(errors))
    return warnings


def chunk_statistics(documents: list[dict[str, str]], chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate deterministic, human-readable ingestion statistics."""
    lengths = [len(str(chunk["text"])) for chunk in chunks]
    per_document = Counter(str(chunk["source"]) for chunk in chunks)
    file_type_counts = Counter(document["file_type"] for document in documents)
    return {
        "documents_loaded": len(documents),
        "txt_files": file_type_counts["txt"],
        "pdf_files": file_type_counts["pdf"],
        "total_chunks": len(chunks),
        "min_chunk_length": min(lengths),
        "max_chunk_length": max(lengths),
        "average_chunk_length": mean(lengths),
        "chunks_per_document": dict(sorted(per_document.items())),
    }


def select_representative_chunks(chunks: list[dict[str, Any]], count: int = 5) -> list[dict[str, Any]]:
    """Select long, readable chunks from distinct sources in a stable order."""
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for chunk in chunks:
        by_source[str(chunk["source"])].append(chunk)

    samples: list[dict[str, Any]] = []
    for source in sorted(by_source, key=str.lower):
        first_chunk = next(
            (chunk for chunk in by_source[source] if int(chunk["chunk_index"]) == 0),
            None,
        )
        best_chunk = first_chunk or sorted(
            by_source[source], key=lambda chunk: (-len(str(chunk["text"])), int(chunk["chunk_index"]))
        )[0]
        samples.append(best_chunk)
        if len(samples) == count:
            break
    return samples


def print_cleaned_preview(document: dict[str, str], preview_length: int = 600) -> None:
    preview = document["text"][:preview_length].rstrip()
    if len(document["text"]) > preview_length:
        preview += "..."
    print("\nCLEANED DOCUMENT PREVIEW")
    print(f"Source: {document['source']}")
    print(preview)


def print_document_loading_report(discovered_files: list[Path], documents: list[dict[str, str]]) -> None:
    """Print the complete discovery and successful-load record for validation."""
    supported_files = [
        path for path in discovered_files if path.suffix.lower() in SUPPORTED_FILE_TYPES
    ]
    print("DOCUMENT DISCOVERY")
    print(f"Files discovered: {len(discovered_files)}")
    for path in discovered_files:
        file_type = SUPPORTED_FILE_TYPES.get(path.suffix.lower(), "unsupported")
        print(f"- {path.name} ({file_type})")
    print(f"Supported documents discovered: {len(supported_files)}")
    print(f"Documents successfully loaded: {len(documents)}")
    for document in documents:
        print(f"- {document['source']} ({document['file_type']})")


def print_summary(statistics: dict[str, Any], warnings: list[str]) -> None:
    print("\nINGESTION STATISTICS")
    print(f"Documents loaded: {statistics['documents_loaded']}")
    print(f".txt files: {statistics['txt_files']}")
    print(f".pdf files: {statistics['pdf_files']}")
    print(f"Total chunks: {statistics['total_chunks']}")
    print(f"Minimum chunk length: {statistics['min_chunk_length']} characters")
    print(f"Maximum chunk length: {statistics['max_chunk_length']} characters")
    print(f"Average chunk length: {statistics['average_chunk_length']:.1f} characters")
    print("Chunks per document:")
    for source, count in statistics["chunks_per_document"].items():
        print(f"- {source}: {count}")

    for warning in warnings:
        print(f"WARNING: {warning}")
    if statistics["total_chunks"] < 50 or statistics["total_chunks"] > 2000:
        print(
            "WARNING: Total chunks are outside the assignment's suggested 50-2,000 range. "
            "Review the corpus and chunking results before changing the planned strategy."
        )


def print_sample_chunks(samples: list[dict[str, Any]]) -> None:
    for number, chunk in enumerate(samples, start=1):
        print(f"\nChunk {number}")
        print(f"Source: {chunk['source']}")
        print(f"Chunk Index: {chunk['chunk_index']}")
        print(f"Length: {len(str(chunk['text']))} characters\n")
        print(chunk["text"])


def main() -> None:
    discovered_files = discover_document_files()
    documents = load_documents()
    validate_documents(documents)
    print_document_loading_report(discovered_files, documents)
    print_cleaned_preview(documents[0])

    chunks = build_chunks(documents)
    warnings = validate_chunks(chunks)
    statistics = chunk_statistics(documents, chunks)
    print_summary(statistics, warnings)

    samples = select_representative_chunks(chunks)
    if len(samples) != 5:
        raise ValueError(f"Expected five representative chunks but found {len(samples)}.")
    print_sample_chunks(samples)


if __name__ == "__main__":
    main()
