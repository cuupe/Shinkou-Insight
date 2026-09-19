from pathlib import Path

from tools.document_generation import DocumentGenerationTool


def test_document_generation_bundle_writes_markdown_docx_and_pptx(tmp_path: Path) -> None:
    result = DocumentGenerationTool().generate(
        title="图形学进展",
        markdown="# 图形学进展\n\n## 重点\n\n- 实时渲染\n- 数字人",
        formats=["markdown", "docx", "pptx"],
        output_dir=str(tmp_path),
        sources=[{"id": "W1", "title": "官方来源", "url": "https://example.com"}],
    )

    names = {item["fileName"] for item in result["artifacts"]}
    assert names == {"图形学进展.md", "图形学进展.docx", "图形学进展.pptx"}
    assert "[官方来源](https://example.com)" in (tmp_path / "图形学进展.md").read_text(encoding="utf-8")
    assert all((tmp_path / name).stat().st_size > 0 for name in names)
    assert result["warnings"] == []
