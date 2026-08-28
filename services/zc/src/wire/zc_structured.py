"""
zc_structured.py — Structured Outputs
AI Model Coder CLI v1.30.0

Force zAICoder to respond in validated JSON matching a schema.
Uses the output_config.format parameter — GA on the zAICoder API for
zAICoder Fable 5, zAICoder Mythos 5, zAICoder Opus 4.8, zAICoder Mythos Preview,
zAICoder Opus 4.7, zAICoder Opus 4.6, zAICoder Sonnet 5, zAICoder Sonnet 4.6,
zAICoder Sonnet 4.5, zAICoder Opus 4.5, and zAICoder Haiku 4.5. No beta header
required (the old structured-outputs-2025-11-13 header still works
during Anthropic's transition period, but sending it unconditionally on
every request is dead weight now that GA doesn't need it — removed in
v1.30.0, see docs/42_upgrade_v1.30.0.md).

Modes:
  • json_object   — Any valid JSON object (no schema)
  • json_schema   — Strict JSON matching a given JSON Schema
  • Tool schemas  — strict:true on tool input_schema

CLI flags:
  --structured             Enable JSON output mode
  --schema FILE            Path to a JSON Schema file
  --schema-inline TEXT     Inline JSON Schema string
  --structured-extract     Extract structured data from text/files
"""

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from wire.exceptions import AICoderError
from wire.resilience import CircuitBreaker, retry, urlopen_json

_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)


class StructuredCoder:
    """zAICoder client for structured / JSON outputs."""

    ENDPOINT = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str = "zc-xxx",
                 max_tokens: int = 4096):
        self.api_key    = api_key
        self.model      = model
        self.max_tokens = max_tokens

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict) -> dict:
        headers = {
            "Content-Type":    "application/json",
            "x-api-key":       self.api_key,
            "anthropic-version": "2023-06-01",
        }
        req = urllib.request.Request(
            self.ENDPOINT,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        return urlopen_json(req, timeout=120)

    def _post(self, payload: dict) -> dict:
        # Preserves the pre-existing {"error": ...} contract callers below
        # already check for, while retrying transient failures in _call().
        try:
            return self._call(payload)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    # ── JSON object mode ──────────────────────────────────────────────────

    def json_object(self, prompt: str, system: Optional[str] = None) -> dict:
        """Return any valid JSON object. No schema enforcement."""
        payload = {
            "model":      self.model,
            "max_tokens": self.max_tokens,
            "output_config": {"format": {"type": "json_object"}},
            "messages":   [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        data = self._post(payload)
        if "error" in data:
            raise RuntimeError(data["error"])
        text = "".join(
            b.get("text", "") for b in data.get("content", [])
            if b.get("type") == "text"
        )
        return json.loads(text)

    # ── JSON schema mode ──────────────────────────────────────────────────

    def json_schema(self, prompt: str, schema: dict,
                    name: str = "output", system: Optional[str] = None) -> dict:
        """Return JSON validated against a JSON Schema."""
        payload = {
            "model":      self.model,
            "max_tokens": self.max_tokens,
            "output_config": {
                "format": {
                    "type":   "json_schema",
                    "name":   name,
                    "schema": schema,
                    "strict": True,
                }
            },
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        data = self._post(payload)
        if "error" in data:
            raise RuntimeError(data["error"])

        text = "".join(
            b.get("text", "") for b in data.get("content", [])
            if b.get("type") == "text"
        )
        parsed = json.loads(text)
        # Client-side schema validation (lightweight)
        self._validate(parsed, schema)
        return parsed

    # ── Extract structured data from content ──────────────────────────────

    def extract(self, content: str, schema: dict,
                instruction: str = "") -> dict:
        """Extract structured data from unstructured text."""
        prompt = (
            f"Extract structured data from the following content.\n"
            f"{('Instructions: ' + instruction) if instruction else ''}\n\n"
            f"Content:\n{content}"
        )
        return self.json_schema(
            prompt, schema,
            system="Extract exactly the fields defined in the schema. "
                   "If a field is missing from the content, use null.",
        )

    # ── Code analysis structured ──────────────────────────────────────────

    def analyse_code(self, code: str, language: str = "") -> dict:
        """Return a structured code analysis report."""
        schema = {
            "type": "object",
            "properties": {
                "summary":         {"type": "string"},
                "language":        {"type": "string"},
                "complexity":      {"type": "string", "enum": ["low", "medium", "high"]},
                "issues":          {"type": "array", "items": {"type": "object",
                    "properties": {
                        "severity":    {"type": "string", "enum": ["info", "warning", "error"]},
                        "line":        {"type": ["integer", "null"]},
                        "description": {"type": "string"},
                    }, "required": ["severity", "description"]}},
                "suggestions":     {"type": "array", "items": {"type": "string"}},
                "security_flags":  {"type": "array", "items": {"type": "string"}},
                "test_coverage":   {"type": "string"},
            },
            "required": ["summary", "complexity", "issues", "suggestions"],
        }
        prompt = f"Analyse this {language} code:\n```\n{code}\n```"
        return self.json_schema(prompt, schema, name="code_analysis",
                                system="You are a senior code reviewer. Be concise and precise.")

    # ── Validation ────────────────────────────────────────────────────────

    def _validate(self, data: dict, schema: dict):
        """Lightweight required-field check."""
        required = schema.get("required", [])
        missing  = [r for r in required if r not in data]
        if missing:
            raise ValueError(f"Schema validation: missing required fields: {missing}")


# ── CLI entry points ───────────────────────────────────────────────────────

def cmd_structured(prompt: str, api_key: str, model: str,
                   schema_path: Optional[str] = None, schema_inline: Optional[str] = None,
                   pretty: bool = True) -> dict:
    sc = StructuredCoder(api_key=api_key, model=model)

    if schema_path:
        schema = json.loads(Path(schema_path).read_text())
        print(f"\033[94mℹ Structured output (schema from {schema_path})\033[0m\n")
        result = sc.json_schema(prompt, schema)
    elif schema_inline:
        schema = json.loads(schema_inline)
        print("\033[94mℹ Structured output (inline schema)\033[0m\n")
        result = sc.json_schema(prompt, schema)
    else:
        print("\033[94mℹ Structured output (JSON object mode)\033[0m\n")
        result = sc.json_object(prompt)

    indent = 2 if pretty else None
    print(json.dumps(result, indent=indent, ensure_ascii=False))
    return result


def cmd_structured_analyse(file_path: str, api_key: str, model: str) -> dict:
    code = Path(file_path).read_text()
    lang = Path(file_path).suffix.lstrip(".")
    print(f"\033[94mℹ Structured code analysis: {file_path}\033[0m\n")
    sc     = StructuredCoder(api_key=api_key, model=model)
    result = sc.analyse_code(code, lang)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_structured_extract(content_file: str, schema_path: str,
                            api_key: str, model: str) -> dict:
    content = Path(content_file).read_text()
    schema  = json.loads(Path(schema_path).read_text())
    print(f"\033[94mℹ Extracting structured data from {content_file}\033[0m\n")
    sc     = StructuredCoder(api_key=api_key, model=model)
    result = sc.extract(content, schema)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result
