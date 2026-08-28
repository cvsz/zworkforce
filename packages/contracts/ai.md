# AI Contracts v1

## ai.chat.request.v1

```json
{
  "model": "string",
  "messages": [{ "role": "user", "content": "string" }],
  "stream": true,
  "attachments": [{ "id": "string", "name": "string" }]
}
```

`attachments` are platform file references. Browser and app clients must send platform references only; they must not send provider-specific file payloads, provider upload IDs, or upstream credentials.

The AI Gateway validates attachment references and translates them before forwarding upstream. The OpenAI-compatible adapter removes the top-level `attachments` field, records references in `metadata.z_platform.attachments`, and adds a textual file-reference context to the final user message.

## ai.model.catalog.v1

```json
{
  "object": "list",
  "data": [
    {
      "object": "model",
      "id": "hf:Qwen/Qwen2.5-7B-Instruct",
      "provider": "huggingface",
      "upstream_provider": "openai-compatible",
      "repo": "Qwen/Qwen2.5-7B-Instruct",
      "task": "text-generation",
      "license": "apache-2.0",
      "profile": "general-instruct",
      "runtime": ["huggingface-endpoint", "local-transformers", "text-generation-inference"],
      "context_window": null,
      "notes": "string"
    }
  ]
}
```

The catalog is metadata only. It does not deploy hosted inference, grant provider credentials, or guarantee zero-cost remote execution. Runtime availability depends on the operator-approved local runtime or upstream endpoint.

## ai.file.uploaded.v1

```json
{
  "id": "string",
  "name": "string",
  "size_bytes": 0
}
```

## ai.workspace.metadata.v1

```json
{
  "id": "string",
  "owner": "string",
  "retention_days": 30,
  "created_at": "2026-07-13T00:00:00.000Z",
  "updated_at": "2026-07-13T00:00:00.000Z",
  "expires_at": "2026-08-12T00:00:00.000Z",
  "files": [
    {
      "id": "string",
      "name": "string",
      "size_bytes": 0,
      "added_at": "2026-07-13T00:00:00.000Z"
    }
  ]
}
```

Workspace metadata links platform file references to a project/workspace boundary. Production services must enforce tenant ownership and retention cleanup before this contract is used outside the local Phase 1 runtime.

## ai.usage.recorded.v1

```json
{
  "usage_id": "string",
  "idempotency_key": "string",
  "tenant_id": "string",
  "subject_id": "string",
  "model": "string",
  "input_tokens": 0,
  "output_tokens": 0,
  "recorded_at": "2026-07-14T00:00:00.000Z"
}
```

Usage records are immutable billing inputs emitted server-side by the AI Gateway. They must not contain wallet signing data, card data, payment-provider credentials, KYC payloads, MPC shares, or swap routes.

Only the gateway may translate these platform contracts into provider-specific requests.
