"""Document processing domain tools for aibes-agent v0.4.0."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

from aibes_agent.tools.base import Tool, ToolContext, ToolResult


def _resolve_path(path: str, cwd: str) -> Path:
    raw_path = Path(path)
    if not raw_path.is_absolute():
        raw_path = Path(cwd) / raw_path
    return raw_path.expanduser().resolve()


class PdfExtractInput(BaseModel):
    file_path: str = Field(..., description="Path to the PDF file")
    pages: Optional[List[int]] = Field(
        None,
        description="Specific 1-indexed pages to extract. Empty means all pages.",
    )
    max_chars: int = Field(20000, description="Maximum characters to return")


class PdfExtractTool(Tool[PdfExtractInput]):
    name = "PdfExtract"
    description = (
        "Extract text from a PDF file. Requires the documents extras. "
        "Optionally limit to specific pages or a maximum character count."
    )
    input_model = PdfExtractInput

    def is_read_only(self, input: PdfExtractInput) -> bool:
        return True

    async def call(self, input: PdfExtractInput, context: ToolContext) -> ToolResult:
        try:
            import fitz  # type: ignore[import-not-found]  # pymupdf
        except ImportError:
            return ToolResult.fail(
                "pymupdf not found. Install the documents extras: "
                "pip install aibes-agent[documents]"
            )

        path = _resolve_path(input.file_path, context.cwd)
        if not path.exists():
            return ToolResult.fail(f"File not found: {path}")

        try:
            doc = fitz.open(str(path))
            texts: List[str] = []
            total_pages = len(doc)

            page_indices = input.pages
            if page_indices:
                page_indices = [p - 1 for p in page_indices if 1 <= p <= total_pages]
            else:
                page_indices = list(range(total_pages))

            for idx in page_indices:
                page = doc.load_page(idx)
                text = page.get_text()
                if text.strip():
                    texts.append(f"--- Page {idx + 1} ---\n{text}")
                if sum(len(t) for t in texts) >= input.max_chars:
                    break

            doc.close()
            full_text = "\n\n".join(texts)[: input.max_chars]
            return ToolResult.ok(
                full_text,
                file_path=str(path),
                total_pages=total_pages,
                extracted_pages=len(page_indices),
            )
        except Exception as e:
            return ToolResult.fail(f"Failed to extract PDF: {e}")


class MarkdownMergeInput(BaseModel):
    paths: List[str] = Field(
        ...,
        description="List of Markdown file paths or glob patterns to merge",
    )
    output_path: str = Field(
        "",
        description="If provided, write the merged result to this file. Otherwise return as text.",
    )
    add_toc: bool = Field(
        False,
        description="If True, prepend a simple table of contents based on H1/H2 headings",
    )


class MarkdownMergeTool(Tool[MarkdownMergeInput]):
    name = "MarkdownMerge"
    description = (
        "Merge multiple Markdown files into a single document. Supports glob patterns, "
        "optional table of contents, and writing the result to a file."
    )
    input_model = MarkdownMergeInput

    def is_read_only(self, input: MarkdownMergeInput) -> bool:
        return not input.output_path

    async def call(self, input: MarkdownMergeInput, context: ToolContext) -> ToolResult:
        try:
            import fnmatch
            import os

            files: List[Path] = []
            for pattern in input.paths:
                raw = Path(pattern)
                if not raw.is_absolute():
                    raw = Path(context.cwd) / raw
                raw = raw.expanduser().resolve()

                if raw.is_file():
                    files.append(raw)
                elif "*" in str(raw) or "?" in str(raw):
                    base_dir = raw.parent
                    match_name = raw.name
                    if base_dir.exists():
                        files.extend(
                            sorted(
                                p
                                for p in base_dir.iterdir()
                                if p.is_file() and fnmatch.fnmatch(p.name, match_name)
                            )
                        )
                elif raw.is_dir():
                    files.extend(
                        sorted(
                            p for p in raw.iterdir() if p.is_file() and p.suffix.lower() == ".md"
                        )
                    )

            if not files:
                return ToolResult.fail("No Markdown files found matching the given paths")

            # Deduplicate while preserving order
            seen = set()
            unique_files: List[Path] = []
            for f in files:
                if f not in seen:
                    seen.add(f)
                    unique_files.append(f)

            merged_parts: List[str] = []
            toc_entries: List[str] = []

            for file_path in unique_files:
                try:
                    content = file_path.read_text(encoding="utf-8")
                except Exception as e:
                    merged_parts.append(f"<!-- Failed to read {file_path}: {e} -->\n")
                    continue

                if input.add_toc:
                    for line in content.splitlines():
                        if line.startswith("# "):
                            title = line.lstrip("# ").strip()
                            toc_entries.append(f"- {title}")
                        elif line.startswith("## "):
                            title = line.lstrip("# ").strip()
                            toc_entries.append(f"  - {title}")

                merged_parts.append(f"<!-- {file_path.name} -->\n\n{content}\n\n---\n")

            body = "\n".join(merged_parts).rstrip("-\n").strip()
            if input.add_toc and toc_entries:
                toc = "# Table of Contents\n\n" + "\n".join(toc_entries) + "\n\n---\n\n"
                body = toc + body

            if input.output_path:
                out_path = _resolve_path(input.output_path, context.cwd)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(body, encoding="utf-8")
                return ToolResult.ok(
                    f"Merged {len(unique_files)} files into {out_path}",
                    output_path=str(out_path),
                    source_files=[str(f) for f in unique_files],
                )

            return ToolResult.ok(
                body,
                source_files=[str(f) for f in unique_files],
                merged_count=len(unique_files),
            )
        except Exception as e:
            return ToolResult.fail(f"Markdown merge failed: {e}")
