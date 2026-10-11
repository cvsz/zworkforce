# Model Context Protocol

zWorkforce exposes an authenticated, tenant-scoped, stateless **POST /mcp** JSON-RPC endpoint. Remote non-local connections must use HTTPS.

## Protocol versions and transport

- Modern discovery/requests: `2026-07-28` on POST `/mcp`; use `server/discover` rather than `initialize`.
- Legacy handshake revisions: `2025-11-25`, `2025-06-18`, `2025-03-26`. `initialize` responds with the proposed supported handshake revision, or counter-offers `2025-11-25` for modern/unknown proposals.
- `2024-11-05` is **not supported**: this endpoint does not implement its HTTP+SSE GET/message transport.
- All tool calls require normal bearer authentication, tenant isolation, and existing role/scope authorization.

## Modern HTTP request contract

Every modern request must have:
1. `Content-Type: application/json`, `MCP-Protocol-Version: 2026-07-28`, and `Mcp-Method` mirroring the JSON-RPC `method`.
2. `Mcp-Name` mirroring `params.name` for `tools/call` (or `params.uri` for `resources/read` and the relevant name for `prompts/get`).
3. `params._meta.io.modelcontextprotocol/protocolVersion` equal to the version header.
4. `params._meta.io.modelcontextprotocol/clientCapabilities` as a JSON **object**, even when empty (`{}`).

A missing or malformed modern metadata object, unsupported revision, or mismatched version is rejected (HTTP 400). Protocol errors return a JSON-RPC envelope with the request `id`; mismatched method/name headers are also rejected. Legacy requests do not require modern routing headers, but supplied routing headers must not conflict with the body.

## Methods

- `initialize` — legacy handshake only
- `server/discover` — modern discovery
- `tools/list`
- `tools/call`

## Example: modern discovery

```bash
curl --fail-with-body -sS https://workforce.example.com/mcp \
  -H "Authorization: Bearer $ZWORKFORCE_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2026-07-28" \
  -H "Mcp-Method: server/discover" \
  --data '{"jsonrpc":"2.0","id":1,"method":"server/discover","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}}}}'
```

## Example: modern tool call

```bash
curl --fail-with-body -sS https://workforce.example.com/mcp \
  -H "Authorization: Bearer $ZWORKFORCE_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2026-07-28" \
  -H "Mcp-Method: tools/call" \
  -H "Mcp-Name: cloudflare.references" \
  --data '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"cloudflare.references","arguments":{},"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}}}}'
```

## Example: legacy initialize

```bash
curl --fail-with-body -sS https://workforce.example.com/mcp \
  -H "Authorization: Bearer $ZWORKFORCE_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-11-25" \
  --data '{"jsonrpc":"2.0","id":3,"method":"initialize","params":{"protocolVersion":"2025-11-25","clientInfo":{"name":"example","version":"1.0"},"capabilities":{}}}'
```

## Management tools

- `workforce.submit_task` — operator + `task:write`
- `workforce.get_task` — viewer + `workforce:read`
- `workforce.search_memory` — viewer + `workforce:read`
- `workforce.run_workflow` — operator + `automation:write`
- `workforce.emit_event` — operator + `automation:write`
- `workforce.install_prometa` — admin + `agent:write`

## CLI

```bash
export ZWORKFORCE_MCP_TOKEN=...
zworkforce mcp-tools https://workforce.example.com/mcp
zworkforce mcp-call https://workforce.example.com/mcp workforce.search_memory --arguments '{"query":"release policy"}'
```
