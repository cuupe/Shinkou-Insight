from __future__ import annotations

import hashlib
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
    def __init__(self, chunk_size: int = 1200, chunk_overlap: int = 180):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap, separators=["\n## ", "\n### ", "\n\n", "\n", "。", "！", "？", ". ", " ", ""])

    def split(self, documents: list[Document]) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        index = 0
        for document in documents:
            split_documents = self.splitter.split_documents([document])
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

    def _section(self, metadata: dict, content: str) -> str | None:
        if metadata.get("section_title"):
            return str(metadata["section_title"])
        first_line = content.splitlines()[0].strip() if content else ""
        return first_line[2:].strip() if first_line.startswith("#") else None
