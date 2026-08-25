# Model Context Protocol

zWorkforce exposes an authenticated stateless MCP endpoint at `POST /mcp` and includes a remote CLI client.

Protocol version: `2026-07-28`.

## Methods

- `initialize` (standard MCP client handshake)
- `server/discover`
- `tools/list`
- `tools/call`

Headers include `MCP-Protocol-Version` and may include `Mcp-Method` / `Mcp-Name`; mismatches are rejected.

## Management tools

- `workforce.submit_task` — operator + `task:write`
- `workforce.get_task` — viewer + `workforce:read`
- `workforce.search_memory` — viewer + `workforce:read`
- `workforce.run_workflow` — operator + `automation:write`
- `workforce.emit_event` — operator + `automation:write`
- `workforce.install_prometa` — admin + `agent:write`

MCP uses the same tenant isolation and credentials as REST. Remote non-local endpoints must use HTTPS.

## CLI

```bash
export ZWORKFORCE_MCP_TOKEN=...
zworkforce mcp-tools https://workforce.example.com/mcp
zworkforce mcp-call https://workforce.example.com/mcp workforce.search_memory --arguments '{"query":"release policy"}'
```
