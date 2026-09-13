from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass(slots=True)
class DocumentChunk:
    content: str
    chunk_index: int
    page_number: int | None
    section_title: str | None
    start_offset: int
    end_offset: int
    checksum: str
    metadata: dict


class DocumentChunker:
    def __init__(self, chunk_size: int = 1200, chunk_overlap: int = 180, strategy: str = "natural", preserve_sections: bool = True):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        if strategy not in {"natural", "paragraph", "fixed"}:
            raise ValueError("unsupported chunking strategy")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy
        self.preserve_sections = preserve_sections
        separators = {
            "natural": ["\n\n", "\n", "。", "！", "？", "；", ";", ". ", " ", ""],
            "paragraph": ["\n\n", "\n", ""],
            "fixed": [""],
        }[strategy]
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
        )

    @classmethod
    def from_config(cls, config: dict | None) -> "DocumentChunker":
        config = config or {}
        return cls(
            chunk_size=int(config.get("chunk_size", config.get("chunkSize", 1200))),
            chunk_overlap=int(config.get("chunk_overlap", config.get("chunkOverlap", 180))),
            strategy=str(config.get("strategy", "natural")),
            preserve_sections=bool(config.get("preserve_sections", config.get("preserveSections", True))),
        )

    def split(self, documents: list[Document]) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        index = 0
        for document in documents:
            section_documents = self._section_documents(document) if self.preserve_sections else [document]
            split_documents = self.splitter.split_documents(section_documents)
            for split in split_documents:
                content = split.page_content.strip()
                if not content:
                    continue
                # Offsets are relative to the source Document. They remain
                # useful for quote validation even when overlap is present.
                start = document.page_content.find(content)
                start = max(start, 0)
                end = start + len(content)
                chunks.append(DocumentChunk(content=content, chunk_index=index, page_number=split.metadata.get("page"), section_title=self._section(split.metadata, content), start_offset=start, end_offset=end, checksum=hashlib.sha256(content.encode("utf-8")).hexdigest(), metadata=dict(split.metadata)))
                index += 1
        return chunks

    def _section_documents(self, document: Document) -> list[Document]:
        """Keep Markdown-style sections together before applying size limits."""

        lines = document.page_content.splitlines()
        if not any(re.match(r"^\s{0,3}#{1,6}\s+\S", line) for line in lines):
            return [document]

        sections: list[Document] = []
        current_lines: list[str] = []
        current_title = str(document.metadata.get("section_title") or "").strip() or None

        def flush() -> None:
            nonlocal current_lines
            content = "\n".join(current_lines).strip()
            if content:
                metadata = dict(document.metadata)
                if current_title:
                    metadata["section_title"] = current_title
                sections.append(Document(page_content=content, metadata=metadata))
            current_lines = []

        for line in lines:
            heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
            if heading:
                flush()
                current_title = heading.group(1).strip()
            current_lines.append(line.rstrip())
        flush()
        return sections or [document]

    def _section(self, metadata: dict, content: str) -> str | None:
        if metadata.get("section_title"):
            return str(metadata["section_title"])
        first_line = content.splitlines()[0].strip() if content else ""
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", first_line)
        return heading.group(1).strip() if heading else None
