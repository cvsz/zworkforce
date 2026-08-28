"""
zc_vision.py — Vision & Multimodal (Images + PDFs)
AI Model Coder CLI v1.8.0

Send images and PDFs to zAICoder for analysis, OCR, review, or code generation.

CLI flags:
  --vision FILE           Analyse an image file (jpg/png/gif/webp)
  --vision-pdf FILE       Analyse a PDF file
  --vision-url URL        Analyse an image from a URL
  --vision-prompt TEXT    Instruction for the vision request (default: "Describe this")
  --vision-code           Ask zAICoder to generate/fix code from a screenshot
  --vision-compare F1 F2  Compare two images side by side
"""

import base64
import mimetypes
import sys
from pathlib import Path

import anthropic
from typing import Optional

SUPPORTED_IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
SUPPORTED_DOC_TYPES   = {".pdf"}


def _encode_file(path: str) -> tuple[str, str]:
    """Return (base64_data, media_type)."""
    p    = Path(path)
    ext  = p.suffix.lower()
    data = base64.standard_b64encode(p.read_bytes()).decode("utf-8")
    mt   = mimetypes.guess_type(path)[0] or "application/octet-stream"
    if ext in SUPPORTED_IMAGE_TYPES:
        mt = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp",
        }[ext]
    elif ext == ".pdf":
        mt = "application/pdf"
    return data, mt


def _image_block(path: Optional[str] = None, url: Optional[str] = None) -> dict:
    if url:
        return {"type": "image", "source": {"type": "url", "url": url}}
    if path is None:
        raise ValueError("Either path or url must be provided")
    data, mt = _encode_file(path)
    return {"type": "image", "source": {"type": "base64", "media_type": mt, "data": data}}


def _doc_block(path: str) -> dict:
    data, _ = _encode_file(path)
    return {
        "type": "document",
        "source": {"type": "base64", "media_type": "application/pdf", "data": data},
        "citations": {"enabled": True},
    }


class VisionCoder:
    """zAICoder client for image and PDF analysis."""

    def __init__(self, api_key: str, model: str = "zc-xxx",
                 max_tokens: int = 4096):
        self.client     = anthropic.Anthropic(api_key=api_key)
        self.model      = model
        self.max_tokens = max_tokens

    def analyse_image(self, path: Optional[str] = None, url: Optional[str] = None,
                      prompt: str = "Describe this image in detail.",
                      system: Optional[str] = None) -> str:
        content = [_image_block(path=path, url=url), {"type": "text", "text": prompt}]
        return self._call(content, system)

    def analyse_pdf(self, path: str,
                    prompt: str = "Summarise this document.",
                    system: Optional[str] = None) -> str:
        content = [_doc_block(path), {"type": "text", "text": prompt}]
        return self._call(content, system)

    def code_from_screenshot(self, path: Optional[str] = None, url: Optional[str] = None,
                              language: str = "auto") -> str:
        prompt = (
            f"This is a screenshot of a UI or code. "
            f"Generate {'the ' + language + ' ' if language != 'auto' else ''}code "
            f"that recreates or implements what you see. "
            f"Provide complete, runnable code with comments."
        )
        content = [_image_block(path=path, url=url), {"type": "text", "text": prompt}]
        system  = "You are an expert developer. Write clean, production-ready code."
        return self._call(content, system)

    def compare_images(self, paths: list[str], prompt: str = "") -> str:
        content = [_image_block(path=p) for p in paths]
        content.append({
            "type": "text",
            "text": prompt or "Compare these images. Describe the differences and similarities."
        })
        return self._call(content)

    def extract_text(self, path: Optional[str] = None, url: Optional[str] = None) -> str:
        """OCR – extract all text from an image."""
        prompt  = "Extract and transcribe ALL text visible in this image. Preserve formatting."
        content = [_image_block(path=path, url=url), {"type": "text", "text": prompt}]
        return self._call(content)

    def _call(self, content: list, system: Optional[str] = None) -> str:
        if system:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": content}],
                system=system,
            )
        else:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": content}],
            )
        return getattr(resp.content[0], "text", "")


# ── CLI entry points ───────────────────────────────────────────────────────

def _validate_image(path: str):
    p = Path(path)
    if not p.exists():
        print(f"\033[91m✗ File not found: {path}\033[0m", file=sys.stderr)
        sys.exit(1)
    if p.suffix.lower() not in SUPPORTED_IMAGE_TYPES:
        print(f"\033[91m✗ Unsupported image type: {p.suffix}\033[0m", file=sys.stderr)
        sys.exit(1)


def cmd_vision(path: str, prompt: str, api_key: str, model: str,
               is_code: bool = False, language: str = "auto"):
    _validate_image(path)
    vc = VisionCoder(api_key=api_key, model=model)
    size = Path(path).stat().st_size // 1024
    print(f"\033[94mℹ Analysing image: {path} ({size} KB)\033[0m\n")
    if is_code:
        result = vc.code_from_screenshot(path=path, language=language)
    else:
        result = vc.analyse_image(path=path, prompt=prompt or "Describe this image in detail.")
    print(result)
    return result


def cmd_vision_url(url: str, prompt: str, api_key: str, model: str):
    vc = VisionCoder(api_key=api_key, model=model)
    print(f"\033[94mℹ Analysing image URL: {url}\033[0m\n")
    result = vc.analyse_image(url=url, prompt=prompt or "Describe this image in detail.")
    print(result)
    return result


def cmd_vision_pdf(path: str, prompt: str, api_key: str, model: str):
    p = Path(path)
    if not p.exists():
        print(f"\033[91m✗ File not found: {path}\033[0m", file=sys.stderr); sys.exit(1)
    vc = VisionCoder(api_key=api_key, model=model)
    size = p.stat().st_size // 1024
    print(f"\033[94mℹ Analysing PDF: {path} ({size} KB)\033[0m\n")
    result = vc.analyse_pdf(path=path, prompt=prompt or "Summarise this document.")
    print(result)
    return result


def cmd_vision_compare(paths: list[str], prompt: str, api_key: str, model: str):
    for p in paths:
        _validate_image(p)
    vc = VisionCoder(api_key=api_key, model=model)
    print(f"\033[94mℹ Comparing {len(paths)} images\033[0m\n")
    result = vc.compare_images(paths, prompt)
    print(result)
    return result


def cmd_vision_ocr(path: str, api_key: str, model: str):
    _validate_image(path)
    vc = VisionCoder(api_key=api_key, model=model)
    print(f"\033[94mℹ OCR: {path}\033[0m\n")
    result = vc.extract_text(path=path)
    print(result)
    return result
