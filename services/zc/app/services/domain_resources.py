"""Tenant-aware application services for migrated legacy CLI domains."""

from __future__ import annotations

import asyncio
import json
import hashlib
import mimetypes
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models.ai import AIResponseRequest
from app.models.domain_resources import (
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
    ProjectCreate,
    ProjectPlanCreate,
    ProjectPatch,
    ResearchCreate,
    ScheduleCreate,
    TaskCreate,
    TaskPatch,
    VaultCreate,
    VaultCredentialCreate,
    WebhookCreate,
)

from .ai_service import AIService, get_ai_service_instance
from .project_templates import PROJECT_TEMPLATES
from .resource_store import ResourceNotFoundError, ResourceStore


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class DomainResourceService:
    """Coordinate resource persistence and explicitly bounded AI operations."""

    def __init__(
        self,
        store: ResourceStore,
        ai_service: AIService | None = None,
        blob_root: Path | None = None,
        encryptor: Any | None = None,
    ) -> None:
        self.store = store
        self.ai_service = ai_service or get_ai_service_instance()
        self.blob_root = blob_root or store.database_path.parent / "blobs"
        self.encryptor = encryptor

    @staticmethod
    def _templates() -> dict[str, list[dict[str, Any]]]:
        return PROJECT_TEMPLATES

    async def create_project(
        self, tenant_id: str, request: ProjectCreate
    ) -> dict[str, Any]:
        tasks = [
            {
                "id": _id("tsk"),
                **task,
                "status": "todo",
                "result": "",
            }
            for task in self._templates()[request.template]
        ]
        return await self.store.create(
            tenant_id,
            "projects",
            _id("prj"),
            {
                "name": request.name,
                "description": request.description,
                "template": request.template,
                "status": "planning",
                "context": "",
                "tasks": tasks,
                "tags": [],
                "run_log": [],
            },
        )

    async def patch_project(
        self, tenant_id: str, project_id: str, request: ProjectPatch
    ) -> dict[str, Any]:
        project = await self.store.get(tenant_id, "projects", project_id)
        project.update(request.model_dump(exclude_none=True))
        return await self.store.replace(tenant_id, "projects", project_id, project)

    async def plan_project(
        self, tenant_id: str, project_id: str, request: ProjectPlanCreate
    ) -> dict[str, Any]:
        project = await self.store.get(tenant_id, "projects", project_id)
        response = await self.ai_service.create_response(
            AIResponseRequest(
                prompt=(
                    f"Project: {project['name']}\n"
                    f"Description: {project['description']}\n"
                    "Return a JSON array of 5-10 tasks. Each task must contain "
                    "title, description, agent, and priority."
                ),
                model=request.model,
                system="Return only valid JSON without Markdown fences.",
            )
        )
        try:
            raw_tasks = json.loads(response.output_text)
            if not isinstance(raw_tasks, list):
                raise ValueError
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError("AI project plan was not a valid task array") from exc
        for raw in raw_tasks[:20]:
            task_request = TaskCreate.model_validate(raw)
            project["tasks"].append(
                {
                    "id": _id("tsk"),
                    **task_request.model_dump(),
                    "status": "todo",
                    "result": "",
                }
            )
        project["status"] = "active"
        project["plan_response_id"] = response.id
        return await self.store.replace(tenant_id, "projects", project_id, project)

    async def add_task(
        self, tenant_id: str, project_id: str, request: TaskCreate
    ) -> dict[str, Any]:
        project = await self.store.get(tenant_id, "projects", project_id)
        task = {
            "id": _id("tsk"),
            **request.model_dump(),
            "status": "todo",
            "result": "",
        }
        project["tasks"].append(task)
        await self.store.replace(tenant_id, "projects", project_id, project)
        return task

    async def patch_task(
        self,
        tenant_id: str,
        project_id: str,
        task_id: str,
        request: TaskPatch,
    ) -> dict[str, Any]:
        project = await self.store.get(tenant_id, "projects", project_id)
        task = next(
            (item for item in project["tasks"] if item["id"] == task_id), None
        )
        if task is None:
            raise ResourceNotFoundError("project task not found")
        task.update(request.model_dump(exclude_none=True))
        await self.store.replace(tenant_id, "projects", project_id, project)
        return task

    async def run_task(
        self, tenant_id: str, project_id: str, task_id: str, model: str | None = None
    ) -> dict[str, Any]:
        project = await self.store.get(tenant_id, "projects", project_id)
        task = next(
            (item for item in project["tasks"] if item["id"] == task_id), None
        )
        if task is None:
            raise ResourceNotFoundError("project task not found")
        task["status"] = "in_progress"
        await self.store.replace(tenant_id, "projects", project_id, project)
        try:
            response = await self.ai_service.create_response(
                AIResponseRequest(
                    prompt=(
                        f"Project: {project['name']}\n"
                        f"Context: {project.get('context', '')}\n"
                        f"Task: {task['title']}\n{task['description']}"
                    ),
                    model=model,
                    agent=task.get("agent") or "full_stack",
                )
            )
        except Exception:
            task["status"] = "blocked"
            await self.store.replace(tenant_id, "projects", project_id, project)
            raise
        task["status"] = "done"
        task["result"] = response.output_text
        project["status"] = "active"
        project["run_log"].append(
            {"task_id": task_id, "response_id": response.id, "status": "done"}
        )
        await self.store.replace(tenant_id, "projects", project_id, project)
        return task

    async def create_artifact(
        self, tenant_id: str, request: ArtifactCreate
    ) -> dict[str, Any]:
        content = request.content
        response_id = None
        if content is None:
            response = await self.ai_service.create_response(
                AIResponseRequest(prompt=request.prompt or "", model=request.model)
            )
            content = response.output_text
            response_id = response.id
        version = {
            "version": 1,
            "content": content,
            "checksum": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "response_id": response_id,
        }
        return await self.store.create(
            tenant_id,
            "artifacts",
            _id("art"),
            {
                "name": request.name,
                "artifact_type": request.artifact_type,
                "language": request.language,
                "project_id": request.project_id,
                "tags": sorted(set(request.tags)),
                "current_version": 1,
                "versions": [version],
            },
        )

    async def iterate_artifact(
        self, tenant_id: str, artifact_id: str, request: ArtifactIteration
    ) -> dict[str, Any]:
        artifact = await self.store.get(tenant_id, "artifacts", artifact_id)
        current = artifact["versions"][-1]["content"]
        response = await self.ai_service.create_response(
            AIResponseRequest(
                prompt=(
                    f"Revise this artifact using the feedback.\n\n"
                    f"Artifact:\n{current}\n\nFeedback:\n{request.feedback}"
                ),
                model=request.model,
            )
        )
        number = int(artifact["current_version"]) + 1
        artifact["versions"].append(
            {
                "version": number,
                "content": response.output_text,
                "checksum": hashlib.sha256(
                    response.output_text.encode("utf-8")
                ).hexdigest(),
                "response_id": response.id,
            }
        )
        artifact["current_version"] = number
        return await self.store.replace(
            tenant_id, "artifacts", artifact_id, artifact
        )

    async def patch_artifact(
        self, tenant_id: str, artifact_id: str, request: ArtifactPatch
    ) -> dict[str, Any]:
        artifact = await self.store.get(tenant_id, "artifacts", artifact_id)
        updates = request.model_dump(exclude_none=True)
        if "tags" in updates:
            updates["tags"] = sorted(set(updates["tags"]))
        artifact.update(updates)
        return await self.store.replace(
            tenant_id, "artifacts", artifact_id, artifact
        )

    async def artifact_diff(
        self,
        tenant_id: str,
        artifact_id: str,
        from_version: int,
        to_version: int,
    ) -> dict[str, Any]:
        import difflib

        artifact = await self.store.get(tenant_id, "artifacts", artifact_id)
        versions = {
            int(version["version"]): version["content"]
            for version in artifact["versions"]
        }
        if from_version not in versions or to_version not in versions:
            raise ResourceNotFoundError("artifact version not found")
        diff = "\n".join(
            difflib.unified_diff(
                versions[from_version].splitlines(),
                versions[to_version].splitlines(),
                fromfile=f"v{from_version}",
                tofile=f"v{to_version}",
                lineterm="",
            )
        )
        return {
            "artifact_id": artifact_id,
            "from_version": from_version,
            "to_version": to_version,
            "diff": diff,
        }

    async def create_research(
        self, tenant_id: str, request: ResearchCreate
    ) -> dict[str, Any]:
        record = await self.store.create(
            tenant_id,
            "research",
            _id("res"),
            {
                "topic": request.topic,
                "depth": request.depth,
                "source_urls": [str(url) for url in request.source_urls],
                "status": "running",
                "report": "",
                "response_id": None,
            },
        )
        source_block = "\n".join(f"- {url}" for url in record["source_urls"])
        try:
            response = await self.ai_service.create_response(
                AIResponseRequest(
                    prompt=(
                        f"Produce a structured research report about: {request.topic}\n"
                        f"Use {request.depth} focused sub-questions. Clearly distinguish "
                        "verified claims, inference, and uncertainty. Do not claim to have "
                        "read a source unless its content is available.\n"
                        f"User-provided source references:\n{source_block or '- none'}"
                    ),
                    model=request.model,
                    system=(
                        "You are a careful research analyst. Return Markdown with a summary, "
                        "sub-questions, findings, limitations, and source-reference section."
                    ),
                )
            )
        except Exception:
            record["status"] = "failed"
            await self.store.replace(
                tenant_id, "research", record["id"], record
            )
            raise
        record["status"] = "completed"
        record["report"] = response.output_text
        record["response_id"] = response.id
        return await self.store.replace(
            tenant_id, "research", record["id"], record
        )

    def _tenant_blob_dir(self, tenant_id: str) -> Path:
        digest = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()
        path = self.blob_root / digest
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def create_file(
        self,
        tenant_id: str,
        filename: str,
        content_type: str | None,
        data: bytes,
    ) -> dict[str, Any]:
        safe_name = Path(filename).name
        forbidden = set('<>:"|?*\\/') | {chr(value) for value in range(32)}
        if (
            not safe_name
            or safe_name != filename
            or len(safe_name) > 255
            or any(character in forbidden for character in safe_name)
        ):
            raise ValueError("invalid filename")
        file_id = _id("fil")
        blob_path = self._tenant_blob_dir(tenant_id) / file_id
        await asyncio.to_thread(blob_path.write_bytes, data)
        return await self.store.create(
            tenant_id,
            "files",
            file_id,
            {
                "filename": safe_name,
                "content_type": content_type
                or mimetypes.guess_type(safe_name)[0]
                or "application/octet-stream",
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "blob_path": str(blob_path),
            },
        )

    async def file_content(self, tenant_id: str, file_id: str) -> tuple[dict, bytes]:
        metadata = await self.store.get(tenant_id, "files", file_id)
        path = Path(metadata["blob_path"])
        if not path.is_file() or path.parent != self._tenant_blob_dir(tenant_id):
            raise ResourceNotFoundError("file content not found")
        return metadata, await asyncio.to_thread(path.read_bytes)

    async def delete_file(self, tenant_id: str, file_id: str) -> None:
        metadata = await self.store.get(tenant_id, "files", file_id)
        path = Path(metadata["blob_path"])
        await self.store.delete(tenant_id, "files", file_id)
        if path.parent == self._tenant_blob_dir(tenant_id):
            await asyncio.to_thread(path.unlink, True)

    async def ask_file(
        self, tenant_id: str, file_id: str, request: FileQuestion
    ) -> dict[str, Any]:
        metadata, data = await self.file_content(tenant_id, file_id)
        if len(data) > 1_000_000:
            raise ValueError("file is too large for direct AI context")
        content = data.decode("utf-8", errors="replace")
        response = await self.ai_service.create_response(
            AIResponseRequest(
                prompt=request.prompt,
                model=request.model,
                file_content=content,
            )
        )
        return {
            "file_id": file_id,
            "filename": metadata["filename"],
            "response_id": response.id,
            "output_text": response.output_text,
        }

    async def create_agent_run(
        self, tenant_id: str, request: ManagedAgentRunCreate
    ) -> dict[str, Any]:
        memory_context = ""
        if request.memory_store_id:
            memories, _ = await self.store.list(
                tenant_id, f"memories:{request.memory_store_id}", limit=100
            )
            memory_context = "\n".join(
                f"{item['path']}: {item['content']}" for item in memories
            )[:200_000]
        if request.vault_id:
            vault = await self.store.get(
                tenant_id, "agent-vaults", request.vault_id
            )
            if vault["status"] != "active":
                raise ValueError("vault is archived")
        run = await self.store.create(
            tenant_id,
            "agent-runs",
            _id("run"),
            {
                **request.model_dump(),
                "status": "running",
                "output_text": "",
                "response_id": None,
            },
        )
        try:
            response = await self.ai_service.create_response(
                AIResponseRequest(
                    prompt=request.task,
                    model=request.model,
                    agent=request.agent,
                    system="\n\n".join(
                        part
                        for part in (
                            request.system,
                            (
                                f"Tenant-scoped memory context:\n{memory_context}"
                                if memory_context
                                else None
                            ),
                            (
                                f"Required outcome: {request.outcome_description}"
                                if request.outcome_description
                                else None
                            ),
                            (
                                f"Outcome rubric:\n{request.outcome_rubric}"
                                if request.outcome_rubric
                                else None
                            ),
                        )
                        if part
                    ),
                ),
            )
        except Exception:
            run["status"] = "failed"
            await self.store.replace(
                tenant_id, "agent-runs", run["id"], run
            )
            raise
        run["status"] = "completed"
        run["output_text"] = response.output_text
        run["response_id"] = response.id
        return await self.store.replace(tenant_id, "agent-runs", run["id"], run)

    async def create_memory_store(
        self, tenant_id: str, name: str
    ) -> dict[str, Any]:
        return await self.store.create(
            tenant_id,
            "memory-stores",
            _id("mems"),
            {"name": name, "status": "active"},
        )

    async def archive_memory_store(
        self, tenant_id: str, store_id: str
    ) -> dict[str, Any]:
        item = await self.store.get(tenant_id, "memory-stores", store_id)
        item["status"] = "archived"
        return await self.store.replace(tenant_id, "memory-stores", store_id, item)

    async def delete_memory_store(self, tenant_id: str, store_id: str) -> None:
        await self.store.get(tenant_id, "memory-stores", store_id)
        memories, _ = await self.store.list(
            tenant_id, f"memories:{store_id}", limit=10_000
        )
        for memory in memories:
            await self.store.delete(
                tenant_id, f"memories:{store_id}", memory["id"]
            )
        await self.store.delete(tenant_id, "memory-stores", store_id)

    async def create_memory(
        self, tenant_id: str, store_id: str, request: MemoryCreate
    ) -> dict[str, Any]:
        store = await self.store.get(tenant_id, "memory-stores", store_id)
        if store["status"] != "active":
            raise ValueError("memory store is archived")
        return await self.store.create(
            tenant_id,
            f"memories:{store_id}",
            _id("mem"),
            request.model_dump(),
        )

    async def patch_memory(
        self,
        tenant_id: str,
        store_id: str,
        memory_id: str,
        request: MemoryPatch,
    ) -> dict[str, Any]:
        await self.store.get(tenant_id, "memory-stores", store_id)
        memory = await self.store.get(
            tenant_id, f"memories:{store_id}", memory_id
        )
        memory.update(request.model_dump(exclude_none=True))
        return await self.store.replace(
            tenant_id, f"memories:{store_id}", memory_id, memory
        )

    async def create_dream(
        self, tenant_id: str, request: DreamCreate
    ) -> dict[str, Any]:
        await self.store.get(
            tenant_id, "memory-stores", request.memory_store_id
        )
        memories, _ = await self.store.list(
            tenant_id, f"memories:{request.memory_store_id}", limit=10_000
        )
        dream = await self.store.create(
            tenant_id,
            "agent-dreams",
            _id("drm"),
            {
                **request.model_dump(),
                "status": "running",
                "output_store_id": None,
                "response_id": None,
            },
        )
        context = "\n".join(
            f"{memory['path']}: {memory['content']}" for memory in memories
        )[:500_000]
        try:
            response = await self.ai_service.create_response(
                AIResponseRequest(
                    prompt=(
                        "Curate, deduplicate, and synthesize this agent memory into a "
                        f"concise durable knowledge document.\n\n{context}"
                    ),
                    system=request.instructions,
                    model=request.model,
                )
            )
        except Exception:
            dream["status"] = "failed"
            await self.store.replace(
                tenant_id, "agent-dreams", dream["id"], dream
            )
            raise
        output_store = await self.create_memory_store(
            tenant_id, f"Dream output {dream['id']}"
        )
        await self.create_memory(
            tenant_id,
            output_store["id"],
            MemoryCreate(path="dream/synthesis.md", content=response.output_text),
        )
        dream["status"] = "completed"
        dream["output_store_id"] = output_store["id"]
        dream["response_id"] = response.id
        return await self.store.replace(
            tenant_id, "agent-dreams", dream["id"], dream
        )

    async def create_webhook(
        self, tenant_id: str, request: WebhookCreate
    ) -> dict[str, Any]:
        return await self.store.create(
            tenant_id,
            "agent-webhooks",
            _id("whk"),
            {
                "url": str(request.url),
                "event_types": request.event_types,
                "status": "active",
            },
        )

    async def create_vault(
        self, tenant_id: str, request: VaultCreate
    ) -> dict[str, Any]:
        return await self.store.create(
            tenant_id,
            "agent-vaults",
            _id("vlt"),
            {
                **request.model_dump(),
                "status": "active",
                "credentials": [],
            },
        )

    async def add_vault_credential(
        self,
        tenant_id: str,
        vault_id: str,
        request: VaultCredentialCreate,
    ) -> dict[str, Any]:
        if self.encryptor is None:
            raise ValueError(
                "ENCRYPTION_KEY is required before storing vault credentials"
            )
        vault = await self.store.get(tenant_id, "agent-vaults", vault_id)
        if vault["status"] != "active":
            raise ValueError("vault is archived")
        credential = {
            "id": _id("cred"),
            **request.model_dump(exclude={"secret_value"}, mode="json"),
            "encrypted_secret": self.encryptor.encrypt_string(request.secret_value),
            "status": "active",
        }
        vault["credentials"].append(credential)
        await self.store.replace(tenant_id, "agent-vaults", vault_id, vault)
        return {
            key: value
            for key, value in credential.items()
            if key != "encrypted_secret"
        }

    async def create_schedule(
        self, tenant_id: str, request: ScheduleCreate
    ) -> dict[str, Any]:
        # Cron execution is reconciled by the deployment worker. The API owns
        # desired state and never shells out from an HTTP request.
        return await self.store.create(
            tenant_id,
            "agent-schedules",
            _id("sch"),
            {**request.model_dump(), "status": "active"},
        )

    async def cancel_schedule(
        self, tenant_id: str, schedule_id: str
    ) -> dict[str, Any]:
        schedule = await self.store.get(
            tenant_id, "agent-schedules", schedule_id
        )
        schedule["status"] = "cancelled"
        return await self.store.replace(
            tenant_id, "agent-schedules", schedule_id, schedule
        )

    async def create_environment(
        self, tenant_id: str, request: EnvironmentCreate
    ) -> dict[str, Any]:
        return await self.store.create(
            tenant_id,
            "agent-environments",
            _id("env"),
            {
                "name": request.name,
                "kind": "self_hosted",
                "status": "awaiting_worker",
                "queue_depth": 0,
                "pending": 0,
                "workers_polling": 0,
            },
        )

    async def create_multiagent_review(
        self, tenant_id: str, request: MultiAgentReviewCreate
    ) -> dict[str, Any]:
        metadata, data = await self.file_content(
            tenant_id, request.file_id
        )
        if len(data) > 1_000_000:
            raise ValueError("review input exceeds the direct context limit")
        content = data.decode("utf-8", errors="replace")
        review = await self.store.create(
            tenant_id,
            "agent-reviews",
            _id("rev"),
            {
                **request.model_dump(),
                "filename": metadata["filename"],
                "status": "running",
                "findings": {},
            },
        )
        findings: dict[str, str] = {}
        agent_map = {
            "security": "security_auditor",
            "style": "code_reviewer",
            "test-coverage": "testing_agent",
        }
        try:
            for specialist in request.specialists:
                response = await self.ai_service.create_response(
                    AIResponseRequest(
                        prompt=f"Review this file as {specialist} specialist.\n\n{content}",
                        model=request.model,
                        agent=agent_map[specialist],
                    )
                )
                findings[specialist] = response.output_text
        except Exception:
            review["status"] = "failed"
            await self.store.replace(
                tenant_id, "agent-reviews", review["id"], review
            )
            raise
        review["status"] = "completed"
        review["findings"] = findings
        return await self.store.replace(
            tenant_id, "agent-reviews", review["id"], review
        )


_service: DomainResourceService | None = None


def get_domain_resource_service_instance() -> DomainResourceService:
    from app.core.config import get_config

    global _service
    if _service is None:
        config = get_config()
        root = config.upload_temp_dir / "enterprise"
        encryptor = None
        if config.encryption_key:
            from app.core.encryption import EndToEndEncryptor

            encryptor = EndToEndEncryptor(config.encryption_key)
        _service = DomainResourceService(
            ResourceStore(root / "resources.sqlite3"),
            blob_root=root / "blobs",
            encryptor=encryptor,
        )
    return _service


async def get_domain_resource_service() -> DomainResourceService:
    """FastAPI dependency that avoids the synchronous dependency threadpool."""
    return get_domain_resource_service_instance()


__all__ = [
    "DomainResourceService",
    "get_domain_resource_service",
    "get_domain_resource_service_instance",
]
