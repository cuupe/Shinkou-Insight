from __future__ import annotations

import csv
import io
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.documents import Document


# The suffix is intentionally the source of truth. MIME types are frequently
# missing or incorrect for files uploaded from browsers and should not be
# enough to make a binary parser run on arbitrary bytes.
SUPPORTED_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".pdf", ".doc", ".docx", ".html", ".htm",
    ".csv", ".json", ".xlsx", ".xls", ".pptx", ".ppt", ".odt", ".ods",
    ".odp", ".rtf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
    ".tif", ".tiff", ".svg", ".mp3", ".wav", ".m4a", ".ogg", ".aac",
    ".flac", ".opus", ".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".svg"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac", ".opus"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}
OFFICE_CONVERSION_EXTENSIONS = {".doc", ".xls", ".ppt", ".odt", ".ods", ".odp", ".rtf"}


@dataclass(slots=True)
class ParsedDocument:
    documents: list[Document]
    parser_version: str = "parser-v3-local-media"
    warnings: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n\n".join(document.page_content for document in self.documents if document.page_content).strip()


@lru_cache(maxsize=2)
def _load_whisper_model(model_name: str, device: str, compute_type: str) -> Any:
    from faster_whisper import WhisperModel

    return WhisperModel(model_name, device=device, compute_type=compute_type)


class DocumentParser:
    """Convert local files into searchable text and structured page metadata.

    Heavy operations are lazy and optional at import time. The Docker image
    installs the command line tools and Python packages; local development can
    still index text documents when one of the optional tools is unavailable.
    """

    def __init__(
        self,
        *,
        ocr_enabled: bool = True,
        ocr_languages: str = "chi_sim+eng",
        pdf_dpi: int = 180,
        max_ocr_pages: int = 100,
        max_video_frames: int = 8,
        whisper_model: str = "base",
        whisper_device: str = "cpu",
        whisper_compute_type: str = "int8",
        external_timeout_seconds: float = 120,
    ) -> None:
        self.ocr_enabled = ocr_enabled
        self.ocr_languages = ocr_languages
        self.pdf_dpi = max(72, min(pdf_dpi, 400))
        self.max_ocr_pages = max(1, min(max_ocr_pages, 500))
        self.max_video_frames = max(0, min(max_video_frames, 32))
        self.whisper_model = whisper_model
        self.whisper_device = whisper_device
        self.whisper_compute_type = whisper_compute_type
        self.external_timeout_seconds = max(5, min(external_timeout_seconds, 900))

    def parse_bytes(self, data: bytes, *, file_name: str, mime_type: str | None = None) -> ParsedDocument:
        return self.analyze_bytes(data, file_name=file_name, mime_type=mime_type)

    def analyze_bytes(self, data: bytes, *, file_name: str, mime_type: str | None = None) -> ParsedDocument:
        suffix = Path(file_name).suffix.casefold()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported document type: {suffix or 'unknown'}")
        if suffix == ".pdf":
            return self._pdf(data, file_name)
        if suffix in OFFICE_CONVERSION_EXTENSIONS:
            return self._office(data, file_name)
        if suffix == ".docx":
            return self._docx(data, file_name)
        if suffix == ".pptx":
            return self._pptx(data, file_name)
        if suffix == ".xlsx":
            return self._xlsx(data, file_name)
        if suffix == ".csv":
            return self._csv(data, file_name)
        if suffix in IMAGE_EXTENSIONS:
            return self._image(data, file_name)
        if suffix in AUDIO_EXTENSIONS | VIDEO_EXTENSIONS:
            kind = "video" if suffix in VIDEO_EXTENSIONS else "audio"
            return self._media(data, file_name, kind=kind)
        if suffix == ".json":
            text = data.decode("utf-8", errors="replace")
        elif suffix in {".html", ".htm"}:
            text = self._html(data)
        else:
            text = data.decode("utf-8-sig", errors="replace")
        return ParsedDocument([self._document(self._clean(text), file_name=file_name)], metadata={"kind": "text"})

    def _pdf(self, data: bytes, file_name: str) -> ParsedDocument:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF parsing requires pypdf") from exc

        reader = PdfReader(io.BytesIO(data))
        extracted = [self._clean(page.extract_text() or "") for page in reader.pages]
        warnings: list[str] = []
        tools = ["pypdf"]
        missing_pages = [index + 1 for index, text in enumerate(extracted) if not text]
        ocr_pages = missing_pages[: self.max_ocr_pages] if self.ocr_enabled else []
        if len(missing_pages) > len(ocr_pages):
            warnings.append(f"PDF 有 {len(missing_pages)} 个页面未提取到文本，仅 OCR 前 {len(ocr_pages)} 页")

        for page_number in ocr_pages:
            image = self._render_pdf_page(data, file_name, page_number)
            if not image:
                warnings.append(f"第 {page_number} 页无法渲染，未完成 OCR")
                continue
            text, ocr_warning = self._ocr_image(image, f"{Path(file_name).stem}-page-{page_number}.png")
            if text:
                extracted[page_number - 1] = text
                if "tesseract" not in tools:
                    tools.append("tesseract")
            if ocr_warning:
                warnings.append(ocr_warning)

        documents = [
            self._document(text, file_name=file_name, page=page_number)
            for page_number, text in enumerate(extracted, start=1)
            if text
        ]
        if missing_pages and not documents:
            warnings.append("PDF 未提取到可索引文本；如果是扫描件，请安装 Tesseract 与 Poppler")
        return ParsedDocument(
            documents,
            warnings=self._unique(warnings),
            tools=tools,
            metadata={
                "kind": "pdf",
                "pageCount": len(reader.pages),
                "ocrPageCount": sum(1 for page in ocr_pages if extracted[page - 1]),
            },
        )

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

        for table_index, table in enumerate(document.tables, start=1):
            paragraphs.append(f"\n[表格 {table_index}]")
            for row in table.rows:
                paragraphs.append("\t".join(cell.text.strip() for cell in row.cells))

        for section in document.sections:
            for label, part in (("页眉", section.header), ("页脚", section.footer)):
                values = [paragraph.text.strip() for paragraph in part.paragraphs if paragraph.text.strip()]
                if values:
                    paragraphs.append(f"\n[{label}]\n" + "\n".join(values))

        tools = ["python-docx"]
        warnings: list[str] = []
        seen_images: set[str] = set()
        for rel in document.part.rels.values():
            rel_type = str(getattr(rel, "reltype", "")).casefold()
            if "image" not in rel_type or str(rel.rId) in seen_images:
                continue
            seen_images.add(str(rel.rId))
            try:
                blob = rel.target_part.blob
            except Exception:
                continue
            text, warning = self._ocr_image(blob, f"{Path(file_name).stem}-{rel.rId}.png")
            if text:
                paragraphs.append(f"\n[嵌入图片 OCR]\n{text}")
                if "tesseract" not in tools:
                    tools.append("tesseract")
            if warning:
                warnings.append(warning)

        return ParsedDocument(
            [self._document(self._clean("\n".join(paragraphs)), file_name=file_name)],
            warnings=self._unique(warnings),
            tools=tools,
            metadata={"kind": "docx", "tableCount": len(document.tables), "embeddedImageCount": len(seen_images)},
        )

    def _pptx(self, data: bytes, file_name: str) -> ParsedDocument:
        try:
            from pptx import Presentation
        except ImportError as exc:
            raise RuntimeError("PPTX parsing requires python-pptx") from exc

        presentation = Presentation(io.BytesIO(data))
        documents: list[Document] = []
        tools = ["python-pptx"]
        warnings: list[str] = []
        for slide_number, slide in enumerate(presentation.slides, start=1):
            parts: list[str] = []
            image_count = 0
            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False):
                    value = shape.text.strip()
                    if value:
                        parts.append(value)
                if getattr(shape, "has_table", False):
                    for row in shape.table.rows:
                        parts.append("\t".join(cell.text.strip() for cell in row.cells))
                if getattr(shape, "shape_type", None) == 13:  # MSO_SHAPE_TYPE.PICTURE
                    image_count += 1
                    text, warning = self._ocr_image(shape.image.blob, f"{Path(file_name).stem}-slide-{slide_number}-{image_count}.png")
                    if text:
                        parts.append(f"[幻灯片图片 OCR]\n{text}")
                        if "tesseract" not in tools:
                            tools.append("tesseract")
                    if warning:
                        warnings.append(warning)
            text = self._clean("\n".join(parts))
            if text:
                documents.append(self._document(text, file_name=file_name, page=slide_number, section=f"Slide {slide_number}"))
        return ParsedDocument(
            documents,
            warnings=self._unique(warnings),
            tools=tools,
            metadata={"kind": "pptx", "slideCount": len(presentation.slides)},
        )

    def _xlsx(self, data: bytes, file_name: str) -> ParsedDocument:
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise RuntimeError("XLSX parsing requires openpyxl") from exc

        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        documents: list[Document] = []
        for sheet in workbook.worksheets:
            rows = [_join(row) for row in sheet.iter_rows(values_only=True)]
            text = self._clean("\n".join(rows))
            if text:
                documents.append(self._document(text, file_name=file_name, page=1, section=sheet.title, sheet=sheet.title))
        return ParsedDocument(documents, tools=["openpyxl"], metadata={"kind": "xlsx", "sheetCount": len(workbook.worksheets)})

    def _csv(self, data: bytes, file_name: str) -> ParsedDocument:
        rows = csv.reader(io.StringIO(data.decode("utf-8-sig", errors="replace")))
        text = "\n".join("\t".join(row) for row in rows)
        return ParsedDocument([self._document(self._clean(text), file_name=file_name)], metadata={"kind": "csv"})

    def _image(self, data: bytes, file_name: str) -> ParsedDocument:
        if Path(file_name).suffix.casefold() == ".svg":
            text = self._clean(re.sub(r"<[^>]+>", " ", data.decode("utf-8", errors="replace")))
            return ParsedDocument([self._document(text, file_name=file_name)], tools=["svg-text"], metadata={"kind": "image", "ocr": False})
        text, warning = self._ocr_image(data, file_name)
        warnings = [warning] if warning else []
        if not text:
            warnings.append("图片未识别到文字；当前本地分析链路提供 OCR，不包含通用视觉描述")
            text = f"[图片文件]\n文件名：{file_name}\n未识别到可索引文字。"
        return ParsedDocument(
            [self._document(text, file_name=file_name)],
            warnings=self._unique(warnings),
            tools=["tesseract"] if not warning else [],
            metadata={"kind": "image", "ocr": "未识别到可索引文字" not in text},
        )

    def _media(self, data: bytes, file_name: str, *, kind: str) -> ParsedDocument:
        metadata = {"kind": kind}
        warnings: list[str] = []
        tools: list[str] = []
        probe = self._probe_media(data, file_name)
        if probe:
            metadata.update(probe)
            tools.append("ffprobe")
        transcript, warning = self._transcribe(data, file_name, language=None)
        if transcript:
            tools.append("faster-whisper")
        if warning:
            warnings.append(warning)
        if kind == "video" and self.max_video_frames:
            for frame_number, frame in enumerate(self._render_video_frames(data, file_name), start=1):
                frame_text, frame_warning = self._ocr_image(frame, f"{Path(file_name).stem}-frame-{frame_number}.png")
                if frame_text:
                    timestamp = _timestamp((frame_number - 1) * 10)
                    transcript = f"{transcript}\n\n[视频画面 OCR · {timestamp}]\n{frame_text}" if transcript else f"[视频画面 OCR · {timestamp}]\n{frame_text}"
                    if "tesseract" not in tools:
                        tools.append("tesseract")
                if frame_warning:
                    warnings.append(frame_warning)
        if not transcript:
            label = "视频" if kind == "video" else "音频"
            duration = f"\n时长：{metadata['durationSeconds']} 秒" if metadata.get("durationSeconds") is not None else ""
            transcript = f"[{label}文件]\n文件名：{file_name}{duration}\n未取得语音转写内容。"
        return ParsedDocument(
            [self._document(transcript, file_name=file_name)],
            warnings=self._unique(warnings),
            tools=self._unique(tools),
            metadata=metadata,
        )

    def _office(self, data: bytes, file_name: str) -> ParsedDocument:
        command = self._find_command("soffice", "libreoffice")
        if not command:
            return ParsedDocument(
                [self._document(f"[Office 文件]\n文件名：{file_name}\n未安装 LibreOffice，无法解析该旧版或开放文档格式。", file_name=file_name)],
                warnings=["Office 格式需要 LibreOffice headless 转换工具"],
                metadata={"kind": "office", "converted": False},
            )
        with tempfile.TemporaryDirectory(prefix="shinkou-office-") as directory:
            source = Path(directory) / Path(file_name).name
            output = Path(directory) / "out"
            profile = Path(directory) / "profile"
            output.mkdir()
            profile.mkdir()
            source.write_bytes(data)
            # LibreOffice can otherwise attach to an existing desktop
            # process and leave a headless conversion waiting on its profile.
            # Use an isolated temporary profile for deterministic server-side
            # conversions and disable first-run/lock UI behavior.
            result = self._run_external([
                command,
                "--headless",
                "--nologo",
                "--nodefault",
                "--nofirststartwizard",
                "--nolockcheck",
                "--norestore",
                f"-env:UserInstallation={profile.as_uri()}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output),
                str(source),
            ])
            pdf = output / f"{source.stem}.pdf"
            if result is None or not pdf.is_file():
                detail = (result.stderr.strip() if result else "转换工具执行失败")[:300]
                return ParsedDocument(
                    [self._document(f"[Office 文件]\n文件名：{file_name}\n转换失败：{detail}", file_name=file_name)],
                    warnings=["Office 文件未能转换为 PDF"],
                    tools=["libreoffice"],
                    metadata={"kind": "office", "converted": False},
                )
            parsed = self._pdf(pdf.read_bytes(), file_name)
            parsed.tools = self._unique(["libreoffice", *parsed.tools])
            parsed.metadata.update({"kind": "office", "converted": True, "originalExtension": source.suffix.casefold()})
            return parsed

    def _render_pdf_page(self, data: bytes, file_name: str, page_number: int) -> bytes | None:
        command = self._find_command("pdftoppm")
        if not command:
            return None
        with tempfile.TemporaryDirectory(prefix="shinkou-pdf-") as directory:
            source = Path(directory) / Path(file_name).with_suffix(".pdf").name
            prefix = Path(directory) / "page"
            source.write_bytes(data)
            result = self._run_external([
                command, "-png", "-r", str(self.pdf_dpi), "-f", str(page_number), "-l", str(page_number), str(source), str(prefix)
            ])
            if result is None or result.returncode != 0:
                return None
            images = sorted(Path(directory).glob("page-*.png"))
            return images[0].read_bytes() if images else None

    def _ocr_image(self, data: bytes, file_name: str) -> tuple[str, str | None]:
        if not self.ocr_enabled:
            return "", "OCR 已被配置关闭"
        command = self._find_command("tesseract")
        if not command:
            return "", "OCR 工具 Tesseract 未安装，扫描版 PDF/图片无法提取文字"
        with tempfile.TemporaryDirectory(prefix="shinkou-ocr-") as directory:
            source = Path(directory) / Path(file_name).name
            source.write_bytes(data)
            input_path = self._normalize_image(source, directory)
            language = self._ocr_language(command)
            result = self._run_external([command, str(input_path), "stdout", "--psm", "3", "-l", language])
            if result is None or result.returncode != 0:
                detail = result.stderr.strip()[:240] if result else "Tesseract 执行失败"
                return "", f"OCR 执行失败：{detail}"
            return self._clean(result.stdout), None

    def _normalize_image(self, source: Path, directory: str) -> Path:
        try:
            from PIL import Image

            target = Path(directory) / "normalized.png"
            with Image.open(source) as image:
                image.convert("RGB").save(target, format="PNG")
            return target
        except Exception:
            return source

    def _ocr_language(self, command: str) -> str:
        requested = [item.strip() for item in self.ocr_languages.split("+") if item.strip()]
        result = self._run_external([command, "--list-langs"])
        available = set((result.stdout if result else "").split())
        selected = [item for item in requested if not available or item in available]
        if selected:
            return "+".join(selected)
        if "eng" in available:
            return "eng"
        return requested[0] if requested else "eng"

    def _transcribe(self, data: bytes, file_name: str, language: str | None) -> tuple[str, str | None]:
        try:
            model = _load_whisper_model(self.whisper_model, self.whisper_device, self.whisper_compute_type)
        except ImportError:
            return "", "语音转写未安装 faster-whisper；音频/视频仍可保存，但无法提取语音内容"
        except Exception as exc:
            return "", f"语音转写模型加载失败：{str(exc)[:240]}"

        with tempfile.TemporaryDirectory(prefix="shinkou-whisper-") as directory:
            source = Path(directory) / Path(file_name).name
            source.write_bytes(data)
            options: dict[str, Any] = {"vad_filter": True, "beam_size": 1}
            if language:
                options["language"] = language.split("-", 1)[0]
            try:
                segments, info = model.transcribe(str(source), **options)
                lines: list[str] = []
                for segment in segments:
                    text = self._clean(getattr(segment, "text", ""))
                    if not text:
                        continue
                    lines.append(f"[{_timestamp(getattr(segment, 'start', 0))} - {_timestamp(getattr(segment, 'end', 0))}] {text}")
                if not lines:
                    return "", "语音转写完成，但未识别到有效语音"
                detected = getattr(info, "language", None)
                prefix = f"检测语言：{detected}\n" if detected else ""
                return prefix + "\n".join(lines), None
            except Exception as exc:
                return "", f"语音转写失败：{str(exc)[:240]}"

    def _probe_media(self, data: bytes, file_name: str) -> dict[str, Any] | None:
        command = self._find_command("ffprobe")
        if not command:
            return None
        with tempfile.TemporaryDirectory(prefix="shinkou-media-") as directory:
            source = Path(directory) / Path(file_name).name
            source.write_bytes(data)
            result = self._run_external([
                command, "-v", "error", "-show_entries", "format=duration,format_name", "-of", "json", str(source)
            ])
            if result is None or result.returncode != 0:
                return None
            try:
                payload = json.loads(result.stdout)
                format_info = payload.get("format", {})
                duration = float(format_info.get("duration")) if format_info.get("duration") else None
                return {"durationSeconds": round(duration, 3) if duration is not None else None, "format": format_info.get("format_name")}
            except (TypeError, ValueError, json.JSONDecodeError):
                return None

    def _render_video_frames(self, data: bytes, file_name: str) -> list[bytes]:
        command = self._find_command("ffmpeg")
        if not command or not self.max_video_frames:
            return []
        with tempfile.TemporaryDirectory(prefix="shinkou-video-") as directory:
            source = Path(directory) / Path(file_name).name
            output = Path(directory) / "frame-%03d.png"
            source.write_bytes(data)
            result = self._run_external([
                command,
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(source),
                "-vf",
                "fps=1/10,scale=1600:-1",
                "-frames:v",
                str(self.max_video_frames),
                str(output),
            ])
            if result is None or result.returncode != 0:
                return []
            return [path.read_bytes() for path in sorted(Path(directory).glob("frame-*.png"))]

    def _html(self, data: bytes) -> str:
        try:
            from bs4 import BeautifulSoup

            return BeautifulSoup(data, "html.parser").get_text("\n")
        except ImportError:
            return re.sub(r"<[^>]+>", " ", data.decode("utf-8", errors="replace"))

    def _document(self, text: str, *, file_name: str, page: int = 1, section: str | None = None, **metadata: Any) -> Document:
        value: dict[str, Any] = {"source": file_name, "page": page}
        if section:
            value["section_title"] = section
        value.update(metadata)
        return Document(page_content=text, metadata=value)

    def _find_command(self, *names: str) -> str | None:
        for name in names:
            command = shutil.which(name)
            if command:
                return command
        return None

    def _run_external(self, command: list[str]) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.external_timeout_seconds,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return None

    def _clean(self, text: str) -> str:
        text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
        # Keep tabs because they delimit spreadsheet rows and Office tables.
        text = re.sub(r" +", " ", text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    def _unique(self, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value for value in values if value))


def _join(values: tuple[Any, ...]) -> str:
    return "\t".join("" if value is None else str(value) for value in values)


def _timestamp(value: Any) -> str:
    try:
        seconds = max(0.0, float(value))
    except (TypeError, ValueError):
        seconds = 0.0
    minutes, remainder = divmod(seconds, 60)
    return f"{int(minutes):02d}:{remainder:05.2f}"
