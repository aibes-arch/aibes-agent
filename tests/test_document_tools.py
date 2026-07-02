import importlib.util
import json
from pathlib import Path

import pytest

from aibes_agent.tools.base import ToolContext
from aibes_agent.tools.documents import MarkdownMergeTool, PdfExtractTool


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(cwd=str(tmp_path))


@pytest.mark.asyncio
async def test_markdown_merge(tmp_path, ctx):
    (tmp_path / "a.md").write_text("# A\n\ncontent a\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# B\n\ncontent b\n", encoding="utf-8")

    tool = MarkdownMergeTool()
    result = await tool.call(tool.input_model(paths=[str(tmp_path / "*.md")]), ctx)
    assert result.success
    assert "content a" in result.content
    assert "content b" in result.content


@pytest.mark.asyncio
async def test_markdown_merge_with_toc(tmp_path, ctx):
    (tmp_path / "a.md").write_text("# Title A\n\ncontent a\n", encoding="utf-8")

    tool = MarkdownMergeTool()
    result = await tool.call(
        tool.input_model(paths=[str(tmp_path / "a.md")], add_toc=True),
        ctx,
    )
    assert result.success
    assert "Table of Contents" in result.content
    assert "Title A" in result.content


@pytest.mark.asyncio
async def test_markdown_merge_write_output(tmp_path, ctx):
    (tmp_path / "a.md").write_text("hello", encoding="utf-8")
    output = tmp_path / "merged.md"

    tool = MarkdownMergeTool()
    result = await tool.call(
        tool.input_model(paths=[str(tmp_path / "a.md")], output_path=str(output)),
        ctx,
    )
    assert result.success
    assert output.exists()
    assert "hello" in output.read_text(encoding="utf-8")


@pytest.mark.skipif(
    importlib.util.find_spec("fitz") is None,
    reason="pymupdf not installed",
)
@pytest.mark.asyncio
async def test_pdf_extract_missing_file(tmp_path, ctx):
    tool = PdfExtractTool()
    result = await tool.call(tool.input_model(file_path=str(tmp_path / "no.pdf")), ctx)
    assert not result.success


@pytest.mark.skipif(
    importlib.util.find_spec("fitz") is None,
    reason="pymupdf not installed",
)
@pytest.mark.asyncio
async def test_pdf_extract_metadata(tmp_path, ctx):
    import fitz  # type: ignore

    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.set_metadata({"title": "Test PDF", "author": "Tester"})
    doc.save(str(pdf_path))
    doc.close()

    tool = PdfExtractTool()
    result = await tool.call(
        tool.input_model(file_path=str(pdf_path), include_metadata=True),
        ctx,
    )
    assert result.success
    assert result.metadata["metadata"].get("title") == "Test PDF"
    assert result.metadata["metadata"].get("author") == "Tester"
