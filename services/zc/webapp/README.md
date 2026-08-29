# wire web console

A browser UI for the AI Model Coder CLI. It does not replace the CLI or
duplicate its logic — `webapp/backend/server.py` imports and calls the
same `Coder` class, `personalities.py`, `skills.py`, `config.py`, and
`health.py` that `main.py` already uses, and just exposes them over HTTP.

```
webapp/
├── backend/
│   └── server.py       # FastAPI app — thin adapter over the CLI core
├── frontend/
│   ├── index.html       # terminal-styled chat UI (no build step needed)
│   ├── style.css
│   └── app.js
└── requirements-web.txt # fastapi + uvicorn, additive to ../requirements.txt
```

## Quick start

From the project root:

```bash
make build      # create .web-venv/ and install requirements.txt + webapp/requirements-web.txt
export ZC_API_KEY=sk-ant-...   # or paste it into the sidebar once running
make start      # launch in the background, http://localhost:8420
make status     # check whether it's up
make logs       # tail logs/web.log
make stop
make restart
make update     # refresh dependencies (and git pull, if this is a git checkout)
make upgrade    # update + restart a running server + health-check
```

Override host/port with `make start HOST=127.0.0.1 PORT=9000`.

## Without the Makefile

```bash
pip install -r requirements.txt -r webapp/requirements-web.txt
uvicorn webapp.backend.server:app --app-dir . --host 0.0.0.0 --port 8420
```

## API surface

| Method & path              | Wraps                                   |
|-----------------------------|------------------------------------------|
| `POST /api/chat`            | `coder.Coder.generate()`                 |
| `GET  /api/health`          | `health.run_health_check()`              |
| `GET  /api/models`          | `zc_models.MODEL_CATALOG`            |
| `GET  /api/personalities`   | `personalities.PersonalityManager`       |
| `GET  /api/skills`          | `skills.SkillManager`                    |
| `GET  /api/agents`          | `main.AGENT_SYSTEM_PROMPTS`              |
| `GET/POST /api/config`      | `config.Config`                          |
| `GET/DELETE /api/sessions/:id` | in-memory chat history (per-process)  |
| `GET  /api/version`         | `main.VERSION`                           |

Sessions are held in memory only (same lifetime as the CLI's
`--interactive` REPL) and are cleared on restart — there's no database
here, by design, to keep this a thin layer over the existing core rather
than a second source of truth.

The API key entered in the sidebar is sent once to `POST /api/config` and
stored the same place the CLI already reads it from
(`~/.ai-coder-config.json` via `config.Config`) — it is never echoed back
in full to the browser afterward.
