# ZChat Read-Only Capability Integration v1

This change establishes only an authenticated, read-only capability handshake
between zWorkforce and the ZChat Control Server. It does not submit commands,
approve provider actions, claim execution leases, or verify Camfrog outcomes.

## Ownership boundary

- zWorkforce owns governed planning and workflow orchestration.
- ZChat owns provider account mapping and application-specific execution policy.
- Windows agents own authorized local runtime effects.
- A capability response is descriptive metadata, not an authorization grant.

## Contract

The read-only API resources are `/capabilities` and `/health` under
`/api/v1/integrations/zworkforce/v1/`. The protocol identifier is
`zchat-zworkforce`, version `1.0`. zWorkforce's local MCP tools
`zchat.get_capabilities` and `zchat.get_health` require `workforce:read` and a
server-side service token; they call ZChat's versioned read-only HTTP
resources. ZChat separately exposes remote MCP tools `zchat.capabilities` and
`zchat.health`.
Worker and operation inventory remains unavailable until authenticated
tenant-to-account identity mapping can enforce tenant isolation. ZChat's MCP
publishes `zchat://capabilities` and `zchat://health` as read-only resources,
alongside its `zchat.capabilities` and `zchat.health` tools. The local
zWorkforce tools require the `workforce:read` scope and produce audit events.
The integration does not expose resource-lock ownership, provider identity
proof, or verified external outcomes. The client rejects non-HTTPS non-loopback
URLs, redirects, malformed capability data, duplicate feature IDs, missing
evidence labels, and unsupported protocol versions. Contract version/resource lists and verified
platform/provider-version lists must contain unique, non-empty trimmed strings.
The v1 health response accepts only `{"status":"healthy","database":"reachable"}`;
other states fail closed instead of being interpreted as healthy.

Configure the same random service token server-side as
`CONTROL_ZWORKFORCE_INTEGRATION_TOKEN` in ZChat and
`ZCHAT_INTEGRATION_TOKEN` in zWorkforce. Set `ZCHAT_CONTROL_URL` in zWorkforce
to the ZChat HTTPS origin. The ZChat endpoint returns `503` when its token is
unset. Never put either service token in browser/static configuration.

The capability response lists eight Camfrog standalone features and the
separately packaged LINE status changer. `standalone_supported` means a source
entry point and build target exist; it is not a live Windows acceptance claim.
`camfrog.private_chat`, `camfrog.status_random`, `camfrog.status_marquee`, and
`camfrog.status_changer` report `unified_supported=true`. The client embeds the
read-only Private Chat window manager and the shared Status Changer module with
Random and Marquee modes. Private Chat does not read or send messages. The
other six features report false.
All entries report `supports_remote_commands=false`,
`evidence_status=PARTIALLY VERIFIED`, and empty verified platform/provider-
version lists. Strict background, minimized/hidden client support, and
external outcome verification are also false. Contract tests do not establish
live provider support.

## Cross-repository contract validation

The `zchat-contract` CI job checks out ZChat at the exact commit recorded in
`.github/workflows/ci.yml`, installs both repositories' Python packages, and
runs `tests/test_zchat_control_contract.py` against a loopback Uvicorn server
with an ephemeral SQLite database and generated in-memory service credentials.
The test exercises the zWorkforce HTTP capability/health client and its
`RemoteMCPClient` against the real ZChat Control Server routes, including
protocol negotiation, read-only tool/resource discovery, invalid credentials,
and rejection of an unavailable mutation tool. It does not use production
credentials, infrastructure, or Camfrog, and does not establish provider
outcome verification. Update the pinned ZChat commit when intentionally
re-baselining this cross-repository contract.

## Remaining gates

The mutation protocol still needs canonical approval grants bound to an exact
account/resource and immutable action digest, authenticated agent enrollment,
durable operation storage, execution claims with fencing generations,
cancellation/emergency stop, outcome reconciliation, and cross-repository
contract/security tests. Do not expose ZChat command submission through MCP
until those controls are implemented and verified.
