# ZAI Coder

ZAI Coder is the coding-agent application for Z Platform.

## Migration scope

The legacy component contains a Python CLI, a browser terminal, and a collection of direct provider integrations. The migration keeps the application boundary but changes credential routing:

```text
Browser / CLI -> Z Platform AI Gateway -> approved model providers
```

Clients must not receive provider credentials. Provider selection, quotas, audit correlation, and tenant policy belong to the gateway.

## Batch 1 status

- Application contract: established
- Python packaging baseline: migrated
- Provider gateway contract: established
- Legacy runtime modules and web UI: pending dependency-audited import

See `docs/migration/zaicoder-dependency-audit.md`.
