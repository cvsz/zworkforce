# Merged Source Upgrade Assessment

## Scope

This assessment compares the source under `/home/zeazdev/merged` with the
current `zc` runtime. The review covers:

- `agentforge` at `f6dc4518`;
- `autoresearch-agent` at `d1e7918`; and
- `shen-ai` at `2b86d9cd`.

The source trees contain approximately 28,000 lines of TypeScript and TSX.
Repository state was treated as read-only. Existing deleted `dist/` artifacts
in `agentforge` and `shen-ai` were not restored or modified.

## Evidence Quality

| Project | Source evidence | Verification limitation |
|---|---|---|
| AgentForge | Generator, template manager, preview process, and unit tests are present | `node_modules` is absent and tracked `dist/` files are deleted locally |
| AutoResearch Agent | Research engine, search client, bounded web fetcher, and focused tests are present | `package.json` is absent, so the checkout cannot be reproduced or built as-is |
| SHEN AI | Provider, agent, memory, graph, checkpoint, plugin, sandbox, and UI implementations are present | No test tree is present, `node_modules` is absent, and tracked `dist/` files are deleted locally |

README feature claims were not accepted as runtime proof when source wiring or
tests were missing.

## Capability Decisions

### Adopted: bounded public-web fetching

AutoResearch Agent contains the strongest directly reusable idea: validate
every initial and redirected URL, reject non-public network destinations,
bound response size, and restrict response content types.

The previous `zc` deep-research fetch path followed redirects automatically and
read the complete response before truncating decoded text. That allowed:

- loopback, private, link-local, and cloud metadata targets;
- redirects from a public URL to a private target;
- arbitrary destination ports;
- binary response ingestion; and
- avoidable memory growth from large responses.

`zc` now implements the behavior independently in `wire.web_fetcher` using
only the Python standard library. The fetcher:

- permits only HTTP and HTTPS on ports 80 and 443;
- rejects URL user information;
- resolves and validates every address as globally routable;
- handles IPv4-mapped IPv6 addresses;
- disables automatic redirects and revalidates each `Location`;
- accepts only bounded textual, JSON, XML, or XHTML responses; and
- reads at most `max_bytes + 1` bytes before rejecting an oversized payload.

The existing retry/error hierarchy remains responsible for transient HTTP and
network failures. Policy failures are not retried.

### Not adopted: provider registry

SHEN AI implements separate adapters for Anthropic, OpenAI, Google, Azure,
Groq, Mistral, Ollama, and custom endpoints. `zc` now embeds LiteLLM Router,
which provides a broader normalized provider surface with centralized routing,
fallbacks, and usage normalization. Porting another provider registry would
create duplicate configuration and credential paths.

### Not adopted: regex code validator

SHEN AI's validator approximates JavaScript and TypeScript parsing by removing
type syntax with regular expressions before using `vm.Script`. This can
misclassify valid code and does not replace language-native compilation,
Ruff, TypeScript, or repository tests. `zc` retains executable validators.

### Deferred: project genome and blast-radius analysis

SHEN AI provides an in-memory graph store and regex-based TypeScript import
scanner. The graph algorithms are useful, but the scanner does not provide the
cross-language, import-resolution, incremental invalidation, and symlink
boundaries required by `zc`. A future implementation should use Python AST and
TypeScript compiler APIs and persist only validated workspace-relative paths.

### Not adopted: plugin sandbox

SHEN AI's plugin sandbox is a JavaScript `vm` and source-pattern filter. It is
not an operating-system security boundary. `zc` must continue to rely on
explicit permissions and process/filesystem sandboxing for untrusted tools.

### Not adopted: project scaffold templates

AgentForge safely checks template destination containment, but its output
templates introduce multi-service Docker/Vercel deployment assumptions that
conflict with `zc`'s local-first, no-recurring-platform-cost architecture.
`zc` project templates are server-owned workflow definitions rather than file
scaffolds, so there is no equivalent untrusted path expansion to port.

## Verification Contract

The adopted fetch behavior is covered without network access:

- private, loopback, link-local metadata, IPv6 loopback, and mapped IPv4;
- unsupported schemes, embedded credentials, and nonstandard ports;
- public-to-private redirects;
- bounded reads for oversized responses;
- binary content rejection; and
- decoded text truncation.

The relevant checks are:

```bash
pytest -q tests/test_web_fetcher.py tests/test_resilience.py
ruff check src/wire/web_fetcher.py src/wire/zc_research.py tests/test_web_fetcher.py
```

No package, hosted service, database, queue, or recurring-cost dependency was
introduced.
