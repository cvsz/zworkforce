# Usage Contracts v1

## ai.usage.recorded.v1

```json
{"event_id":"string","idempotency_key":"string","tenant_id":"string","request_id":"string","model":"string","input_tokens":0,"output_tokens":0,"recorded_at":"RFC3339 timestamp"}
```

Usage must be emitted by the AI Gateway after a completed request. The billing ledger rejects duplicate idempotency keys.
