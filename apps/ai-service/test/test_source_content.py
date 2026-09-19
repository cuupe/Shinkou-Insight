import httpx
import pytest
from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from models.schemas import Evidence
from tools.source_content import hydrate_web_evidence


def _pdf_bytes() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})
    })
    stream = DecodedStreamObject()
    stream.set_data(
        b"BT /F1 12 Tf 72 720 Td (3D Gaussian Splatting method enables real-time rendering of novel views and dynamic scene reconstruction for computer graphics research.) Tj ET"
    )
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.mark.asyncio
async def test_hydrate_web_evidence_uses_article_body_not_search_description():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                "<html><head><title>3D Gaussian Splatting paper</title></head><body>"
                "<nav>目录 首页 推荐文章</nav>"
                "<main><h1>3D Gaussian Splatting</h1>"
                "<p>This paper presents a 3D Gaussian Splatting method for real-time scene rendering and novel view synthesis.</p>"
                "<p>The method optimizes explicit Gaussian primitives and reports faster training and rendering than earlier neural representations.</p>"
                "</main><footer>相关链接 隐私政策</footer></body></html>"
            ),
            headers={"content-type": "text/html; charset=utf-8"},
            request=request,
        )

    candidate = Evidence(
        id="W1",
        chunk_id="web:1",
        content="3D Gaussian Splatting - search engine description",
        source_name="3D Gaussian Splatting paper",
        source_type="web",
        url="https://graphics.example.org/paper",
        content_kind="search_snippet",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await hydrate_web_evidence(client, [candidate], "3D Gaussian Splatting real-time rendering")

    assert len(results) == 1
    assert results[0].content_kind == "fulltext"
    assert "This paper presents" in results[0].content
    assert "search engine description" not in results[0].content


@pytest.mark.asyncio
async def test_hydrate_web_evidence_drops_issue_directory_pages():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                "<html><body><main><ul>"
                "<li><a href='/a'>2026 graphics research issue contents and article list</a></li>"
                "<li><a href='/b'>Recent neural rendering papers and publication index</a></li>"
                "<li><a href='/c'>Three dimensional vision and reconstruction directory</a></li>"
                "<li><a href='/d'>Computer graphics journal archive navigation</a></li>"
                "</ul></main></body></html>"
            ),
            headers={"content-type": "text/html"},
            request=request,
        )

    candidate = Evidence(
        id="W2",
        chunk_id="web:2",
        content="2026 graphics issue contents",
        source_name="2026 graphics issue contents",
        source_type="web",
        url="https://journal.example.org/issue/2026/7/",
        content_kind="search_snippet",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await hydrate_web_evidence(client, [candidate], "最新图形学研究进展")

    assert results == []


@pytest.mark.asyncio
async def test_hydrate_web_evidence_extracts_actual_pdf_page_text():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_pdf_bytes(),
            headers={"content-type": "application/pdf"},
            request=request,
        )

    candidate = Evidence(
        id="W3",
        chunk_id="web:3",
        content="3D Gaussian Splatting paper search result",
        source_name="3D Gaussian Splatting paper",
        source_type="web",
        url="https://graphics.example.org/paper.pdf",
        content_kind="search_snippet",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await hydrate_web_evidence(client, [candidate], "3D Gaussian Splatting rendering")

    assert len(results) == 1
    assert results[0].content_kind == "fulltext"
    assert results[0].page_number == 1
    assert "real-time rendering" in results[0].content
