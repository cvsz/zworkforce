"""Resource APIs replacing specialized legacy CLI subcommands."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import StreamingResponse

from ...core.auth import Principal, require_roles
from ...models.domain_resources import (
    ArtifactCreate,
    ArtifactIteration,
    ArtifactPatch,
    DreamCreate,
    EnvironmentCreate,
    FileQuestion,
    ManagedAgentRunCreate,
    MemoryCreate,
    MemoryPatch,
    MultiAgentReviewCreate,
    MemoryStoreCreate,
    ProjectCreate,
    ProjectPlanCreate,
    ProjectPatch,
    ProjectTaskRunCreate,
    ResearchCreate,
    ScheduleCreate,
    TaskCreate,
    TaskPatch,
    VaultCreate,
    VaultCredentialCreate,
    WebhookCreate,
)
from ...services.domain_resources import (
    DomainResourceService,
    get_domain_resource_service,
)

router = APIRouter(prefix="/v1", tags=["migrated CLI resources"])
_read = require_roles("admin", "developer", "agent", "cli_service", "viewer")
_write = require_roles("admin", "developer", "agent", "cli_service")
_admin = require_roles("admin", "developer")


def _page(data: list[dict[str, Any]], total: int, limit: int, offset: int) -> dict:
    return {
        "data": data,
        "meta": {"total": total, "limit": limit, "offset": offset},
    }


@router.post("/projects", status_code=201)
async def create_project(
    request: ProjectCreate,
    response: Response,
    principal: Principal = Depends(_write),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    item = await service.create_project(principal.tenant_id, request)
    response.headers["Location"] = f"/v1/projects/{item['id']}"
    return {"data": item}


@router.get("/project-templates")
async def list_project_templates(
    _principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    return {"data": sorted(service._templates())}


@router.get("/projects")
async def list_projects(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    items, total = await service.store.list(
        principal.tenant_id, "projects", limit=limit, offset=offset
    )
    return _page(items, total, limit, offset)


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    return {
        "data": await service.store.get(
            principal.tenant_id, "projects", project_id
        )
    }


@router.patch("/projects/{project_id}")
async def patch_project(
    project_id: str,
    request: ProjectPatch,
    principal: Principal = Depends(_write),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    return {
        "data": await service.patch_project(
            principal.tenant_id, project_id, request
        )
    }


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    principal: Principal = Depends(_admin),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> Response:
    await service.store.delete(principal.tenant_id, "projects", project_id)
    return Response(status_code=204)


@router.post("/projects/{project_id}/tasks", status_code=201)
async def create_project_task(
    project_id: str,
    request: TaskCreate,
    response: Response,
    principal: Principal = Depends(_write),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    task = await service.add_task(principal.tenant_id, project_id, request)
    response.headers["Location"] = f"/v1/projects/{project_id}/tasks/{task['id']}"
    return {"data": task}


@router.post("/projects/{project_id}/plans", status_code=201)
async def create_project_plan(
    project_id: str,
    request: ProjectPlanCreate,
    principal: Principal = Depends(_write),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    return {
        "data": await service.plan_project(
            principal.tenant_id, project_id, request
        )
    }


@router.patch("/projects/{project_id}/tasks/{task_id}")
async def patch_project_task(
    project_id: str,
    task_id: str,
    request: TaskPatch,
    principal: Principal = Depends(_write),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    return {
        "data": await service.patch_task(
            principal.tenant_id, project_id, task_id, request
        )
    }


@router.post("/projects/{project_id}/tasks/{task_id}/runs", status_code=201)
async def run_project_task(
    project_id: str,
    task_id: str,
    request: ProjectTaskRunCreate,
    principal: Principal = Depends(_write),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    return {
        "data": await service.run_task(
            principal.tenant_id, project_id, task_id, request.model
        )
    }


@router.post("/artifacts", status_code=201)
async def create_artifact(
    request: ArtifactCreate,
    response: Response,
    principal: Principal = Depends(_write),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    item = await service.create_artifact(principal.tenant_id, request)
    response.headers["Location"] = f"/v1/artifacts/{item['id']}"
    return {"data": item}


@router.get("/artifacts")
async def list_artifacts(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    artifact_type: str | None = Query(None, max_length=64),
    project_id: str | None = Query(None, max_length=64),
    tag: str | None = Query(None, max_length=100),
    q: str | None = Query(None, max_length=500),
    principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    all_items, _ = await service.store.list(
        principal.tenant_id, "artifacts", limit=10_000, offset=0
    )
    filtered = [
        item
        for item in all_items
        if (artifact_type is None or item["artifact_type"] == artifact_type)
        and (project_id is None or item.get("project_id") == project_id)
        and (tag is None or tag in item.get("tags", []))
        and (
            q is None
            or q.casefold() in item["name"].casefold()
            or q.casefold() in item["versions"][-1]["content"].casefold()
        )
    ]
    return _page(filtered[offset : offset + limit], len(filtered), limit, offset)


@router.get("/artifact-types")
async def list_artifact_types(
    _principal: Principal = Depends(_read),
) -> dict:
    return {
        "data": [
            "code",
            "document",
            "config",
            "test",
            "schema",
            "prompt",
            "data",
            "other",
        ]
    }


@router.get("/artifacts/{artifact_id}")
async def get_artifact(
    artifact_id: str,
    principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    return {
        "data": await service.store.get(
            principal.tenant_id, "artifacts", artifact_id
        )
    }


@router.patch("/artifacts/{artifact_id}")
async def patch_artifact(
    artifact_id: str,
    request: ArtifactPatch,
    principal: Principal = Depends(_write),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    return {
        "data": await service.patch_artifact(
            principal.tenant_id, artifact_id, request
        )
    }


@router.post("/artifacts/{artifact_id}/versions", status_code=201)
async def iterate_artifact(
    artifact_id: str,
    request: ArtifactIteration,
    principal: Principal = Depends(_write),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    return {
        "data": await service.iterate_artifact(
            principal.tenant_id, artifact_id, request
        )
    }


@router.get("/artifacts/{artifact_id}/diff")
async def get_artifact_diff(
    artifact_id: str,
    from_version: int = Query(ge=1),
    to_version: int = Query(ge=1),
    principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    return {
        "data": await service.artifact_diff(
            principal.tenant_id, artifact_id, from_version, to_version
        )
    }


@router.delete("/artifacts/{artifact_id}", status_code=204)
async def delete_artifact(
    artifact_id: str,
    principal: Principal = Depends(_admin),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> Response:
    await service.store.delete(principal.tenant_id, "artifacts", artifact_id)
    return Response(status_code=204)


@router.post("/research-reports", status_code=201)
async def create_research_report(
    request: ResearchCreate,
    response: Response,
    principal: Principal = Depends(_write),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    item = await service.create_research(principal.tenant_id, request)
    response.headers["Location"] = f"/v1/research-reports/{item['id']}"
    return {"data": item}


@router.get("/research-reports")
async def list_research_reports(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    items, total = await service.store.list(
        principal.tenant_id, "research", limit=limit, offset=offset
    )
    return _page(items, total, limit, offset)


@router.get("/research-reports/{report_id}")
async def get_research_report(
    report_id: str,
    principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    return {
        "data": await service.store.get(
            principal.tenant_id, "research", report_id
        )
    }


@router.delete("/research-reports/{report_id}", status_code=204)
async def delete_research_report(
    report_id: str,
    principal: Principal = Depends(_admin),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> Response:
    await service.store.delete(principal.tenant_id, "research", report_id)
    return Response(status_code=204)


@router.post("/files", status_code=201)
async def create_file(
    response: Response,
    upload: UploadFile = File(...),
    principal: Principal = Depends(_write),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    from app.core.config import get_config

    maximum = get_config().max_message_size
    content = bytearray()
    while chunk := await upload.read(1024 * 1024):
        content.extend(chunk)
        if len(content) > maximum:
            raise ValueError("file exceeds the API upload limit")
    item = await service.create_file(
        principal.tenant_id,
        upload.filename or "",
        upload.content_type,
        bytes(content),
    )
    response.headers["Location"] = f"/v1/files/{item['id']}"
    item.pop("blob_path", None)
    return {"data": item}


@router.get("/files")
async def list_files(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    items, total = await service.store.list(
        principal.tenant_id, "files", limit=limit, offset=offset
    )
    for item in items:
        item.pop("blob_path", None)
    return _page(items, total, limit, offset)


@router.get("/files/{file_id}")
async def get_file(
    file_id: str,
    principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    item = await service.store.get(principal.tenant_id, "files", file_id)
    item.pop("blob_path", None)
    return {"data": item}


@router.get("/files/{file_id}/content")
async def download_file(
    file_id: str,
    principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> StreamingResponse:
    metadata, data = await service.file_content(principal.tenant_id, file_id)

    async def content_stream() -> AsyncIterator[bytes]:
        yield data

    return StreamingResponse(
        content_stream(),
        media_type=metadata["content_type"],
        headers={
            "Content-Disposition": (
                "attachment; filename*=UTF-8''"
                f"{quote(metadata['filename'], safe='')}"
            )
        },
    )


@router.post("/files/{file_id}/questions", status_code=201)
async def ask_file(
    file_id: str,
    request: FileQuestion,
    principal: Principal = Depends(_write),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    return {
        "data": await service.ask_file(principal.tenant_id, file_id, request)
    }


@router.delete("/files/{file_id}", status_code=204)
async def delete_file(
    file_id: str,
    principal: Principal = Depends(_admin),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> Response:
    await service.delete_file(principal.tenant_id, file_id)
    return Response(status_code=204)


@router.post("/managed-agent-runs", status_code=201)
async def create_managed_agent_run(
    request: ManagedAgentRunCreate,
    response: Response,
    principal: Principal = Depends(_write),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    item = await service.create_agent_run(principal.tenant_id, request)
    response.headers["Location"] = f"/v1/managed-agent-runs/{item['id']}"
    return {"data": item}


@router.get("/managed-agent-runs")
async def list_managed_agent_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    items, total = await service.store.list(
        principal.tenant_id, "agent-runs", limit=limit, offset=offset
    )
    return _page(items, total, limit, offset)


@router.get("/managed-agent-runs/{run_id}")
async def get_managed_agent_run(
    run_id: str,
    principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    return {
        "data": await service.store.get(
            principal.tenant_id, "agent-runs", run_id
        )
    }


@router.post("/agent-dreams", status_code=201)
async def create_agent_dream(
    request: DreamCreate,
    response: Response,
    principal: Principal = Depends(_write),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    item = await service.create_dream(principal.tenant_id, request)
    response.headers["Location"] = f"/v1/agent-dreams/{item['id']}"
    return {"data": item}


@router.get("/agent-dreams")
async def list_agent_dreams(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    items, total = await service.store.list(
        principal.tenant_id, "agent-dreams", limit=limit, offset=offset
    )
    return _page(items, total, limit, offset)


@router.get("/agent-dreams/{dream_id}")
async def get_agent_dream(
    dream_id: str,
    principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    return {
        "data": await service.store.get(
            principal.tenant_id, "agent-dreams", dream_id
        )
    }


@router.post("/agent-webhooks", status_code=201)
async def create_agent_webhook(
    request: WebhookCreate,
    response: Response,
    principal: Principal = Depends(_admin),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    item = await service.create_webhook(principal.tenant_id, request)
    response.headers["Location"] = f"/v1/agent-webhooks/{item['id']}"
    return {"data": item}


@router.get("/agent-webhooks")
async def list_agent_webhooks(
    principal: Principal = Depends(_admin),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    items, total = await service.store.list(
        principal.tenant_id, "agent-webhooks", limit=200
    )
    return _page(items, total, 200, 0)


@router.post("/agent-vaults", status_code=201)
async def create_agent_vault(
    request: VaultCreate,
    response: Response,
    principal: Principal = Depends(_admin),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    item = await service.create_vault(principal.tenant_id, request)
    item["credentials"] = []
    response.headers["Location"] = f"/v1/agent-vaults/{item['id']}"
    return {"data": item}


@router.get("/agent-vaults")
async def list_agent_vaults(
    principal: Principal = Depends(_admin),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    items, total = await service.store.list(
        principal.tenant_id, "agent-vaults", limit=200
    )
    for item in items:
        item["credentials"] = [
            {
                key: value
                for key, value in credential.items()
                if key != "encrypted_secret"
            }
            for credential in item["credentials"]
        ]
    return _page(items, total, 200, 0)


@router.post("/agent-vaults/{vault_id}/credentials", status_code=201)
async def create_agent_vault_credential(
    vault_id: str,
    request: VaultCredentialCreate,
    response: Response,
    principal: Principal = Depends(_admin),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    item = await service.add_vault_credential(
        principal.tenant_id, vault_id, request
    )
    response.headers["Location"] = (
        f"/v1/agent-vaults/{vault_id}/credentials/{item['id']}"
    )
    return {"data": item}


@router.post("/agent-schedules", status_code=201)
async def create_agent_schedule(
    request: ScheduleCreate,
    response: Response,
    principal: Principal = Depends(_admin),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    item = await service.create_schedule(principal.tenant_id, request)
    response.headers["Location"] = f"/v1/agent-schedules/{item['id']}"
    return {"data": item}


@router.get("/agent-schedules")
async def list_agent_schedules(
    principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    items, total = await service.store.list(
        principal.tenant_id, "agent-schedules", limit=200
    )
    return _page(items, total, 200, 0)


@router.post("/agent-schedules/{schedule_id}/cancel")
async def cancel_agent_schedule(
    schedule_id: str,
    principal: Principal = Depends(_admin),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    return {
        "data": await service.cancel_schedule(
            principal.tenant_id, schedule_id
        )
    }


@router.post("/agent-environments", status_code=201)
async def create_agent_environment(
    request: EnvironmentCreate,
    response: Response,
    principal: Principal = Depends(_admin),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    item = await service.create_environment(principal.tenant_id, request)
    response.headers["Location"] = f"/v1/agent-environments/{item['id']}"
    return {"data": item}


@router.get("/agent-environments/{environment_id}/work-stats")
async def get_agent_environment_work_stats(
    environment_id: str,
    principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    item = await service.store.get(
        principal.tenant_id, "agent-environments", environment_id
    )
    return {
        "data": {
            "environment_id": environment_id,
            "queue_depth": item["queue_depth"],
            "pending": item["pending"],
            "workers_polling": item["workers_polling"],
            "status": item["status"],
        }
    }


@router.post("/multi-agent-reviews", status_code=201)
async def create_multiagent_review(
    request: MultiAgentReviewCreate,
    response: Response,
    principal: Principal = Depends(_write),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    item = await service.create_multiagent_review(principal.tenant_id, request)
    response.headers["Location"] = f"/v1/multi-agent-reviews/{item['id']}"
    return {"data": item}


@router.get("/multi-agent-reviews/{review_id}")
async def get_multiagent_review(
    review_id: str,
    principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    return {
        "data": await service.store.get(
            principal.tenant_id, "agent-reviews", review_id
        )
    }


@router.post("/memory-stores", status_code=201)
async def create_memory_store(
    request: MemoryStoreCreate,
    response: Response,
    principal: Principal = Depends(_write),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    item = await service.create_memory_store(principal.tenant_id, request.name)
    response.headers["Location"] = f"/v1/memory-stores/{item['id']}"
    return {"data": item}


@router.get("/memory-stores")
async def list_memory_stores(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    include_archived: bool = False,
    principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    all_items, _ = await service.store.list(
        principal.tenant_id, "memory-stores", limit=10_000, offset=0
    )
    filtered = [
        item
        for item in all_items
        if include_archived or item["status"] != "archived"
    ]
    return _page(filtered[offset : offset + limit], len(filtered), limit, offset)


@router.post("/memory-stores/{store_id}/archive")
async def archive_memory_store(
    store_id: str,
    principal: Principal = Depends(_write),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    return {
        "data": await service.archive_memory_store(principal.tenant_id, store_id)
    }


@router.delete("/memory-stores/{store_id}", status_code=204)
async def delete_memory_store(
    store_id: str,
    principal: Principal = Depends(_admin),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> Response:
    await service.delete_memory_store(principal.tenant_id, store_id)
    return Response(status_code=204)


@router.post("/memory-stores/{store_id}/memories", status_code=201)
async def create_memory(
    store_id: str,
    request: MemoryCreate,
    response: Response,
    principal: Principal = Depends(_write),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    item = await service.create_memory(principal.tenant_id, store_id, request)
    response.headers["Location"] = (
        f"/v1/memory-stores/{store_id}/memories/{item['id']}"
    )
    return {"data": item}


@router.get("/memory-stores/{store_id}/memories")
async def list_memories(
    store_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    path_prefix: str | None = Query(None, max_length=500),
    depth: int | None = Query(None, ge=0, le=100),
    principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    await service.store.get(principal.tenant_id, "memory-stores", store_id)
    all_items, _ = await service.store.list(
        principal.tenant_id,
        f"memories:{store_id}",
        limit=10_000,
        offset=0,
    )
    filtered = []
    for item in all_items:
        path = item["path"]
        if path_prefix is not None and not path.startswith(path_prefix):
            continue
        if depth is not None:
            relative = path.removeprefix(path_prefix or "").strip("/")
            if relative and len(relative.split("/")) > depth:
                continue
        filtered.append(item)
    return _page(filtered[offset : offset + limit], len(filtered), limit, offset)


@router.get("/memory-stores/{store_id}/memories/{memory_id}")
async def get_memory(
    store_id: str,
    memory_id: str,
    principal: Principal = Depends(_read),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    await service.store.get(principal.tenant_id, "memory-stores", store_id)
    return {
        "data": await service.store.get(
            principal.tenant_id, f"memories:{store_id}", memory_id
        )
    }


@router.patch("/memory-stores/{store_id}/memories/{memory_id}")
async def patch_memory(
    store_id: str,
    memory_id: str,
    request: MemoryPatch,
    principal: Principal = Depends(_write),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> dict:
    return {
        "data": await service.patch_memory(
            principal.tenant_id, store_id, memory_id, request
        )
    }


@router.delete(
    "/memory-stores/{store_id}/memories/{memory_id}", status_code=204
)
async def delete_memory(
    store_id: str,
    memory_id: str,
    principal: Principal = Depends(_write),
    service: DomainResourceService = Depends(get_domain_resource_service),
) -> Response:
    await service.store.get(principal.tenant_id, "memory-stores", store_id)
    await service.store.delete(
        principal.tenant_id, f"memories:{store_id}", memory_id
    )
    return Response(status_code=204)


__all__ = ["router"]
