from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

DEFAULT_TARGET_CHUNK_SIZE = 800
DEFAULT_OVERLAP = 150


def normalize_text(raw_text: str) -> str:
    """Normalize whitespace while preserving paragraph breaks."""
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\t", " ")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = text.strip()
    return text


def split_into_paragraphs(text: str) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]
    return paragraphs


def find_sentence_boundary(text: str, start: int, end: int) -> int | None:
    """Find a sentence-ending boundary near the end of a chunk when one exists."""
    boundaries = [
        text.rfind(". ", start, end),
        text.rfind("! ", start, end),
        text.rfind("? ", start, end),
        text.rfind("\n", start, end),
    ]
    valid = [index for index in boundaries if index > start + 80]
    if not valid:
        return None
    return max(valid) + 1


def chunk_paragraph(paragraph: str, target_size: int = DEFAULT_TARGET_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP) -> list[str]:
    """Chunk a paragraph using a sliding-window approach with overlap."""
    if not paragraph.strip():
        return []
    if len(paragraph) <= target_size:
        return [paragraph.strip()]

    chunks: list[str] = []
    start = 0

    while start < len(paragraph):
        end = min(start + target_size, len(paragraph))
        boundary = None

        if end < len(paragraph):
            boundary = find_sentence_boundary(paragraph, start, end)
            if boundary is not None and boundary > start + max(80, target_size // 2):
                end = boundary

        chunk = paragraph[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(paragraph):
            break

        next_start = max(start + target_size - overlap, end - overlap)
        if next_start <= start:
            next_start = start + max(60, target_size // 3)
        start = next_start

    return [chunk for chunk in chunks if chunk]


def build_document_chunks(text: str, target_size: int = DEFAULT_TARGET_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP) -> list[str]:
    """Combine paragraph-level chunks into a final chunk list."""
    paragraphs = split_into_paragraphs(text)
    if not paragraphs:
        return []

    chunks: list[str] = []
    current_group: list[str] = []
    current_length = 0

    for paragraph in paragraphs:
        paragraph_len = len(paragraph)
        if paragraph_len <= target_size:
            if current_group and current_length + len(paragraph) + 1 > target_size:
                chunks.extend(chunk_paragraph(" ".join(current_group), target_size, overlap))
                current_group = []
                current_length = 0
            current_group.append(paragraph)
            current_length = len(" ".join(current_group))
        else:
            if current_group:
                chunks.extend(chunk_paragraph(" ".join(current_group), target_size, overlap))
                current_group = []
                current_length = 0
            chunks.extend(chunk_paragraph(paragraph, target_size, overlap))

    if current_group:
        chunks.extend(chunk_paragraph(" ".join(current_group), target_size, overlap))

    return [chunk.strip() for chunk in chunks if chunk and chunk.strip()]


def load_chunks(doc_dir: str | Path = "documents", target_size: int = DEFAULT_TARGET_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP) -> list[dict[str, Any]]:
    """Load every text file in the documents directory and return chunk metadata."""
    folder = Path(doc_dir)
    if not folder.exists():
        return []

    all_chunks: list[dict[str, Any]] = []
    for document_path in sorted(folder.glob("*.txt")):
        if not document_path.is_file():
            continue

        raw_text = document_path.read_text(encoding="utf-8")
        cleaned_text = normalize_text(raw_text)
        document_chunks = build_document_chunks(cleaned_text, target_size=target_size, overlap=overlap)

        for chunk_index, chunk_text in enumerate(document_chunks):
            cleaned_chunk = " ".join(chunk_text.split())
            if not cleaned_chunk:
                continue
            all_chunks.append(
                {
                    "source": document_path.name,
                    "chunk_index": chunk_index,
                    "text": cleaned_chunk,
                }
            )

    return all_chunks


def main() -> None:
    chunks = load_chunks()
    document_paths = sorted(Path("documents").glob("*.txt"))
    print(f"Documents loaded: {len(document_paths)}")
    print(f"Total chunks generated: {len(chunks)}")

    if chunks:
        print("\nSample chunks:")
        sample_chunks = chunks[:5]
        for entry in sample_chunks:
            print(f"- source={entry['source']} | chunk_index={entry['chunk_index']}")
            print(entry["text"])
            print("-" * 60)
    else:
        print("No valid chunks were generated. Add .txt files to the documents/ directory and rerun this script.")


if __name__ == "__main__":
    main()
