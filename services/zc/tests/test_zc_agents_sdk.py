"""tests/test_zc_agents_sdk.py

Covers zc_agents_sdk.py. This module had zero test coverage going
into v1.19.0, so per this cycle's Definition of Done, this file covers
both the pre-existing behavior (PermissionMode, TOOL_PRESETS,
McpServerConfig) and the new v1.19.0 Managed Agents memory store support
(ManagedAgentsClient.create_memory_store, create_session's
memory_store_id wiring, cmd_managed_agent_run's memory_store param,
cmd_agent_memory_store_create).

The real ManagedAgentsClient talks to the hosted Managed Agents API via
the `anthropic` SDK's client.beta.{agents,environments,sessions,
memory_stores} resources, so these tests stub out `anthropic.Anthropic`
rather than hitting the network.
"""
import sys
import types
from unittest.mock import MagicMock

import pytest


def _install_fake_anthropic_module():
    """Install a minimal fake `anthropic` module into sys.modules so
    `import anthropic` inside zc_agents_sdk works without the real
    package needing client.beta.memory_stores (which may not exist in
    whatever SDK version is actually pinned/installed)."""
    fake = types.ModuleType("anthropic")
    fake.Anthropic = MagicMock()
    sys.modules["anthropic"] = fake
    return fake


@pytest.fixture
def agents_sdk(monkeypatch):
    _install_fake_anthropic_module()
    import importlib

    import wire.zc_agents_sdk as mod
    importlib.reload(mod)
    return mod


# ── Pre-existing behavior (previously untested) ─────────────────────────


def test_permission_mode_constants(agents_sdk):
    assert agents_sdk.PermissionMode.ACCEPT_EDITS == "acceptEdits"
    assert agents_sdk.PermissionMode.ASK_PERMISSION == "askPermission"
    assert agents_sdk.PermissionMode.SUPERVISED == "supervised"


def test_tool_presets_contains_expected_groups(agents_sdk):
    assert "all" in agents_sdk.TOOL_PRESETS
    assert "code" in agents_sdk.TOOL_PRESETS
    assert "bash" in agents_sdk.TOOL_PRESETS["all"]
    assert "web_search" not in agents_sdk.TOOL_PRESETS["code"]


def test_managed_agents_beta_header_unchanged(agents_sdk):
    # Regression guard: this header string is load-bearing for every
    # hosted Managed Agents call. Accidentally editing it silently breaks
    # every endpoint call with a 400, not an obvious error.
    assert agents_sdk.MANAGED_AGENTS_BETA == "managed-agents-2026-04-01"


# ── v1.19.0: Managed Agents memory stores ────────────────────────────────


def test_memory_store_beta_header(agents_sdk):
    assert agents_sdk.MEMORY_STORE_BETA == "agent-memory-2026-07-22"


def test_create_memory_store_sends_expected_betas(agents_sdk):
    # v1.27.0: memory store endpoints take MEMORY_STORE_BETA *alone* --
    # per the July 2, 2026 release note, agent-memory-2026-07-22 replaces
    # (not adds to) managed-agents-2026-04-01 on these endpoints, and
    # sending both 400s. See zc_agents_sdk.py's create_memory_store()
    # docstring.
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    fake_store = MagicMock(id="store_123")
    client.client.beta.memory_stores.create.return_value = fake_store

    result = client.create_memory_store(name="project-x-memory")

    client.client.beta.memory_stores.create.assert_called_once_with(
        name="project-x-memory",
        betas=[agents_sdk.MEMORY_STORE_BETA],
    )
    assert result == {"id": "store_123", "name": "project-x-memory"}


def test_create_memory_store_with_description(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.memory_stores.create.return_value = MagicMock(id="store_9")

    client.create_memory_store(name="notes", description="Per-user preferences")

    _, kwargs = client.client.beta.memory_stores.create.call_args
    assert kwargs["description"] == "Per-user preferences"
    assert kwargs["betas"] == [agents_sdk.MEMORY_STORE_BETA]


def test_get_memory_store_uses_memory_store_beta_alone(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.memory_stores.retrieve.return_value = MagicMock(id="store_1")

    client.get_memory_store("store_1")

    client.client.beta.memory_stores.retrieve.assert_called_once_with(
        "store_1", betas=[agents_sdk.MEMORY_STORE_BETA],
    )


def test_list_memory_stores_uses_memory_store_beta_alone(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.memory_stores.list.return_value = {"data": []}

    client.list_memory_stores(include_archived=True)

    client.client.beta.memory_stores.list.assert_called_once_with(
        betas=[agents_sdk.MEMORY_STORE_BETA], limit=50, include_archived=True,
    )


def test_archive_memory_store_uses_memory_store_beta_alone(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.memory_stores.archive.return_value = MagicMock(id="store_1")

    client.archive_memory_store("store_1")

    client.client.beta.memory_stores.archive.assert_called_once_with(
        "store_1", betas=[agents_sdk.MEMORY_STORE_BETA],
    )


def test_delete_memory_store_uses_memory_store_beta_alone(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")

    result = client.delete_memory_store("store_1")

    client.client.beta.memory_stores.delete.assert_called_once_with(
        "store_1", betas=[agents_sdk.MEMORY_STORE_BETA],
    )
    assert result == {"id": "store_1", "deleted": True}


def test_create_memory_uses_memory_store_beta_alone(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.memory_stores.memories.create.return_value = MagicMock(id="mem_1")

    result = client.create_memory("store_1", path="/notes.md", content="hello")

    client.client.beta.memory_stores.memories.create.assert_called_once_with(
        "store_1", path="/notes.md", content="hello", betas=[agents_sdk.MEMORY_STORE_BETA],
    )
    assert result["id"] == "mem_1"


def test_get_memory_uses_memory_store_beta_alone(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.memory_stores.memories.retrieve.return_value = MagicMock(content="x")

    client.get_memory("store_1", "mem_1")

    client.client.beta.memory_stores.memories.retrieve.assert_called_once_with(
        "mem_1", memory_store_id="store_1", betas=[agents_sdk.MEMORY_STORE_BETA],
    )


def test_update_memory_with_precondition(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.memory_stores.memories.update.return_value = MagicMock(id="mem_1")

    client.update_memory("store_1", "mem_1", content="new", content_sha256="abc123")

    _, kwargs = client.client.beta.memory_stores.memories.update.call_args
    assert kwargs["content"] == "new"
    assert kwargs["precondition"] == {"type": "content_sha256", "content_sha256": "abc123"}
    assert kwargs["betas"] == [agents_sdk.MEMORY_STORE_BETA]


def test_delete_memory_uses_memory_store_beta_alone(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")

    result = client.delete_memory("store_1", "mem_1")

    client.client.beta.memory_stores.memories.delete.assert_called_once_with(
        "mem_1", memory_store_id="store_1", betas=[agents_sdk.MEMORY_STORE_BETA],
    )
    assert result == {"id": "mem_1", "deleted": True}


def test_cmd_agent_memory_store_delete_dry_runs_by_default(agents_sdk, monkeypatch):
    mac = MagicMock()
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    result = agents_sdk.cmd_agent_memory_store_delete("store_1", api_key="sk-test")

    mac.delete_memory_store.assert_not_called()
    assert result is None


def test_cmd_agent_memory_store_delete_confirmed(agents_sdk, monkeypatch):
    mac = MagicMock()
    mac.delete_memory_store.return_value = {"id": "store_1", "deleted": True}
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    result = agents_sdk.cmd_agent_memory_store_delete("store_1", api_key="sk-test", confirm=True)

    mac.delete_memory_store.assert_called_once_with("store_1")
    assert result == {"id": "store_1", "deleted": True}


def test_cmd_agent_memory_delete_dry_runs_by_default(agents_sdk, monkeypatch):
    mac = MagicMock()
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    result = agents_sdk.cmd_agent_memory_delete("store_1", "mem_1", api_key="sk-test")

    mac.delete_memory.assert_not_called()
    assert result is None


def test_create_session_without_memory_store_omits_resources(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    fake_session = MagicMock(id="sess_1")
    client.client.beta.sessions.create.return_value = fake_session

    result = client.create_session("agent_1", "env_1", title="t")

    _, kwargs = client.client.beta.sessions.create.call_args
    assert kwargs["resources"] is None
    assert kwargs["betas"] == [agents_sdk.MANAGED_AGENTS_BETA]
    assert "vault_ids" not in kwargs
    assert result["memory_store_id"] is None


def test_create_session_with_memory_store_mounts_resource(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    fake_session = MagicMock(id="sess_2")
    client.client.beta.sessions.create.return_value = fake_session

    result = client.create_session("agent_1", "env_1", title="t",
                                    memory_store_id="store_123")

    _, kwargs = client.client.beta.sessions.create.call_args
    assert kwargs["resources"] == [
        {"type": "memory_store", "memory_store_id": "store_123"}
    ]
    assert agents_sdk.MEMORY_STORE_BETA in kwargs["betas"]
    assert result["memory_store_id"] == "store_123"


def test_cmd_managed_agent_run_creates_and_mounts_store_when_named(agents_sdk, monkeypatch, capsys):
    mac = MagicMock()
    mac.create_agent.return_value = {"id": "agent_1"}
    mac.create_environment.return_value = {"id": "env_1"}
    mac.create_memory_store.return_value = {"id": "store_1", "name": "notes"}
    mac.create_session.return_value = {"id": "sess_1"}
    mac.run_task.return_value = {"text": "done", "tool_calls": []}
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    agents_sdk.cmd_managed_agent_run("do the thing", api_key="sk-test",
                                     memory_store="notes")

    mac.create_memory_store.assert_called_once_with(name="notes")
    _, kwargs = mac.create_session.call_args
    assert kwargs["memory_store_id"] == "store_1"


def test_cmd_managed_agent_run_skips_store_when_not_named(agents_sdk, monkeypatch):
    mac = MagicMock()
    mac.create_agent.return_value = {"id": "agent_1"}
    mac.create_environment.return_value = {"id": "env_1"}
    mac.create_session.return_value = {"id": "sess_1"}
    mac.run_task.return_value = {"text": "done", "tool_calls": []}
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    agents_sdk.cmd_managed_agent_run("do the thing", api_key="sk-test")

    mac.create_memory_store.assert_not_called()
    _, kwargs = mac.create_session.call_args
    assert kwargs["memory_store_id"] is None


def test_cmd_agent_memory_store_create_standalone(agents_sdk, monkeypatch):
    mac = MagicMock()
    mac.create_memory_store.return_value = {"id": "store_9", "name": "shared"}
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    result = agents_sdk.cmd_agent_memory_store_create("shared", api_key="sk-test")

    mac.create_memory_store.assert_called_once_with(name="shared")
    assert result == {"id": "store_9", "name": "shared"}


# ── v1.20.0: Dreaming (research preview) ────────────────────────────────


def test_dreaming_beta_header_unchanged(agents_sdk):
    assert agents_sdk.DREAMING_BETA == "dreaming-2026-04-21"


def test_create_dream_sends_expected_inputs_and_betas(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    fake_dream = MagicMock(id="drm_1", status="pending")
    client.client.beta.dreams.create.return_value = fake_dream

    result = client.create_dream("store_1", session_ids=["sesn_1", "sesn_2"],
                                  model="zc-opus-4-8", instructions="focus on prefs")

    _, kwargs = client.client.beta.dreams.create.call_args
    assert kwargs["inputs"] == [
        {"type": "memory_store", "memory_store_id": "store_1"},
        {"type": "sessions", "session_ids": ["sesn_1", "sesn_2"]},
    ]
    assert kwargs["betas"] == [agents_sdk.MANAGED_AGENTS_BETA, agents_sdk.DREAMING_BETA]
    assert result == {"id": "drm_1", "status": "pending"}


def test_create_dream_without_sessions_omits_sessions_input(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.dreams.create.return_value = MagicMock(id="drm_2", status="pending")

    client.create_dream("store_1")

    _, kwargs = client.client.beta.dreams.create.call_args
    assert kwargs["inputs"] == [{"type": "memory_store", "memory_store_id": "store_1"}]


def test_get_dream_extracts_output_store_id(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    fake_output = MagicMock(type="memory_store", memory_store_id="store_curated")
    fake_dream = MagicMock(id="drm_1", status="completed", outputs=[fake_output], error=None)
    client.client.beta.dreams.retrieve.return_value = fake_dream

    result = client.get_dream("drm_1")

    assert result == {"id": "drm_1", "status": "completed",
                       "output_store_id": "store_curated", "error": None}


def test_get_dream_handles_no_outputs_yet(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    fake_dream = MagicMock(id="drm_1", status="pending", outputs=[], error=None)
    client.client.beta.dreams.retrieve.return_value = fake_dream

    result = client.get_dream("drm_1")

    assert result["output_store_id"] is None


def test_list_dreams_returns_id_and_status(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.dreams.list.return_value = [
        MagicMock(id="drm_1", status="completed"),
        MagicMock(id="drm_2", status="pending"),
    ]

    result = client.list_dreams()

    assert result == [{"id": "drm_1", "status": "completed"},
                       {"id": "drm_2", "status": "pending"}]


def test_cancel_dream(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.dreams.cancel.return_value = MagicMock(id="drm_1", status="canceled")

    result = client.cancel_dream("drm_1")

    assert result == {"id": "drm_1", "status": "canceled"}


def test_cmd_agent_dream_prints_and_returns(agents_sdk, monkeypatch, capsys):
    mac = MagicMock()
    mac.create_dream.return_value = {"id": "drm_1", "status": "pending"}
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    result = agents_sdk.cmd_agent_dream("store_1", api_key="sk-test")

    mac.create_dream.assert_called_once()
    assert result == {"id": "drm_1", "status": "pending"}
    assert "drm_1" in capsys.readouterr().out


def test_cmd_agent_dream_list_handles_empty(agents_sdk, monkeypatch, capsys):
    mac = MagicMock()
    mac.list_dreams.return_value = []
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    result = agents_sdk.cmd_agent_dream_list(api_key="sk-test")

    assert result == []
    assert "no dreams found" in capsys.readouterr().out


# ── v1.20.0: Outcomes (public beta) ─────────────────────────────────────


def test_define_outcome_sends_expected_event(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.sessions.events.send.return_value = {"ok": True}

    client.define_outcome("sess_1", "Build a DCF model", "## Rubric\n- has a price column",
                          max_iterations=5)

    _, kwargs = client.client.beta.sessions.events.send.call_args
    event = kwargs["events"][0]
    assert event["type"] == "user.define_outcome"
    assert event["description"] == "Build a DCF model"
    assert event["rubric"] == {"type": "text", "content": "## Rubric\n- has a price column"}
    assert event["max_iterations"] == 5
    assert kwargs["betas"] == [agents_sdk.MANAGED_AGENTS_BETA]


def test_define_outcome_default_max_iterations(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.sessions.events.send.return_value = {"ok": True}

    client.define_outcome("sess_1", "desc", "rubric text")

    _, kwargs = client.client.beta.sessions.events.send.call_args
    assert kwargs["events"][0]["max_iterations"] == 3


def test_cmd_managed_agent_run_with_outcome_calls_define_outcome_not_run_task(agents_sdk, monkeypatch):
    mac = MagicMock()
    mac.create_agent.return_value = {"id": "agent_1"}
    mac.create_environment.return_value = {"id": "env_1"}
    mac.create_memory_store.return_value = {"id": "store_1", "name": "notes"}
    mac.create_session.return_value = {"id": "sess_1"}
    mac.wait_for_outcome.return_value = {"text": "done", "result": "satisfied"}
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    result = agents_sdk.cmd_managed_agent_run(
        "unused task text", api_key="sk-test",
        outcome_description="Build a report", outcome_rubric="## has a table",
        outcome_max_iterations=7,
    )

    mac.define_outcome.assert_called_once_with(
        "sess_1", "Build a report",
        rubric_text="## has a table", rubric_file_id=None, max_iterations=7,
    )
    mac.run_task.assert_not_called()
    assert result == {"text": "done", "result": "satisfied"}


def test_cmd_managed_agent_run_without_outcome_calls_run_task(agents_sdk, monkeypatch):
    mac = MagicMock()
    mac.create_agent.return_value = {"id": "agent_1"}
    mac.create_environment.return_value = {"id": "env_1"}
    mac.create_session.return_value = {"id": "sess_1"}
    mac.run_task.return_value = {"text": "done", "tool_calls": []}
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    agents_sdk.cmd_managed_agent_run("plain task", api_key="sk-test")

    mac.define_outcome.assert_not_called()
    # run_task has taken stream_deltas since v1.22.0 (default False); this
    # assertion went stale when that param was added and started failing
    # here since — fixed as part of the v1.26.0 cycle while this file was
    # already open for self-hosted sandbox coverage.
    mac.run_task.assert_called_once_with("sess_1", "plain task", stream_deltas=False)


# ── v1.20.0: Webhooks (public beta) ─────────────────────────────────────


def test_register_webhook_sends_expected_payload(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.webhooks.create.return_value = MagicMock(id="wh_1")

    result = client.register_webhook("https://example.com/hook", event_types=["session.status_idle"])

    _, kwargs = client.client.beta.webhooks.create.call_args
    assert kwargs["url"] == "https://example.com/hook"
    assert kwargs["event_types"] == ["session.status_idle"]
    assert kwargs["betas"] == [agents_sdk.MANAGED_AGENTS_BETA]
    assert result == {"id": "wh_1", "url": "https://example.com/hook",
                       "event_types": ["session.status_idle"]}


def test_register_webhook_defaults_event_types_to_none(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.webhooks.create.return_value = MagicMock(id="wh_2")

    client.register_webhook("https://example.com/hook")

    _, kwargs = client.client.beta.webhooks.create.call_args
    assert kwargs["event_types"] is None


def test_cmd_agent_webhook_register_prints_and_returns(agents_sdk, monkeypatch, capsys):
    mac = MagicMock()
    mac.register_webhook.return_value = {"id": "wh_1", "url": "https://x.test/h",
                                          "event_types": None}
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    result = agents_sdk.cmd_agent_webhook_register("https://x.test/h", api_key="sk-test")

    assert result["id"] == "wh_1"
    assert "wh_1" in capsys.readouterr().out


# ── v1.22.0: Session-level overrides (public beta) ───────────────────────


def test_create_session_without_overrides_sends_bare_agent_id(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.sessions.create.return_value = MagicMock(id="sess_1")

    result = client.create_session("agent_1", "env_1", title="t")

    _, kwargs = client.client.beta.sessions.create.call_args
    assert kwargs["agent"] == "agent_1"
    assert result["agent_overrides"] is None


def test_create_session_with_overrides_builds_agent_with_overrides(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.sessions.create.return_value = MagicMock(id="sess_2")
    overrides = {"model": {"id": "zc-xxx"}, "system": None, "tools": []}

    result = client.create_session("agent_1", "env_1", title="t", agent_overrides=overrides)

    _, kwargs = client.client.beta.sessions.create.call_args
    assert kwargs["agent"] == {
        "type": "agent_with_overrides", "id": "agent_1",
        "model": {"id": "zc-xxx"}, "system": None, "tools": [],
    }
    assert result["agent_overrides"] == overrides


def test_cmd_managed_agent_run_merges_override_model_and_system(agents_sdk, monkeypatch):
    mac = MagicMock()
    mac.create_agent.return_value = {"id": "agent_1"}
    mac.create_environment.return_value = {"id": "env_1"}
    mac.create_session.return_value = {"id": "sess_1"}
    mac.run_task.return_value = {"text": "done", "tool_calls": []}
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    agents_sdk.cmd_managed_agent_run(
        "task", api_key="sk-test",
        agent_overrides={"model": "zc-xxx", "system": "be terse"},
    )

    _, kwargs = mac.create_session.call_args
    assert kwargs["agent_overrides"] == {"model": "zc-xxx", "system": "be terse"}


def test_cmd_managed_agent_run_without_overrides_passes_none(agents_sdk, monkeypatch):
    mac = MagicMock()
    mac.create_agent.return_value = {"id": "agent_1"}
    mac.create_environment.return_value = {"id": "env_1"}
    mac.create_session.return_value = {"id": "sess_1"}
    mac.run_task.return_value = {"text": "done", "tool_calls": []}
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    agents_sdk.cmd_managed_agent_run("task", api_key="sk-test")

    _, kwargs = mac.create_session.call_args
    assert kwargs["agent_overrides"] is None


# ── v1.22.0: Vault credential injection_location (public beta) ──────────


def test_add_credential_environment_variable_with_injection_location(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.vaults.credentials.create.return_value = MagicMock(id="cred_1")

    client.add_credential(
        "vault_1", "environment_variable",
        secret_name="NOTION_API_KEY", secret_value="secret",
        allowed_domains=["api.notion.com"], injection_location="headers",
    )

    _, kwargs = client.client.beta.vaults.credentials.create.call_args
    assert kwargs["auth"]["injection_location"] == "headers"


def test_add_credential_omits_injection_location_when_not_given(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.vaults.credentials.create.return_value = MagicMock(id="cred_2")

    client.add_credential(
        "vault_1", "environment_variable",
        secret_name="NOTION_API_KEY", secret_value="secret",
        allowed_domains=["api.notion.com"],
    )

    _, kwargs = client.client.beta.vaults.credentials.create.call_args
    assert "injection_location" not in kwargs["auth"]


def test_add_credential_rejects_injection_location_for_mcp_oauth(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    with pytest.raises(ValueError, match="injection_location is only valid"):
        client.add_credential("vault_1", "mcp_oauth", mcp_server_url="https://x",
                              secret_value="tok", injection_location="headers")


def test_add_credential_rejects_invalid_injection_location(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    with pytest.raises(ValueError, match="must be one of"):
        client.add_credential("vault_1", "environment_variable",
                              secret_name="X", secret_value="v",
                              allowed_domains=["a.com"], injection_location="bogus")


@pytest.mark.parametrize("loc", ["headers", "body", "both"])
def test_add_credential_accepts_all_valid_injection_locations(agents_sdk, loc):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.vaults.credentials.create.return_value = MagicMock(id="cred_3")

    client.add_credential("vault_1", "environment_variable",
                          secret_name="X", secret_value="v",
                          allowed_domains=["a.com"], injection_location=loc)

    _, kwargs = client.client.beta.vaults.credentials.create.call_args
    assert kwargs["auth"]["injection_location"] == loc


def test_cmd_agent_vault_add_credential_threads_injection_location(agents_sdk, monkeypatch):
    mac = MagicMock()
    mac.add_credential.return_value = {"id": "cred_1", "vault_id": "vault_1",
                                       "credential_type": "environment_variable",
                                       "mcp_server_url": None, "secret_name": "X"}
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    agents_sdk.cmd_agent_vault_add_credential(
        "vault_1", "environment_variable", api_key="sk-test",
        secret_name="X", secret_value="v", allowed_domains=["a.com"],
        injection_location="body",
    )

    _, kwargs = mac.add_credential.call_args
    assert kwargs["injection_location"] == "body"


# ── v1.22.0: Session event deltas (public beta) ──────────────────────────


class _FakeEvent:
    def __init__(self, type_, **kw):
        self.type = type_
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeBlock:
    def __init__(self, text):
        self.text = text


def _fake_stream_cm(events):
    cm = MagicMock()
    cm.__enter__.return_value = events
    cm.__exit__.return_value = False
    return cm


def test_run_task_default_omits_event_deltas(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    events = [_FakeEvent("agent.message", content=[_FakeBlock("hi")]),
              _FakeEvent("session.status_idle")]
    client.client.beta.sessions.events.stream.return_value = _fake_stream_cm(events)
    client.client.beta.sessions.events.send.return_value = {}

    result = client.run_task("sess_1", "do it")

    _, kwargs = client.client.beta.sessions.events.stream.call_args
    assert "event_deltas" not in kwargs
    assert result["text"] == "hi"


def test_run_task_stream_deltas_sends_event_deltas_param(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    events = [_FakeEvent("agent.message", content=[_FakeBlock("hi")]),
              _FakeEvent("session.status_idle")]
    client.client.beta.sessions.events.stream.return_value = _fake_stream_cm(events)
    client.client.beta.sessions.events.send.return_value = {}

    client.run_task("sess_1", "do it", stream_deltas=True)

    _, kwargs = client.client.beta.sessions.events.stream.call_args
    assert kwargs["event_deltas"] == ["text"]


def test_run_task_event_delta_prints_live_without_altering_returned_text(agents_sdk, capsys):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    events = [
        _FakeEvent("event_start"),
        _FakeEvent("event_delta", text="par"),
        _FakeEvent("event_delta", text="tial"),
        _FakeEvent("agent.message", content=[_FakeBlock("complete text")]),
        _FakeEvent("session.status_idle"),
    ]
    client.client.beta.sessions.events.stream.return_value = _fake_stream_cm(events)
    client.client.beta.sessions.events.send.return_value = {}

    result = client.run_task("sess_1", "do it", stream_deltas=True)

    assert result["text"] == "complete text"
    assert "partial" in capsys.readouterr().out


def test_wait_for_outcome_default_omits_event_deltas(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    events = [_FakeEvent("agent.message", content=[_FakeBlock("hi")]),
              _FakeEvent("span.outcome_evaluation_end", result="satisfied"),
              _FakeEvent("session.status_idle")]
    client.client.beta.sessions.events.stream.return_value = _fake_stream_cm(events)

    result = client.wait_for_outcome("sess_1")

    _, kwargs = client.client.beta.sessions.events.stream.call_args
    assert "event_deltas" not in kwargs
    assert result == {"text": "hi", "result": "satisfied"}


def test_wait_for_outcome_stream_deltas_sends_event_deltas_param(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    events = [_FakeEvent("agent.message", content=[_FakeBlock("hi")]),
              _FakeEvent("span.outcome_evaluation_end", result="satisfied"),
              _FakeEvent("session.status_idle")]
    client.client.beta.sessions.events.stream.return_value = _fake_stream_cm(events)

    client.wait_for_outcome("sess_1", stream_deltas=True)

    _, kwargs = client.client.beta.sessions.events.stream.call_args
    assert kwargs["event_deltas"] == ["text"]


def test_cmd_managed_agent_run_threads_stream_deltas_into_run_task(agents_sdk, monkeypatch):
    mac = MagicMock()
    mac.create_agent.return_value = {"id": "agent_1"}
    mac.create_environment.return_value = {"id": "env_1"}
    mac.create_session.return_value = {"id": "sess_1"}
    mac.run_task.return_value = {"text": "done", "tool_calls": []}
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    agents_sdk.cmd_managed_agent_run("task", api_key="sk-test", stream_deltas=True)

    _, kwargs = mac.run_task.call_args
    assert kwargs["stream_deltas"] is True


def test_cmd_managed_agent_run_threads_stream_deltas_into_wait_for_outcome(agents_sdk, monkeypatch):
    mac = MagicMock()
    mac.create_agent.return_value = {"id": "agent_1"}
    mac.create_environment.return_value = {"id": "env_1"}
    mac.create_session.return_value = {"id": "sess_1"}
    mac.wait_for_outcome.return_value = {"text": "done", "result": "satisfied"}
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    agents_sdk.cmd_managed_agent_run(
        "unused", api_key="sk-test", outcome_description="Build a report",
        outcome_rubric="rubric text", stream_deltas=True,
    )

    _, kwargs = mac.wait_for_outcome.call_args
    assert kwargs["stream_deltas"] is True


# ── v1.24.0: Managed Agents memory listing ───────────────────────────────


def test_list_memories_sends_expected_params_and_betas(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.memory_stores.memories.list.return_value = {
        "data": [{"path": "notes/a.md"}], "has_more": False,
    }

    result = client.list_memories("store_1", path_prefix="notes/", depth=1, limit=10)

    args, kwargs = client.client.beta.memory_stores.memories.list.call_args
    assert args[0] == "store_1"
    assert kwargs["betas"] == [agents_sdk.MEMORY_STORE_BETA]
    assert kwargs["path_prefix"] == "notes/"
    assert kwargs["depth"] == 1
    assert kwargs["limit"] == 10
    assert result["memory_store_id"] == "store_1"
    assert result["raw"]["data"][0]["path"] == "notes/a.md"


def test_list_memories_omits_optional_params_when_not_given(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.memory_stores.memories.list.return_value = {"data": []}

    client.list_memories("store_1")

    _, kwargs = client.client.beta.memory_stores.memories.list.call_args
    assert "path_prefix" not in kwargs
    assert "depth" not in kwargs
    assert "page" not in kwargs
    assert kwargs["limit"] == 50


@pytest.mark.parametrize("bad_depth", [2, -1, 5])
def test_list_memories_rejects_invalid_depth(agents_sdk, bad_depth):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    with pytest.raises(ValueError, match="depth must be"):
        client.list_memories("store_1", depth=bad_depth)


@pytest.mark.parametrize("good_depth", [0, 1])
def test_list_memories_accepts_valid_depth(agents_sdk, good_depth):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.memory_stores.memories.list.return_value = {"data": []}

    client.list_memories("store_1", depth=good_depth)

    _, kwargs = client.client.beta.memory_stores.memories.list.call_args
    assert kwargs["depth"] == good_depth


def test_list_memories_rejects_path_prefix_without_trailing_slash(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    with pytest.raises(ValueError, match="must end with"):
        client.list_memories("store_1", path_prefix="notes")


def test_list_memories_accepts_path_prefix_with_trailing_slash(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    client.client.beta.memory_stores.memories.list.return_value = {"data": []}

    client.list_memories("store_1", path_prefix="notes/sub/")

    _, kwargs = client.client.beta.memory_stores.memories.list.call_args
    assert kwargs["path_prefix"] == "notes/sub/"


def test_cmd_agent_memory_list_prints_paths(agents_sdk, monkeypatch, capsys):
    mac = MagicMock()
    mac.list_memories.return_value = {
        "memory_store_id": "store_1", "path_prefix": None, "depth": None,
        "raw": {"data": [{"path": "a.md"}, {"path": "b.md"}]},
    }
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    result = agents_sdk.cmd_agent_memory_list("store_1", api_key="sk-test")

    out = capsys.readouterr().out
    assert "a.md" in out
    assert "b.md" in out
    assert result["memory_store_id"] == "store_1"


def test_cmd_agent_memory_list_handles_empty(agents_sdk, monkeypatch, capsys):
    mac = MagicMock()
    mac.list_memories.return_value = {
        "memory_store_id": "store_1", "path_prefix": None, "depth": None,
        "raw": {"data": []},
    }
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    agents_sdk.cmd_agent_memory_list("store_1", api_key="sk-test")

    out = capsys.readouterr().out
    assert "no memories found" in out


# ── v1.26.0: Self-hosted sandboxes (public beta) ─────────────────────────


def test_create_environment_defaults_to_cloud(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    fake_env = MagicMock(id="env_1")
    client.client.beta.environments.create.return_value = fake_env

    result = client.create_environment(name="my-env")

    _, kwargs = client.client.beta.environments.create.call_args
    assert kwargs["config"] == {"type": "cloud", "networking": {"type": "unrestricted"}}
    assert result == {"id": "env_1", "name": "my-env", "type": "cloud"}


def test_create_environment_self_hosted_config_has_no_networking_field(agents_sdk):
    # {"type": "self_hosted"} is the *entire* config — no pool, capacity,
    # or networking sub-fields, unlike the cloud config. Passing
    # networking anyway must not leak into the self-hosted payload.
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    fake_env = MagicMock(id="env_2")
    client.client.beta.environments.create.return_value = fake_env

    result = client.create_environment(name="sh-env", env_type="self_hosted",
                                       networking="limited")

    _, kwargs = client.client.beta.environments.create.call_args
    assert kwargs["config"] == {"type": "self_hosted"}
    assert result == {"id": "env_2", "name": "sh-env", "type": "self_hosted"}


def test_get_environment_work_stats_shapes_response(agents_sdk):
    client = agents_sdk.ManagedAgentsClient(api_key="sk-test")
    fake_stats = MagicMock(depth=3, pending=1, oldest_queued_at="2026-07-13T00:00:00Z",
                           workers_polling=2)
    client.client.beta.environments.work.stats.return_value = fake_stats

    result = client.get_environment_work_stats("env_1")

    client.client.beta.environments.work.stats.assert_called_once_with("env_1")
    assert result == {
        "depth": 3, "pending": 1,
        "oldest_queued_at": "2026-07-13T00:00:00Z", "workers_polling": 2,
    }


def test_cmd_agent_env_self_hosted_create_prints_next_steps(agents_sdk, monkeypatch, capsys):
    mac = MagicMock()
    mac.create_environment.return_value = {"id": "env_9", "name": "sh", "type": "self_hosted"}
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    result = agents_sdk.cmd_agent_env_self_hosted_create("sh", api_key="sk-test")

    mac.create_environment.assert_called_once_with(name="sh", env_type="self_hosted")
    out = capsys.readouterr().out
    assert "env_9" in out
    assert "Generate environment key" in out
    assert result["id"] == "env_9"


def test_cmd_agent_env_work_stats_warns_when_no_workers(agents_sdk, monkeypatch, capsys):
    mac = MagicMock()
    mac.get_environment_work_stats.return_value = {
        "depth": 0, "pending": 0, "oldest_queued_at": None, "workers_polling": 0,
    }
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    agents_sdk.cmd_agent_env_work_stats("env_1", api_key="sk-test")

    out = capsys.readouterr().out
    assert "no worker has polled" in out


def test_cmd_agent_env_work_stats_no_warning_when_workers_active(agents_sdk, monkeypatch, capsys):
    mac = MagicMock()
    mac.get_environment_work_stats.return_value = {
        "depth": 0, "pending": 1, "oldest_queued_at": None, "workers_polling": 1,
    }
    monkeypatch.setattr(agents_sdk, "ManagedAgentsClient", lambda api_key: mac)

    agents_sdk.cmd_agent_env_work_stats("env_1", api_key="sk-test")

    out = capsys.readouterr().out
    assert "no worker has polled" not in out
