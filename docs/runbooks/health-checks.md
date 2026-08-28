# Health Check Matrix

| Service | Endpoint | Expected result | Does not verify |
|---|---|---|---|
| AI Gateway | `GET /health` | process reachable; upstream configuration presence | upstream connectivity or credentials |
| Agent Orchestrator | `GET /health` | process reachable; execution disabled state | queue/database/worker execution |
| ZChat | `GET /health` | process reachable; gateway configuration presence | provider connectivity or user session |

Health endpoints are unauthenticated only because they expose no secrets, job data, tenant data, or provider configuration values.

Use readiness checks separately once an operator selects durable storage, queue, and observability backends.
