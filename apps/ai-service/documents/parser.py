from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document

SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf", ".docx", ".html", ".htm", ".csv", ".json", ".xlsx"}


@dataclass(slots=True)
class ParsedDocument:
    documents: list[Document]
    parser_version: str = "parser-v2"


class DocumentParser:
    """Parse supported files into LangChain Documents with source metadata."""

    def parse_bytes(self, data: bytes, *, file_name: str, mime_type: str | None = None) -> ParsedDocument:
        suffix = Path(file_name).suffix.casefold()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported document type: {suffix or 'unknown'}")
        if suffix == ".pdf":
            return self._pdf(data, file_name)
        if suffix == ".docx":
            return self._docx(data, file_name)
        if suffix in {".xlsx"}:
            return self._xlsx(data, file_name)
        if suffix in {".csv"}:
            return self._csv(data, file_name)
        if suffix == ".json":
            text = data.decode("utf-8", errors="replace")
        elif suffix in {".html", ".htm"}:
            text = self._html(data)
        else:
            text = data.decode("utf-8-sig", errors="replace")
        return ParsedDocument([Document(page_content=self._clean(text), metadata={"source": file_name, "page": 1})])

    def _pdf(self, data: bytes, file_name: str) -> ParsedDocument:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF parsing requires pypdf") from exc
        pages: list[Document] = []
        for page_number, page in enumerate(PdfReader(io.BytesIO(data)).pages, start=1):
            text = self._clean(page.extract_text() or "")
            if text:
                pages.append(Document(page_content=text, metadata={"source": file_name, "page": page_number}))
        return ParsedDocument(pages)

    def _docx(self, data: bytes, file_name: str) -> ParsedDocument:
        try:
            from docx import Document as DocxDocument
        except ImportError as exc:
            raise RuntimeError("DOCX parsing requires python-docx") from exc
        document = DocxDocument(io.BytesIO(data))
        paragraphs: list[str] = []
        for paragraph in document.paragraphs:
            value = paragraph.text.strip()
            if not value:
                paragraphs.append("")
                continue
            style_name = str(getattr(paragraph.style, "name", "") or "")
            heading = re.search(r"(\d+)", style_name) if "heading" in style_name.casefold() else None
            prefix = "#" * min(int(heading.group(1)), 6) + " " if heading else ""
            paragraphs.append(prefix + value)
        text = "\n".join(paragraphs)
        return ParsedDocument([Document(page_content=self._clean(text), metadata={"source": file_name, "page": 1})])

    def _xlsx(self, data: bytes, file_name: str) -> ParsedDocument:
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise RuntimeError("XLSX parsing requires openpyxl") from exc
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        documents: list[Document] = []
        for sheet in workbook.worksheets:
            rows = ["\t".join("" if value is None else str(value) for value in row) for row in sheet.iter_rows(values_only=True)]
            text = self._clean("\n".join(rows))
            if text:
                documents.append(Document(page_content=text, metadata={"source": file_name, "sheet": sheet.title, "page": 1}))
        return ParsedDocument(documents)

    def _csv(self, data: bytes, file_name: str) -> ParsedDocument:
        rows = csv.reader(io.StringIO(data.decode("utf-8-sig", errors="replace")))
        text = "\n".join("\t".join(row) for row in rows)
        return ParsedDocument([Document(page_content=self._clean(text), metadata={"source": file_name, "page": 1})])

    def _html(self, data: bytes) -> str:
        try:
            from bs4 import BeautifulSoup
            return BeautifulSoup(data, "html.parser").get_text("\n")
        except ImportError:
            return re.sub(r"<[^>]+>", " ", data.decode("utf-8", errors="replace"))

    def _clean(self, text: str) -> str:
        text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()
