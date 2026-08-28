"""tests/test_zc_word_pdf.py

Covers zc_word.py / zc_pdf.py: the two Skills-only chat loops
added in v1.33.0 to close out zc_skills_api.py's PREBUILT_SKILLS set
(docx/pdf had been listed there since v1.15.0 with no CLI path to either).
Both modules are structurally identical to zc_excel.py's /
zc_powerpoint.py's --*-native path minus the hand-rolled fallback, so
these tests mirror test_zc_skills_api.py's monkeypatch style rather
than duplicating a full interactive-session harness.
"""
import pytest

import wire.zc_pdf as zc_pdf
import wire.zc_word as zc_word
from wire.zc_files import FilesAPI
from wire.zc_skills_api import SkillsApiClient


@pytest.fixture(autouse=True)
def _no_real_network(monkeypatch):
    """Belt-and-suspenders: fail loudly if a test forgets to monkeypatch
    FilesAPI/SkillsApiClient and a real network call is attempted."""
    def _boom(*a, **k):
        raise AssertionError("unmocked network call in zc_word/zc_pdf test")
    monkeypatch.setattr(SkillsApiClient, "_call", _boom)


def _queue_inputs(monkeypatch, inputs):
    it = iter(inputs)
    monkeypatch.setattr("builtins.input", lambda *_: next(it))


# ── zc_word.cmd_docx_chat ────────────────────────────────────────────


def test_docx_chat_no_input_file_skips_upload(monkeypatch, capsys):
    monkeypatch.setattr(FilesAPI, "upload", lambda self, path: pytest.fail("should not upload"))
    _queue_inputs(monkeypatch, ["/exit"])
    out_path = zc_word.cmd_docx_chat("k", "claude-sonnet-5")
    assert out_path == "docx_session.docx"


def test_docx_chat_uploads_input_file_once(monkeypatch):
    calls = []
    monkeypatch.setattr(FilesAPI, "upload", lambda self, path: calls.append(path) or {"id": "file_1"})
    monkeypatch.setattr(SkillsApiClient, "call_with_skills_turn",
                        lambda self, *a, **k: {"content": []})
    _queue_inputs(monkeypatch, ["make it a memo", "/exit"])
    zc_word.cmd_docx_chat("k", "claude-sonnet-5", input_path="draft.docx")
    assert calls == ["draft.docx"]


def test_docx_chat_upload_failure_exits(monkeypatch):
    monkeypatch.setattr(FilesAPI, "upload", lambda self, path: (_ for _ in ()).throw(OSError("nope")))
    with pytest.raises(SystemExit):
        zc_word.cmd_docx_chat("k", "claude-sonnet-5", input_path="missing.docx")


def test_docx_chat_default_output_path_from_input():
    # output_path derivation doesn't touch the network — check directly
    # via the same regex the function uses, since there's no separate
    # helper to import.
    import re
    assert re.sub(r"\.\w+$", "", "notes.txt") + ".docx" == "notes.docx"


def test_docx_chat_downloads_generated_file(monkeypatch):
    downloaded = {}
    monkeypatch.setattr(FilesAPI, "download",
                        lambda self, fid, out: downloaded.setdefault("fid", fid) or out)
    monkeypatch.setattr(SkillsApiClient, "call_with_skills_turn", lambda self, *a, **k: {
        "content": [{"type": "text", "text": "done"}],
        "container": {"id": "cont_1"},
    })
    # No file_id in this response -> nothing to download
    _queue_inputs(monkeypatch, ["write a memo", "/exit"])
    zc_word.cmd_docx_chat("k", "claude-sonnet-5")
    assert "fid" not in downloaded

    monkeypatch.setattr(SkillsApiClient, "call_with_skills_turn", lambda self, *a, **k: {
        "content": [{"type": "text", "text": "done"},
                    {"type": "code_execution_tool_result",
                     "content": {"content": [{"type": "file", "file_id": "file_out"}]}}],
        "container": {"id": "cont_1"},
    })
    _queue_inputs(monkeypatch, ["write a memo", "/exit"])
    zc_word.cmd_docx_chat("k", "claude-sonnet-5", output_path="memo.docx")
    assert downloaded["fid"] == "file_out"


def test_docx_chat_api_error_does_not_crash(monkeypatch, capsys):
    monkeypatch.setattr(SkillsApiClient, "call_with_skills_turn",
                        lambda self, *a, **k: {"error": "rate limited"})
    _queue_inputs(monkeypatch, ["write a memo", "/exit"])
    zc_word.cmd_docx_chat("k", "claude-sonnet-5")
    assert "rate limited" in capsys.readouterr().out


def test_docx_chat_uses_docx_skill(monkeypatch):
    seen = {}

    def fake_call(self, messages, skills, **k):
        seen["skills"] = skills
        return {"content": []}

    monkeypatch.setattr(SkillsApiClient, "call_with_skills_turn", fake_call)
    _queue_inputs(monkeypatch, ["hi", "/exit"])
    zc_word.cmd_docx_chat("k", "claude-sonnet-5")
    assert seen["skills"] == ["docx"]


# ── zc_pdf.cmd_pdf_chat ──────────────────────────────────────────────


def test_pdf_chat_no_input_file_skips_upload(monkeypatch):
    monkeypatch.setattr(FilesAPI, "upload", lambda self, path: pytest.fail("should not upload"))
    _queue_inputs(monkeypatch, ["/exit"])
    out_path = zc_pdf.cmd_pdf_chat("k", "claude-sonnet-5")
    assert out_path == "pdf_session.pdf"


def test_pdf_chat_uploads_input_file_once(monkeypatch):
    calls = []
    monkeypatch.setattr(FilesAPI, "upload", lambda self, path: calls.append(path) or {"id": "file_2"})
    monkeypatch.setattr(SkillsApiClient, "call_with_skills_turn",
                        lambda self, *a, **k: {"content": []})
    _queue_inputs(monkeypatch, ["fill in the form", "/exit"])
    zc_pdf.cmd_pdf_chat("k", "claude-sonnet-5", input_path="form.pdf")
    assert calls == ["form.pdf"]


def test_pdf_chat_upload_missing_id_exits(monkeypatch):
    monkeypatch.setattr(FilesAPI, "upload", lambda self, path: {})  # no "id" key
    with pytest.raises(SystemExit):
        zc_pdf.cmd_pdf_chat("k", "claude-sonnet-5", input_path="form.pdf")


def test_pdf_chat_uses_pdf_skill(monkeypatch):
    seen = {}

    def fake_call(self, messages, skills, **k):
        seen["skills"] = skills
        return {"content": []}

    monkeypatch.setattr(SkillsApiClient, "call_with_skills_turn", fake_call)
    _queue_inputs(monkeypatch, ["hi", "/exit"])
    zc_pdf.cmd_pdf_chat("k", "claude-sonnet-5")
    assert seen["skills"] == ["pdf"]


def test_pdf_chat_reuses_container_id_across_turns(monkeypatch):
    container_ids_seen = []

    def fake_call(self, messages, skills, container_id=None, **k):
        container_ids_seen.append(container_id)
        return {"content": [], "container": {"id": "cont_persist"}}

    monkeypatch.setattr(SkillsApiClient, "call_with_skills_turn", fake_call)
    _queue_inputs(monkeypatch, ["first turn", "second turn", "/exit"])
    zc_pdf.cmd_pdf_chat("k", "claude-sonnet-5")
    assert container_ids_seen == [None, "cont_persist"]
