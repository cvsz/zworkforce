"""tests/test_zc_code_slash_compact.py

Covers the /compact fix in cmd_code_slash() (zc_code.py). Previously
/compact printed a success message and did nothing at all — see
CHANGELOG for this fix, and tests/test_zc_code_context_editing.py
for the sibling --agent-context-editing feature this reuses
(zc_tools.build_context_management / COMPACTION_BETA).
"""

import pytest

from wire.zc_code import CodeSession, cmd_code_slash
from wire.zc_tools import COMPACTION_BETA


@pytest.fixture(autouse=True)
def isolated_sessions_dir(tmp_path, monkeypatch):
    """Keep CodeSession.save() out of the real ~/.ai-coder directory."""
    monkeypatch.setattr(
"wire.zc_code.SESSIONS_DIR", tmp_path)


def _compaction_response(summary="Compacted summary of prior turns."):
    return {
        "content": [{"type": "compaction", "content": summary}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 40, "output_tokens": 20},
    }


def _session_with_turns(model="zc-xxx"):
    s = CodeSession(cwd=".", model=model)
    s.add_turn("user", "do a big task", usage={"input_tokens": 1000, "output_tokens": 0})
    s.add_turn("assistant", "done", usage={"input_tokens": 0, "output_tokens": 500})
    s.save()
    return s


def test_compact_without_session_id_does_not_call_api(monkeypatch, capsys):
    called = {"n": 0}
    monkeypatch.setattr(
"wire.zc_code.CodeAgent._post", lambda *a, **k: called.__setitem__("n", called["n"] + 1))

    cmd_code_slash("/compact", "key", "zc-xxx", session_id=None)

    assert called["n"] == 0
    assert "needs an active session" in capsys.readouterr().out


def test_compact_missing_session_reports_not_found(capsys):
    cmd_code_slash("/compact", "key", "zc-xxx", session_id="does-not-exist")
    assert "not found" in capsys.readouterr().out.lower()


def test_compact_sends_compaction_beta_and_edit(monkeypatch):
    session = _session_with_turns()
    captured = {}

    def fake_post(self, payload, betas=None):
        captured["payload"] = payload
        captured["betas"] = betas
        return _compaction_response()

    monkeypatch.setattr(
"wire.zc_code.CodeAgent._post", fake_post)

    cmd_code_slash("/compact", "key", session.model, session_id=session.id)

    assert captured["betas"] == [COMPACTION_BETA]
    edits = captured["payload"]["context_management"]["edits"]
    assert len(edits) == 1
    assert edits[0]["type"] == "compact_20260112"
    # forced immediately rather than waiting for the normal threshold
    assert edits[0]["trigger"]["value"] == 0


def test_compact_replaces_turns_with_summary_and_persists(monkeypatch):
    session = _session_with_turns()
    monkeypatch.setattr(

        "wire.zc_code.CodeAgent._post",
        lambda self, payload, betas=None: _compaction_response("the summary text"),
    )

    cmd_code_slash("/compact", "key", session.model, session_id=session.id)

    reloaded = CodeSession.load(session.id)
    assert len(reloaded.turns) == 1
    assert reloaded.turns[0]["content"] == "the summary text"


def test_compact_reports_api_error_without_touching_session(monkeypatch, capsys):
    session = _session_with_turns()
    monkeypatch.setattr(

        "wire.zc_code.CodeAgent._post",
        lambda self, payload, betas=None: {"error": "rate limited"},
    )

    cmd_code_slash("/compact", "key", session.model, session_id=session.id)

    assert "Compaction failed" in capsys.readouterr().out
    reloaded = CodeSession.load(session.id)
    assert len(reloaded.turns) == 2  # untouched
