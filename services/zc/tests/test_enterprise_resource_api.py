"""End-to-end contracts for specialized CLI resource migrations."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx
import pytest

import app.core.config as config_module
from app.core.auth import create_short_lived_token
from app.core.config import Config
from app.main import app
from app.models.ai import AIResponse
from app.services.domain_resources import (
    DomainResourceService,
    get_domain_resource_service,
)
from app.services.resource_store import ResourceStore


class FakeAIService:
    """Offline AI boundary shared by all migrated domain tests."""

    async def create_response(self, request):
        output = f"generated:{request.prompt[:80]}"
        if "Return a JSON array" in request.prompt:
            output = (
                '[{"title":"Generated task","description":"From plan",'
                '"agent":"full_stack","priority":"medium"}]'
            )
        return AIResponse(
            id="air_test",
            created_at=datetime.now(timezone.utc),
            model=request.model or "test-model",
            output_text=output,
        )


class FakeEncryptor:
    def encrypt_string(self, value: str) -> str:
        return f"encrypted:{len(value)}"


@pytest.fixture
def resource_service(tmp_path, monkeypatch) -> DomainResourceService:
    async def immediate_to_thread(function, /, *args, **kwargs):
        return function(*args, **kwargs)

    config = Config(
        environment="test",
        redis_enabled=False,
        nats_enabled=False,
        protobuf_enabled=False,
        upload_temp_dir=tmp_path,
        storage_backend="local",
        jwt_secret="a-test-secret-with-sufficient-entropy",
        auth_required=True,
        rate_limit_enabled=False,
    )
    monkeypatch.setattr(config_module, "_config", config)
    monkeypatch.setattr(asyncio, "to_thread", immediate_to_thread)
    service = DomainResourceService(
        ResourceStore(tmp_path / "resources.sqlite3"),
        ai_service=FakeAIService(),
        blob_root=tmp_path / "blobs",
        encryptor=FakeEncryptor(),
    )
    async def fake_resource_service() -> DomainResourceService:
        return service

    app.dependency_overrides[get_domain_resource_service] = fake_resource_service
    yield service
    app.dependency_overrides.pop(get_domain_resource_service, None)


def headers(tenant: str, role: str = "developer") -> dict[str, str]:
    token = create_short_lived_token(tenant, role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_projects_tasks_and_tenant_isolation(
    resource_service: DomainResourceService,
) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/v1/projects",
            json={"name": "API migration", "template": "blank"},
            headers=headers("tenant-a"),
        )
        assert created.status_code == 201
        project = created.json()["data"]
        assert created.headers["location"] == f"/v1/projects/{project['id']}"

        hidden = await client.get(
            f"/v1/projects/{project['id']}", headers=headers("tenant-b")
        )
        assert hidden.status_code == 404

        task_response = await client.post(
            f"/v1/projects/{project['id']}/tasks",
            json={
                "title": "Implement boundary",
                "agent": "code_reviewer",
                "priority": "high",
            },
            headers=headers("tenant-a"),
        )
        assert task_response.status_code == 201
        task = task_response.json()["data"]

        run = await client.post(
            f"/v1/projects/{project['id']}/tasks/{task['id']}/runs",
            json={},
            headers=headers("tenant-a"),
        )
        assert run.status_code == 201
        assert run.json()["data"]["status"] == "done"

        listing = await client.get("/v1/projects", headers=headers("tenant-a"))
        assert listing.json()["meta"]["total"] == 1

        plan = await client.post(
            f"/v1/projects/{project['id']}/plans",
            json={},
            headers=headers("tenant-a"),
        )
        assert plan.status_code == 201
        assert len(plan.json()["data"]["tasks"]) == 2


@pytest.mark.asyncio
async def test_artifact_versions_and_research_resources(
    resource_service: DomainResourceService,
) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        artifact_response = await client.post(
            "/v1/artifacts",
            json={"name": "service.py", "content": "version one"},
            headers=headers("tenant-a"),
        )
        assert artifact_response.status_code == 201
        artifact = artifact_response.json()["data"]
        assert artifact["current_version"] == 1

        iteration = await client.post(
            f"/v1/artifacts/{artifact['id']}/versions",
            json={"feedback": "Add validation"},
            headers=headers("tenant-a"),
        )
        assert iteration.status_code == 201
        assert iteration.json()["data"]["current_version"] == 2
        assert len(iteration.json()["data"]["versions"]) == 2

        diff = await client.get(
            f"/v1/artifacts/{artifact['id']}/diff",
            params={"from_version": 1, "to_version": 2},
            headers=headers("tenant-a"),
        )
        assert diff.status_code == 200
        assert diff.json()["data"]["from_version"] == 1

        research = await client.post(
            "/v1/research-reports",
            json={
                "topic": "Tenant isolation",
                "depth": 3,
                "source_urls": ["https://example.com/reference"],
            },
            headers=headers("tenant-a"),
        )
        assert research.status_code == 201
        assert research.json()["data"]["status"] == "completed"
        assert research.json()["data"]["report"].startswith("generated:")


@pytest.mark.asyncio
async def test_file_lifecycle_question_and_private_storage_path(
    resource_service: DomainResourceService,
) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        uploaded = await client.post(
            "/v1/files",
            files={"upload": ("notes.txt", b"tenant private notes", "text/plain")},
            headers=headers("tenant-a"),
        )
        assert uploaded.status_code == 201
        metadata = uploaded.json()["data"]
        assert "blob_path" not in metadata

        forbidden = await client.get(
            f"/v1/files/{metadata['id']}/content",
            headers=headers("tenant-b"),
        )
        assert forbidden.status_code == 404

        downloaded = await client.get(
            f"/v1/files/{metadata['id']}/content",
            headers=headers("tenant-a"),
        )
        assert downloaded.status_code == 200
        assert downloaded.content == b"tenant private notes"

        answer = await client.post(
            f"/v1/files/{metadata['id']}/questions",
            json={"prompt": "Summarize"},
            headers=headers("tenant-a"),
        )
        assert answer.status_code == 201
        assert answer.json()["data"]["output_text"].startswith("generated:")

        deleted = await client.delete(
            f"/v1/files/{metadata['id']}", headers=headers("tenant-a")
        )
        assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_file_rejects_unsafe_filename(
    resource_service: DomainResourceService,
) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/files",
            files={"upload": ("bad<name.txt", b"unsafe", "text/plain")},
            headers=headers("tenant-a"),
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "domain_validation_error"


@pytest.mark.asyncio
async def test_managed_agent_runs_and_memory_lifecycle(
    resource_service: DomainResourceService,
) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        store_response = await client.post(
            "/v1/memory-stores",
            json={"name": "project context"},
            headers=headers("tenant-a"),
        )
        store = store_response.json()["data"]

        memory_response = await client.post(
            f"/v1/memory-stores/{store['id']}/memories",
            json={"path": "architecture/decision", "content": "Use resource APIs"},
            headers=headers("tenant-a"),
        )
        assert memory_response.status_code == 201
        memory = memory_response.json()["data"]

        updated = await client.patch(
            f"/v1/memory-stores/{store['id']}/memories/{memory['id']}",
            json={"content": "Use tenant-scoped resource APIs"},
            headers=headers("tenant-a"),
        )
        assert updated.status_code == 200

        run = await client.post(
            "/v1/managed-agent-runs",
            json={
                "task": "Review the architecture",
                "agent": "code_reviewer",
                "memory_store_id": store["id"],
            },
            headers=headers("tenant-a"),
        )
        assert run.status_code == 201
        assert run.json()["data"]["status"] == "completed"

        hidden = await client.get(
            f"/v1/managed-agent-runs/{run.json()['data']['id']}",
            headers=headers("tenant-b"),
        )
        assert hidden.status_code == 404

        archived = await client.post(
            f"/v1/memory-stores/{store['id']}/archive",
            headers=headers("tenant-a"),
        )
        assert archived.json()["data"]["status"] == "archived"


@pytest.mark.asyncio
async def test_viewer_is_read_only(resource_service: DomainResourceService) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        denied = await client.post(
            "/v1/projects",
            json={"name": "denied"},
            headers=headers("tenant-a", "viewer"),
        )
        allowed = await client.get(
            "/v1/projects", headers=headers("tenant-a", "viewer")
        )

    assert denied.status_code == 403
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_extended_managed_agent_resources_hide_vault_secrets(
    resource_service: DomainResourceService,
) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        vault_response = await client.post(
            "/v1/agent-vaults",
            json={"display_name": "deployment credentials"},
            headers=headers("tenant-a", "admin"),
        )
        vault = vault_response.json()["data"]
        credential = await client.post(
            f"/v1/agent-vaults/{vault['id']}/credentials",
            json={
                "credential_type": "environment_variable",
                "secret_value": "never-return-this",
                "secret_name": "DEPLOY_TOKEN",
                "allowed_domains": ["example.com"],
                "injection_location": "headers",
            },
            headers=headers("tenant-a", "admin"),
        )
        assert credential.status_code == 201
        assert "secret_value" not in credential.text
        assert "encrypted_secret" not in credential.text
        listed_vaults = await client.get(
            "/v1/agent-vaults", headers=headers("tenant-a", "admin")
        )
        assert "never-return-this" not in listed_vaults.text
        assert "encrypted_secret" not in listed_vaults.text

        environment = await client.post(
            "/v1/agent-environments",
            json={"name": "local-worker"},
            headers=headers("tenant-a", "admin"),
        )
        environment_id = environment.json()["data"]["id"]
        schedule = await client.post(
            "/v1/agent-schedules",
            json={
                "agent_id": "agent-a",
                "environment_id": environment_id,
                "cron_expression": "0 * * * *",
                "timezone": "UTC",
                "task": "Review queued work",
            },
            headers=headers("tenant-a", "admin"),
        )
        assert schedule.status_code == 201
        cancelled = await client.post(
            f"/v1/agent-schedules/{schedule.json()['data']['id']}/cancel",
            headers=headers("tenant-a", "admin"),
        )
        assert cancelled.json()["data"]["status"] == "cancelled"

        webhook = await client.post(
            "/v1/agent-webhooks",
            json={"url": "https://example.com/events", "event_types": ["run.completed"]},
            headers=headers("tenant-a", "admin"),
        )
        assert webhook.status_code == 201
        insecure = await client.post(
            "/v1/agent-webhooks",
            json={"url": "http://example.com/events"},
            headers=headers("tenant-a", "admin"),
        )
        assert insecure.status_code == 422


@pytest.mark.asyncio
async def test_dream_and_multiagent_review_are_resource_backed(
    resource_service: DomainResourceService,
) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        store = (
            await client.post(
                "/v1/memory-stores",
                json={"name": "dream source"},
                headers=headers("tenant-a"),
            )
        ).json()["data"]
        await client.post(
            f"/v1/memory-stores/{store['id']}/memories",
            json={"path": "facts/a", "content": "A durable fact"},
            headers=headers("tenant-a"),
        )
        dream = await client.post(
            "/v1/agent-dreams",
            json={"memory_store_id": store["id"], "instructions": "Deduplicate"},
            headers=headers("tenant-a"),
        )
        assert dream.status_code == 201
        assert dream.json()["data"]["status"] == "completed"
        assert dream.json()["data"]["output_store_id"].startswith("mems_")

        uploaded = (
            await client.post(
                "/v1/files",
                files={"upload": ("service.py", b"def run(): pass", "text/x-python")},
                headers=headers("tenant-a"),
            )
        ).json()["data"]
        review = await client.post(
            "/v1/multi-agent-reviews",
            json={
                "file_id": uploaded["id"],
                "specialists": ["security", "style", "test-coverage"],
            },
            headers=headers("tenant-a"),
        )
        assert review.status_code == 201
        assert set(review.json()["data"]["findings"]) == {
            "security",
            "style",
            "test-coverage",
        }
