from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


FORMAT_META: dict[str, tuple[str, str]] = {
    "markdown": ("text/markdown", ".md"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
    "pdf": ("application/pdf", ".pdf"),
    "pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
}


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", str(value or "").strip(), flags=re.UNICODE)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-_")
    return (cleaned or "shinkou-report")[:100]


def _plain_inline(value: str) -> str:
    value = re.sub(r"!\[([^]]*)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"\[([^]]+)\]\(([^)]+)\)", r"\1 (\2)", value)
    value = re.sub(r"(`+|\*\*|__|\*|_)", "", value)
    return value.strip()


def _markdown_lines(markdown: str) -> list[str]:
    return [line.rstrip() for line in str(markdown or "").replace("\r\n", "\n").split("\n")]


def _normalise_markdown(markdown: str, sources: list[dict[str, Any]]) -> str:
    content = str(markdown or "").strip()
    if not sources:
        return content + ("\n" if content else "")
    source_lines = ["", "## 来源", ""]
    for item in sources[:30]:
        title = str(item.get("title") or item.get("name") or item.get("source") or "未命名来源").strip()
        source_id = str(item.get("id") or "").strip()
        url = str(item.get("url") or "").strip()
        label = f"[{title}]({url})" if url else title
        suffix = f"（{source_id}）" if source_id else ""
        source_lines.append(f"- {label}{suffix}")
    return (content + "\n" if content else "") + "\n".join(source_lines) + "\n"


def _set_run_font(run: Any, name: str = "Microsoft YaHei", size: int = 11, bold: bool = False, italic: bool = False) -> None:
    from docx.oxml.ns import qn
    from docx.shared import Pt

    run.font.name = name
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)


def _add_hyperlink(paragraph: Any, label: str, url: str) -> None:
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    part = paragraph.part
    relationship = part.relate_to(url, RT.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relationship)
    run = OxmlElement("w:r")
    properties = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "147d78")
    properties.append(color)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    properties.append(underline)
    run.append(properties)
    text = OxmlElement("w:t")
    text.text = label
    run.append(text)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def _add_markdown_runs(paragraph: Any, text: str) -> None:
    pattern = re.compile(r"(\[([^\]]+)\]\((https?://[^)]+)\)|\*\*([^*]+)\*\*|__([^_]+)__|`([^`]+)`)")
    cursor = 0
    for match in pattern.finditer(text):
        if match.start() > cursor:
            run = paragraph.add_run(text[cursor:match.start()])
            _set_run_font(run)
        if match.group(2) and match.group(3):
            _add_hyperlink(paragraph, match.group(2), match.group(3))
        else:
            run = paragraph.add_run(match.group(4) or match.group(5) or match.group(6) or "")
            _set_run_font(run, bold=bool(match.group(4) or match.group(5)))
        cursor = match.end()
    if cursor < len(text):
        run = paragraph.add_run(text[cursor:])
        _set_run_font(run)


def _write_docx(path: Path, markdown: str) -> None:
    from docx import Document
    from docx.enum.section import WD_SECTION
    from docx.enum.style import WD_STYLE_TYPE
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)
    styles = document.styles
    normal = styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal.font.size = Pt(10.5)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    for style_name, size, color in (("Title", 22, "174b4a"), ("Heading 1", 16, "147d78"), ("Heading 2", 13, "286a68"), ("Heading 3", 11, "286a68")):
        style = styles[style_name]
        style.font.name = "Microsoft YaHei"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    if "Quote" not in styles:
        styles.add_style("Quote", WD_STYLE_TYPE.PARAGRAPH)
    in_code = False
    for raw_line in _markdown_lines(markdown):
        line = raw_line.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            paragraph = document.add_paragraph(style="Quote")
            run = paragraph.add_run(raw_line)
            _set_run_font(run, name="Consolas", size=9)
            continue
        if not line:
            continue
        heading = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading:
            level = len(heading.group(1))
            paragraph = document.add_paragraph(style="Title" if level == 1 and not document.paragraphs else f"Heading {level}")
            _add_markdown_runs(paragraph, heading.group(2))
            continue
        if line.startswith(">"):
            paragraph = document.add_paragraph(style="Quote")
            _add_markdown_runs(paragraph, line[1:].strip())
            continue
        bullet = re.match(r"^(?:[-*+])\s+(.+)$", line)
        ordered = re.match(r"^\d+[.)]\s+(.+)$", line)
        if bullet or ordered:
            paragraph = document.add_paragraph(style="List Bullet" if bullet else "List Number")
            _add_markdown_runs(paragraph, (bullet or ordered).group(1))
            continue
        paragraph = document.add_paragraph()
        _add_markdown_runs(paragraph, line)
    document.save(path)


def _add_slide_text(slide: Any, title: str, body: list[str], *, title_size: int = 30, body_size: int = 18) -> None:
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_AUTO_SIZE
    from pptx.util import Inches, Pt

    title_box = slide.shapes.add_textbox(Inches(0.7), Inches(0.45), Inches(12), Inches(0.75))
    title_frame = title_box.text_frame
    title_frame.clear()
    title_frame.word_wrap = True
    title_paragraph = title_frame.paragraphs[0]
    title_paragraph.alignment = PP_ALIGN.LEFT
    run = title_paragraph.add_run()
    run.text = title
    run.font.name = "Microsoft YaHei"
    run.font.size = Pt(title_size)
    run.font.bold = True
    run.font.color.rgb = RGBColor(24, 91, 88)
    body_box = slide.shapes.add_textbox(Inches(0.85), Inches(1.45), Inches(11.7), Inches(5.45))
    frame = body_box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    for index, item in enumerate(body[:12]):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = _plain_inline(item)
        paragraph.level = 0
        paragraph.space_after = Pt(10)
        for run in paragraph.runs:
            run.font.name = "Microsoft YaHei"
            run.font.size = Pt(body_size)
            run.font.color.rgb = RGBColor(46, 59, 67)


def _write_pptx(path: Path, title: str, markdown: str, sources: list[dict[str, Any]]) -> None:
    from pptx import Presentation
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches, Pt

    presentation = Presentation()
    presentation.slide_width = Inches(13.333)
    presentation.slide_height = Inches(7.5)
    blank = presentation.slide_layouts[6]
    cover = presentation.slides.add_slide(blank)
    _add_slide_text(cover, title, ["研究整理与行动摘要"], title_size=36, body_size=22)
    sections: list[tuple[str, list[str]]] = []
    current_title = "摘要"
    current_body: list[str] = []
    for raw in _markdown_lines(markdown):
        line = raw.strip()
        heading = re.match(r"^#{1,3}\s+(.+)$", line)
        if heading:
            if current_body:
                sections.append((current_title, current_body))
            current_title = _plain_inline(heading.group(1))
            current_body = []
        elif line:
            current_body.append(line)
    if current_body:
        sections.append((current_title, current_body))
    for section_title, body in sections[:12]:
        slide = presentation.slides.add_slide(blank)
        _add_slide_text(slide, section_title, body)
    if sources:
        slide = presentation.slides.add_slide(blank)
        source_lines = []
        for item in sources[:20]:
            label = str(item.get("title") or item.get("name") or item.get("source") or "未命名来源")
            url = str(item.get("url") or "").strip()
            source_lines.append(f"• {label}{f' — {url}' if url else ''}")
        _add_slide_text(slide, "来源", source_lines, title_size=26, body_size=14)
    presentation.save(path)


def _convert_to_pdf(docx_path: Path, output_dir: Path) -> Path:
    command = shutil.which("soffice") or shutil.which("libreoffice")
    if not command:
        raise RuntimeError("未找到 LibreOffice/soffice，无法把 DOCX 转换为 PDF")
    profile_dir = output_dir / ".libreoffice-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    profile_uri = profile_dir.as_uri()
    completed = subprocess.run(
        [
            command,
            "--headless",
            "--norestore",
            "--nodefault",
            "--nolockcheck",
            "--nofirststartwizard",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(docx_path),
        ],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    pdf_path = output_dir / f"{docx_path.stem}.pdf"
    if completed.returncode != 0 or not pdf_path.exists():
        detail = (completed.stderr or completed.stdout or "转换没有产生 PDF").strip()
        raise RuntimeError(detail[-500:])
    return pdf_path


class DocumentGenerationTool:
    """Generate a consistent document bundle from the final Markdown answer."""

    def generate(self, **input_data: Any) -> dict[str, Any]:
        title = str(input_data.get("title") or "Shinkou 研究报告").strip()[:200]
        markdown = str(input_data.get("markdown") or "").strip()
        formats = [str(item).lower().strip() for item in input_data.get("formats", [])]
        formats = list(dict.fromkeys(item for item in formats if item in FORMAT_META))
        sources = input_data.get("sources") if isinstance(input_data.get("sources"), list) else []
        output_dir = Path(str(input_data.get("output_dir") or "")).expanduser().resolve()
        if not markdown:
            raise ValueError("markdown 不能为空")
        if not formats:
            raise ValueError("formats 至少需要包含一种输出格式")
        output_dir.mkdir(parents=True, exist_ok=True)
        document_markdown = _normalise_markdown(markdown, sources)
        base_name = _slug(title)
        artifacts: list[dict[str, Any]] = []
        warnings: list[str] = []
        docx_path: Path | None = None

        if "markdown" in formats:
            path = output_dir / f"{base_name}.md"
            path.write_text(document_markdown, encoding="utf-8")
            artifacts.append(self._artifact(path, "markdown"))
        if "docx" in formats or "pdf" in formats:
            docx_path = output_dir / f"{base_name}.docx"
            _write_docx(docx_path, document_markdown)
            if "docx" in formats:
                artifacts.append(self._artifact(docx_path, "docx"))
        if "pdf" in formats and docx_path is not None:
            try:
                artifacts.append(self._artifact(_convert_to_pdf(docx_path, output_dir), "pdf"))
            except Exception as exc:
                warnings.append(f"PDF 生成失败：{str(exc)[:300]}")
        if "pptx" in formats:
            path = output_dir / f"{base_name}.pptx"
            _write_pptx(path, title, markdown, sources)
            artifacts.append(self._artifact(path, "pptx"))
        return {"artifacts": artifacts, "warnings": warnings}

    @staticmethod
    def _artifact(path: Path, format_name: str) -> dict[str, Any]:
        mime_type, _ = FORMAT_META[format_name]
        return {
            "fileName": path.name,
            "mimeType": mime_type,
            "fileSize": path.stat().st_size,
            "path": str(path),
            "format": format_name,
        }
