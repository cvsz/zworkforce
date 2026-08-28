"""
zc_files.py — Files API (beta)
AI Model Coder CLI v1.8.0

Upload files once, reference by file_id in multiple Messages API calls.
Supports: PDFs, images, plain text, code, documents.

CLI flags:
  --file-upload FILE        Upload a file, print file_id
  --file-list               List all uploaded files
  --file-delete ID          Delete a file
  --file-use ID             Use a file_id in a prompt
  --file-ask ID PROMPT      Ask a question about an uploaded file
  --file-download ID OUT    Download file content
"""

import json
import mimetypes
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from wire.exceptions import AICoderError
from wire.resilience import CircuitBreaker, raise_for_http_error, retry, urlopen_json

FILES_BASE    = "https://api.anthropic.com/v1/files"
MESSAGES_BASE = "https://api.anthropic.com/v1/messages"
BETA_HEADER   = "files-api-2025-04-14"

# platform.zc.com/docs/en/build-with-zc/files — File storage and limits
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB per file
_FORBIDDEN_FILENAME_CHARS = set('<>:"|?*\\/') | {chr(c) for c in range(32)}

LOCAL_REGISTRY = Path(os.path.expanduser("~/.ai-coder/files_registry.json"))
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)


def _validate_filename(name: str) -> Optional[str]:
    """Mirror the API's documented Invalid filename (400) rule client-side.
    Returns an error message, or None if the filename is fine."""
    if not (1 <= len(name) <= 255):
        return f"Invalid filename: must be 1-255 characters (got {len(name)})"
    bad = _FORBIDDEN_FILENAME_CHARS & set(name)
    if bad:
        shown = ", ".join(repr(c) for c in sorted(bad, key=str))
        return f"Invalid filename: contains forbidden character(s) {shown}"
    return None


class FilesAPI:
    """Wrapper around the Anthropic Files API."""

    def __init__(self, api_key: str, model: str = "zc-xxx"):
        self.api_key = api_key
        self.model   = model
        LOCAL_REGISTRY.parent.mkdir(parents=True, exist_ok=True)

    def _headers(self, content_type: str = "application/json") -> dict:
        return {
            "x-api-key":         self.api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta":    BETA_HEADER,
            "Content-Type":      content_type,
        }

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call_json(self, req: "urllib.request.Request", timeout: float) -> dict:
        return urlopen_json(req, timeout=timeout)

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call_bytes(self, req: "urllib.request.Request", timeout: float) -> bytes:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except (urllib.error.HTTPError, TimeoutError, ConnectionError, OSError) as e:
            raise_for_http_error(e)

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call_nobody(self, req: "urllib.request.Request", timeout: float) -> None:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                r.read()
        except (urllib.error.HTTPError, TimeoutError, ConnectionError, OSError) as e:
            raise_for_http_error(e)

    # ── Upload ────────────────────────────────────────────────────────────

    def upload(self, file_path: str) -> dict:
        """Upload a file. Returns {id, filename, size, created_at, ...}"""
        p = Path(file_path)

        name_err = _validate_filename(p.name)
        if name_err:
            raise RuntimeError(f"Upload failed: {name_err}")

        size = p.stat().st_size
        if size > MAX_FILE_SIZE_BYTES:
            raise RuntimeError(
                f"Upload failed: File too large: {size / (1024*1024):.1f}MB "
                f"(max {MAX_FILE_SIZE_BYTES / (1024*1024):.0f}MB per file)"
            )

        data = p.read_bytes()
        mt   = mimetypes.guess_type(str(p))[0] or "application/octet-stream"

        # Multipart/form-data encoding
        boundary = "---AICLIBoundary"

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{p.name}"\r\n'
            f"Content-Type: {mt}\r\n\r\n"
        ).encode() + data + f"\r\n--{boundary}--\r\n".encode()

        headers = self._headers(f"multipart/form-data; boundary={boundary}")
        headers.pop("Content-Type", None)  # let us set it with boundary
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"

        req = urllib.request.Request(FILES_BASE, data=body, headers=headers, method="POST")
        try:
            result = self._call_json(req, timeout=60)
        except AICoderError as e:
            raise RuntimeError(f"Upload failed: {e.message}") from e

        # Save to local registry
        self._register(result, str(p))
        return result

    # ── List ──────────────────────────────────────────────────────────────

    def list_files(self, limit: int = 20, before_id: Optional[str] = None,
                   after_id: Optional[str] = None) -> dict:
        """List one page of files. Returns {"data": [...], "has_more": bool,
        "first_id": ..., "last_id": ...} per the paginated List Files endpoint."""
        params = {"limit": str(limit)}
        if before_id:
            params["before_id"] = before_id
        if after_id:
            params["after_id"] = after_id
        query = "&".join(f"{k}={v}" for k, v in params.items())
        req = urllib.request.Request(
            f"{FILES_BASE}?{query}",
            headers=self._headers(),
            method="GET",
        )
        try:
            return self._call_json(req, timeout=30)
        except AICoderError as e:
            raise RuntimeError(f"List failed: {e.message}") from e

    def list_files_all(self, max_items: Optional[int] = None) -> list:
        """Auto-paginate across all pages, bounded by max_items (None = unbounded)."""
        out, after_id = [], None
        while True:
            page = self.list_files(limit=100, after_id=after_id)
            batch = page.get("data", [])
            out.extend(batch)
            if max_items is not None and len(out) >= max_items:
                return out[:max_items]
            if not page.get("has_more") or not batch:
                return out
            after_id = batch[-1]["id"]

    # ── Retrieve metadata ─────────────────────────────────────────────────

    def get_file(self, file_id: str) -> dict:
        req = urllib.request.Request(
            f"{FILES_BASE}/{file_id}",
            headers=self._headers(),
            method="GET",
        )
        try:
            return self._call_json(req, timeout=30)
        except AICoderError as e:
            raise RuntimeError(f"Get failed: {e.message}") from e

    # ── Download content ──────────────────────────────────────────────────

    def download(self, file_id: str, output_path: str) -> str:
        # The API returns 400 "Not downloadable" for any file you uploaded
        # yourself — only files created by Skills or the code execution tool
        # have downloadable=true. Check metadata first so the CLI gives a
        # clear, actionable message instead of a bare HTTP error.
        try:
            meta = self.get_file(file_id)
        except RuntimeError:
            meta = None
        if meta is not None and meta.get("downloadable") is False:
            raise RuntimeError(
                "Download failed: this file is not downloadable. Only files "
                "created by Skills or the code execution tool can be "
                "downloaded — files you uploaded yourself never can be."
            )

        req = urllib.request.Request(
            f"{FILES_BASE}/{file_id}/content",
            headers={k: v for k, v in self._headers().items() if k != "Content-Type"},
            method="GET",
        )
        try:
            data = self._call_bytes(req, timeout=60)
        except AICoderError as e:
            raise RuntimeError(f"Download failed: {e.message}") from e
        Path(output_path).write_bytes(data)
        return output_path

    # ── Delete ────────────────────────────────────────────────────────────

    def delete(self, file_id: str) -> bool:
        req = urllib.request.Request(
            f"{FILES_BASE}/{file_id}",
            headers=self._headers(),
            method="DELETE",
        )
        try:
            self._call_nobody(req, timeout=30)
            self._unregister(file_id)
            return True
        except AICoderError as e:
            raise RuntimeError(f"Delete failed: {e.message}") from e

    # ── Use file in Messages API ──────────────────────────────────────────

    def ask_about_file(self, file_id: str, prompt: str,
                       media_type: str = "application/pdf",
                       max_tokens: int = 4096,
                       use_code_execution: bool = False) -> str:
        """Reference an uploaded file in a Messages API call.

        Block type follows the File type -> Content block table in
        platform.zc.com/docs/en/build-with-zc/files:
          - image/*                          -> `image` block
          - use_code_execution=True           -> `container_upload` block
            (datasets/CSV/XLSX/etc. that zAICoder's sandbox needs to actually
            open and run code against, not just read as text)
          - everything else (PDF, text/plain) -> `document` block
        """
        tools = []

        if media_type.startswith("image/"):
            block = {"type": "image", "source": {"type": "file", "file_id": file_id}}
        elif use_code_execution:
            block = {"type": "container_upload", "file_id": file_id}
            tools = [{"type": "code_execution_20250825", "name": "code_execution"}]
        else:
            block = {"type": "document", "source": {"type": "file", "file_id": file_id},
                     "citations": {"enabled": True}}

        payload = {
            "model":      self.model,
            "max_tokens": max_tokens,
            "messages": [{
                "role": "user",
                "content": [block, {"type": "text", "text": prompt}],
            }],
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Content-Type":      "application/json",
            "x-api-key":         self.api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta":    BETA_HEADER,
        }
        req = urllib.request.Request(
            MESSAGES_BASE,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        try:
            data = self._call_json(req, timeout=120)
        except AICoderError as e:
            return f"[API ERROR {getattr(e, 'status_code', '')}] {e.message}"

        return "".join(
            b.get("text", "") for b in data.get("content", [])
            if b.get("type") == "text"
        )

    # ── Local registry helpers ────────────────────────────────────────────

    def _load_registry(self) -> dict:
        if LOCAL_REGISTRY.exists():
            try:
                return json.loads(LOCAL_REGISTRY.read_text())
            except Exception:
                pass
        return {}

    def _register(self, api_result: dict, local_path: str):
        reg = self._load_registry()
        reg[api_result["id"]] = {
            "id":          api_result["id"],
            "filename":    api_result.get("filename", ""),
            "local_path":  local_path,
            "created_at":  api_result.get("created_at", ""),
            "size":        api_result.get("size", 0),
        }
        LOCAL_REGISTRY.write_text(json.dumps(reg, indent=2))

    def _unregister(self, file_id: str):
        reg = self._load_registry()
        reg.pop(file_id, None)
        LOCAL_REGISTRY.write_text(json.dumps(reg, indent=2))

    def list_local(self) -> dict:
        return self._load_registry()


# ── CLI entry points ───────────────────────────────────────────────────────

def cmd_file_upload(file_path: str, api_key: str, model: str):
    fa = FilesAPI(api_key=api_key, model=model)
    print(f"\033[94mℹ Uploading {file_path}…\033[0m")
    result = fa.upload(file_path)
    print(f"\033[92m✓ Uploaded: {result['id']}\033[0m")
    print(f"  Filename: {result.get('filename', '')}")
    print(f"  Size:     {result.get('size', 0):,} bytes")
    print(f"  Created:  {result.get('created_at', '')}")
    print(f"\n  Use with: ai-coder --file-ask {result['id']} \"your question\"")
    return result["id"]


def cmd_file_list(api_key: str, model: str, max_items: Optional[int] = None):
    fa    = FilesAPI(api_key=api_key, model=model)
    files = fa.list_files_all(max_items=max_items)
    local = fa.list_local()
    if not files:
        print("No files uploaded yet.")
        return
    print(f"\n{'ID':<28}{'FILENAME':<30}{'SIZE':>10}  CREATED")
    print("─" * 80)
    for f in files:
        fid      = f["id"]
        local_fn = local.get(fid, {}).get("local_path", "")
        fname    = f.get("filename", local_fn)[:29]
        size     = f"{f.get('size', 0):,}"
        created  = str(f.get("created_at", ""))[:10]
        print(f"{fid:<28}{fname:<30}{size:>10}  {created}")
    print(f"\n{len(files)} file(s)")


def cmd_file_delete(file_id: str, api_key: str):
    fa = FilesAPI(api_key=api_key)
    fa.delete(file_id)
    print(f"\033[92m✓ File {file_id} deleted.\033[0m")


def cmd_file_ask(file_id: str, prompt: str, api_key: str, model: str,
                 media_type: str = "application/pdf"):
    print(f"\033[94mℹ Asking about file {file_id}…\033[0m\n")
    fa     = FilesAPI(api_key=api_key, model=model)
    result = fa.ask_about_file(file_id, prompt, media_type=media_type)
    print(result)
    return result


def cmd_file_download(file_id: str, output_path: str, api_key: str):
    fa   = FilesAPI(api_key=api_key)
    path = fa.download(file_id, output_path)
    print(f"\033[92m✓ Downloaded to {path}\033[0m")
