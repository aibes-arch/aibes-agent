"""Image processing tools for aibes-agent."""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from aibes_agent.tools.base import Tool, ToolContext, ToolResult


def _resolve_path(path: str, cwd: str) -> Path:
    raw_path = Path(path)
    if not raw_path.is_absolute():
        raw_path = Path(cwd) / raw_path
    return raw_path.expanduser().resolve()


class ImageReadInput(BaseModel):
    file_path: str = Field(..., description="Path to the image file")
    include_base64: bool = Field(
        False,
        description="If True, include a base64 data URI of the image in the result metadata.",
    )
    max_size: int = Field(
        1024,
        description="When include_base64 is True, resize the longest edge to at most this many pixels before encoding.",
    )


class ImageReadTool(Tool[ImageReadInput]):
    name = "ImageRead"
    description = (
        "Read image metadata (dimensions, format, mode, file size) and optionally "
        "return a base64 data URI. Useful when the user refers to an uploaded image."
    )
    input_model = ImageReadInput

    def is_read_only(self, input: ImageReadInput) -> bool:
        return True

    async def call(self, input: ImageReadInput, context: ToolContext) -> ToolResult:
        try:
            from PIL import Image
        except ImportError:
            return ToolResult.fail(
                "Pillow not found. Install it with: pip install Pillow"
            )

        path = _resolve_path(input.file_path, context.cwd)
        if not path.exists():
            return ToolResult.fail(f"File not found: {path}")

        try:
            with Image.open(path) as img:
                width, height = img.size
                image_format = img.format or path.suffix.lstrip(".").upper() or "UNKNOWN"
                mode = img.mode

                metadata = {
                    "file_path": str(path),
                    "width": width,
                    "height": height,
                    "format": image_format,
                    "mode": mode,
                    "file_size_bytes": path.stat().st_size,
                }

                content_lines = [
                    f"Image: {path.name}",
                    f"Format: {image_format}",
                    f"Dimensions: {width}x{height}",
                    f"Mode: {mode}",
                    f"File size: {path.stat().st_size} bytes",
                ]

                if input.include_base64:
                    data_uri = _image_to_data_uri(img, input.max_size, image_format)
                    metadata["data_uri"] = data_uri
                    content_lines.append(f"Data URI length: {len(data_uri)} characters")

                return ToolResult.ok("\n".join(content_lines), **metadata)
        except Exception as e:
            return ToolResult.fail(f"Failed to read image: {e}")


def _image_to_data_uri(img, max_size: int, fallback_format: str) -> str:
    """Resize an image if needed and return a base64 data URI."""
    from PIL import Image

    # Resize preserving aspect ratio
    img = img.copy()
    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

    fmt = img.format or fallback_format
    if fmt and fmt.upper() not in ("PNG", "JPEG", "GIF", "WEBP", "BMP"):
        fmt = "PNG"
    if not fmt:
        fmt = "PNG"

    buffer = io.BytesIO()
    if fmt.upper() == "JPEG" and img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.save(buffer, format=fmt)
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    mime = f"image/{fmt.lower()}"
    return f"data:{mime};base64,{encoded}"
