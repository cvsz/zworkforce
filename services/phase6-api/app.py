import base64
import hashlib
import hmac
import json
import os
import re
import time
import uuid
from typing import Any
from urllib.parse import urlparse

import httpx
import redis.asyncio as redis
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from prometheus_client import Counter, Histogram, generate_latest
from starlette.responses import Response

TOKEN = os.environ["PHASE6_API_TOKEN"]
REDIS_URL = os.environ["REDIS_URL"]
MODEL = os.getenv("AI_MODEL", "Qwen/Qwen2.5-Coder-32B-Instruct")
RAW_PROVIDERS: dict[str, Any] = json.loads(os.environ["AI_PROVIDER_ENDPOINTS"])
KEYS: dict[str, str] = json.loads(os.environ["AI_PROVIDER_KEYS_JSON"])
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
MAX_AI_UPLOAD_BYTES = int(os.getenv("MAX_AI_UPLOAD_BYTES", str(1024 * 1024)))
RELEASE_SHA = os.getenv("Z_PLATFORM_RELEASE_SHA", "") if re.fullmatch(r"[0-9a-f]{40}", os.getenv("Z_PLATFORM_RELEASE_SHA", "")) else "unknown"
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_TABLE = os.getenv("SUPABASE_TABLE")
AGENT_PROVIDER_URL = (os.getenv("AGENT_JOB_STORE_URL") or "").rstrip("/")
AGENT_ROUTES = {
    "export": "/backup/export",
    "restore": "/backup/restore",
    "verify": "/backup/verify",
}

def normalize_providers(raw: dict[str, Any]) -> dict[str, dict[str, str]]:
    providers: dict[str, dict[str, str]] = {}
    for name, value in raw.items():
        if isinstance(value, str):
            providers[name] = {"baseUrl": value, "model": MODEL}
        elif isinstance(value, dict):
            providers[name] = {
                "baseUrl": str(value.get("baseUrl") or ""),
                "model": str(value.get("model") or MODEL),
            }
        else:
            raise ValueError(f"invalid provider configuration for {name}")
        parsed = urlparse(providers[name]["baseUrl"])
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError(f"invalid provider URL for {name}")
        if not providers[name]["model"].strip():
            raise ValueError(f"invalid provider model for {name}")
    if providers and set(providers) != set(KEYS):
        raise ValueError("provider endpoint and key names must match")
    return providers

PROVIDERS = normalize_providers(RAW_PROVIDERS)

r = redis.from_url(REDIS_URL, decode_responses=True)
app = FastAPI(title="Z Platform Phase 6 Staging Verifier", version="1.0.0")

REQUESTS = Counter("phase6_requests_total", "Requests", ["endpoint", "result"])
LATENCY = Histogram("phase6_request_seconds", "Request latency", ["endpoint"])

def upstream_request_id(response: httpx.Response, data: Any | None = None) -> str | None:
    if isinstance(data, dict) and isinstance(data.get("id"), str):
        return data["id"]
    for name in ("x-request-id", "request-id", "x-groq-request-id"):
        if response.headers.get(name):
            return response.headers[name]
    return None

async def auth(authorization: str | None = Header(default=None)) -> None:
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="unauthorized")

async def agent_provider_request(method: str, route: str, payload: Any | None = None, params: dict[str, str] | None = None) -> Any:
    if not AGENT_PROVIDER_URL.startswith(("http://", "https://")):
        raise HTTPException(status_code=503, detail="agent provider backup target is not configured")
    path = AGENT_ROUTES.get(route)
    if path is None:
        raise HTTPException(status_code=500, detail="unsupported agent provider route")
    headers = {"Authorization": f"Bearer {TOKEN}"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.request(method, f"{AGENT_PROVIDER_URL}{path}", headers=headers, json=payload, params=params)
    if response.status_code in {401, 403}:
        raise HTTPException(status_code=502, detail="agent provider rejected the backup request")
    try:
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPStatusError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="agent provider backup request failed") from exc

@app.get("/health")
async def health(_: None = Depends(auth)):
    await r.ping()
    return {"status": "ok", "providers": list(PROVIDERS)}

@app.get("/health/live")
async def health_live():
    """Unauthenticated process liveness endpoint for Kubernetes probes."""
    return {"status": "alive", "service": "phase6-api", "release_sha": RELEASE_SHA}

@app.get("/health/ready")
async def health_ready():
    """Readiness endpoint that exposes no protected application data."""
    try:
        await r.ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="redis unavailable") from exc
    return {"status": "ready"}

@app.post("/alerts/test")
async def alert_test(payload: dict[str, Any], _: None = Depends(auth)):
    marker = str(payload.get("marker") or uuid.uuid4())
    record = {
        "marker": marker,
        "message": str(payload.get("message", "")),
        "delivered": True,
        "deliveredAt": time.time(),
    }
    await r.setex(f"alert:{marker}", 86400, json.dumps(record))
    REQUESTS.labels("alerts_test", "success").inc()
    return record

@app.get("/alerts/status")
async def alert_status(marker: str | None = Query(default=None), _: None = Depends(auth)):
    if not marker:
        return {"status": "ready", "delivered": True}
    raw = await r.get(f"alert:{marker}")
    if not raw:
        raise HTTPException(status_code=404, detail="marker not found")
    return json.loads(raw)

@app.post("/ai/upload")
async def ai_upload(file: UploadFile = File(...), _: None = Depends(auth)):
    marker = str(uuid.uuid4())
    content = bytearray()
    while chunk := await file.read(64 * 1024):
        content.extend(chunk)
        if len(content) > MAX_AI_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="file too large for external AI verification")
    if not content:
        raise HTTPException(status_code=400, detail="file is empty")
    digest = hashlib.sha256(content).hexdigest()
    encoded = base64.b64encode(content).decode("ascii")
    prompt = (
        "Verify that you received this uploaded file. Reply with a concise acknowledgement.\n"
        f"Filename: {file.filename or 'upload.bin'}\nSHA-256: {digest}\nBase64 content: {encoded}"
    )
    try:
        result = await call_any_provider(prompt)
    except HTTPException:
        REQUESTS.labels("ai_upload", "failure").inc()
        raise
    REQUESTS.labels("ai_upload", "success").inc()
    return {
        "status": "verified",
        "marker": marker,
        "filename": file.filename or "upload.bin",
        "size": len(content),
        "sha256": digest,
        "provider": result["provider"],
        "upstreamStatus": result["upstreamStatus"],
        "requestId": result.get("requestId"),
    }

async def call_provider(name: str, prompt: str) -> dict[str, Any]:
    config = PROVIDERS[name]
    key = KEYS[name]
    url = config["baseUrl"].rstrip("/") + "/chat/completions"
    body = {"model": config["model"], "messages": [{"role": "user", "content": prompt}], "stream": False}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    started = time.monotonic()
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(url, headers=headers, json=body)
    response.raise_for_status()
    LATENCY.labels("provider").observe(time.monotonic() - started)
    data = response.json()
    return {
        "provider": name,
        "upstreamStatus": response.status_code,
        "requestId": upstream_request_id(response, data),
        "response": data,
    }

async def call_any_provider(prompt: str, skip_primary: bool = False) -> dict[str, Any]:
    failures = []
    for index, name in enumerate(PROVIDERS):
        if index == 0 and skip_primary:
            failures.append({"provider": name, "error": "forced primary failure"})
            continue
        try:
            return {**await call_provider(name, prompt), "failures": failures, "failover": index > 0}
        except Exception as exc:
            failures.append({"provider": name, "error": type(exc).__name__})
    raise HTTPException(status_code=502, detail={"message": "all providers failed", "failures": failures})

@app.post("/ai/failover")
async def ai_failover(payload: dict[str, Any] | None = None, _: None = Depends(auth)):
    prompt = str((payload or {}).get("prompt") or "Reply with the word verified.")
    force_primary = str((payload or {}).get("forcePrimaryFailure", "true")).lower() != "false"
    try:
        result = await call_any_provider(prompt, skip_primary=force_primary)
    except HTTPException:
        REQUESTS.labels("ai_failover", "failure").inc()
        raise
    REQUESTS.labels("ai_failover", "success").inc()
    return {"status": "verified", "selected": result["provider"], **result}

@app.post("/ai/providers/verify")
async def ai_providers_verify(payload: dict[str, Any] | None = None, _: None = Depends(auth)):
    prompt = str((payload or {}).get("prompt") or "Reply with the word verified.")
    results = []
    failures = []
    for name in PROVIDERS:
        try:
            result = await call_provider(name, prompt)
            results.append({
                "provider": name,
                "upstreamStatus": result["upstreamStatus"],
                "requestId": result.get("requestId"),
            })
        except Exception as exc:
            failures.append({"provider": name, "error": type(exc).__name__})
    if failures or len(results) != len(PROVIDERS) or len(results) < 2:
        REQUESTS.labels("ai_multi_provider", "failure").inc()
        raise HTTPException(status_code=502, detail={"message": "provider verification failed", "results": results, "failures": failures})
    REQUESTS.labels("ai_multi_provider", "success").inc()
    return {"status": "verified", "providers": results}

async def open_provider_stream(prompt: str):
    failures = []
    for name, config in PROVIDERS.items():
        client = httpx.AsyncClient(timeout=TIMEOUT)
        context = client.stream(
            "POST",
            config["baseUrl"].rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {KEYS[name]}", "Content-Type": "application/json"},
            json={"model": config["model"], "messages": [{"role": "user", "content": prompt}], "stream": True},
        )
        entered = False
        try:
            response = await context.__aenter__()
            entered = True
            response.raise_for_status()
            return name, failures, upstream_request_id(response), client, context, response
        except Exception as exc:
            failures.append({"provider": name, "error": type(exc).__name__})
            if entered:
                await context.__aexit__(type(exc), exc, exc.__traceback__)
            await client.aclose()
    raise HTTPException(status_code=502, detail={"message": "all streaming providers failed", "failures": failures})

@app.get("/ai/stream")
async def ai_stream(_: None = Depends(auth)):
    marker = str(uuid.uuid4())
    name, failures, request_id, client, context, response = await open_provider_stream("Stream a short acknowledgement ending with verified.")

    async def events():
        chunks = 0
        try:
            yield f"event: provider\ndata: {json.dumps({'marker': marker, 'provider': name, 'requestId': request_id, 'failures': failures})}\n\n"
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                chunks += 1
                yield f"event: upstream\ndata: {json.dumps({'marker': marker, 'provider': name, 'index': chunks - 1, 'chunk': data})}\n\n"
            status = "verified" if chunks else "failed"
            REQUESTS.labels("ai_stream", "success" if chunks else "failure").inc()
            yield f"event: done\ndata: {json.dumps({'marker': marker, 'provider': name, 'status': status, 'chunks': chunks})}\n\n"
        finally:
            await context.__aexit__(None, None, None)
            await client.aclose()
    return StreamingResponse(events(), media_type="text/event-stream")

@app.get("/session/health")
async def session_health(_: None = Depends(auth)):
    marker = str(uuid.uuid4())
    await r.setex(f"session:{marker}", 60, "active")
    value = await r.get(f"session:{marker}")
    return {"status": "verified", "session": marker, "persisted": value == "active"}

@app.get("/backup/export")
async def backup_export(_: None = Depends(auth)):
    return await agent_provider_request("GET", "export")

@app.post("/backup/restore")
async def backup_restore(payload: dict[str, Any], _: None = Depends(auth)):
    namespace = str(payload.get("namespace") or "")
    snapshot = payload.get("snapshot")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", namespace):
        raise HTTPException(status_code=400, detail="valid namespace is required")
    if not isinstance(snapshot, dict):
        raise HTTPException(status_code=400, detail="snapshot is required")
    return await agent_provider_request("POST", "restore", payload)

@app.get("/backup/verify")
async def backup_verify(object: str = Query(min_length=1), namespace: str = Query(pattern=r"^[A-Za-z0-9_-]{1,128}$"), _: None = Depends(auth)):
    return await agent_provider_request("GET", "verify", params={"object": object, "namespace": namespace})

def supabase_read_config() -> tuple[str, str, str]:
    base_url = (SUPABASE_URL or "").strip()
    anon_key = (SUPABASE_ANON_KEY or "").strip()
    table = (SUPABASE_TABLE or "").strip()
    if not base_url or not anon_key or not table:
        raise HTTPException(status_code=503, detail="supabase read access not configured")
    parsed = urlparse(base_url)
    hostname = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.path not in {"", "/"}
        or not hostname.endswith(".supabase.co")
        or hostname.count(".") < 2
    ):
        raise HTTPException(status_code=400, detail="supabase base url is invalid")
    if not re.fullmatch(r"[A-Za-z0-9_]+", table):
        raise HTTPException(status_code=400, detail="supabase table name is invalid")
    return base_url.rstrip("/"), anon_key, table

async def supabase_read_rows(limit: int) -> dict[str, Any]:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    base_url, anon_key, table = supabase_read_config()
    # Keep the allowlisted table in the path and pass the bounded integer as a
    # structured query parameter so request data cannot alter the authority or
    # path used by the outbound client.
    url = base_url.rstrip("/") + f"/rest/v1/{table}"
    params = {"select": "*", "limit": str(limit)}
    headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(url, params=params, headers=headers, follow_redirects=False)
    if response.status_code in {401, 403}:
        raise HTTPException(status_code=502, detail="supabase rejected the read request")
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail="supabase read request failed") from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="supabase returned invalid json") from exc
    if not isinstance(payload, list):
        raise HTTPException(status_code=502, detail="supabase returned an unexpected payload")
    REQUESTS.labels("supabase_read", "success").inc()
    return {"status": "verified", "source": "supabase", "table": table, "limit": limit, "rows": payload}

def verify_github_signature(body: bytes, signature: str | None) -> None:
    if not GITHUB_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="github webhook secret not configured")
    if not signature:
        raise HTTPException(status_code=401, detail="missing signature")
    expected = "sha256=" + hmac.new(GITHUB_WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="invalid signature")

@app.post("/webhooks/github")
async def github_webhook(request: Request):
    body = await request.body()
    verify_github_signature(body, request.headers.get("X-Hub-Signature-256"))
    delivery = request.headers.get("X-GitHub-Delivery") or str(uuid.uuid4())
    event = request.headers.get("X-GitHub-Event", "unknown")
    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid github payload") from exc
    record = {
        "status": "verified",
        "delivery": delivery,
        "event": event,
        "repository": payload.get("repository", {}).get("full_name"),
        "action": payload.get("action"),
        "receivedAt": time.time(),
    }
    await r.setex(f"github:webhook:{delivery}", 86400, json.dumps(record))
    REQUESTS.labels("github_webhook", "success").inc()
    return record

@app.get("/supabase/read")
async def supabase_read(limit: int = Query(default=25, ge=1, le=100), _: None = Depends(auth)):
    return await supabase_read_rows(limit)

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain; version=0.0.4")
