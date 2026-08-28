# Agent MCP transports

ZeaZ implements MCP JSON-RPC in `zeaz-agent`, never in the provider gateway.
The implementation follows the MCP 2025-11-25 transport specification:

- stdio messages are UTF-8 JSON-RPC objects delimited by a newline;
- Streamable HTTP sends one JSON-RPC message per HTTPS POST and accepts JSON or
  SSE responses;
- HTTP redirects are never followed.

## Policy boundary

Every transport receives an immutable exact method allow-list. Remote
transports also receive an exact hostname allow-list and require HTTPS. A
denied host is rejected at construction and a denied method is rejected
before process creation or network I/O. URLs containing credentials or
fragments are invalid.

The HTTP client ignores proxy environment variables and does not follow
redirects. Authentication is intentionally outside this transport primitive;
tokens must be supplied by a separate credential component and must never be
placed in tool arguments or logs.

The stdio transport accepts only an absolute, non-symlink executable and uses
`create_subprocess_exec` with immutable argv. It never invokes a shell and
starts with an explicit environment that is empty by default, preventing
provider credentials from being inherited. Arguments come from trusted
configuration, never from model output.

## Bounds and untrusted input

Both transports enforce time and message-byte limits. HTTP also bounds SSE
event count. Responses must be JSON-RPC 2.0 objects, must match the request ID,
and must contain exactly one result or error. Server error details are not
surfaced. Stdio peers are killed after timeout, protocol overflow, or broken
framing.

Specification provenance:
<https://modelcontextprotocol.io/specification/2025-11-25/basic/transports>
