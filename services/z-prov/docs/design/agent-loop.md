# Agent loop design

Status: implemented for model turns and explicit tool-result resumption.

`AgentLoop` is a provider-neutral immutable-session state machine. It accepts
user content, asks a narrow `ModelClient` protocol for the next assistant turn,
and returns either `completed` or `requires_action`. It never invokes a tool.
Callers must later submit exactly one result for every pending call; missing,
duplicate, injected, and unrelated call IDs are rejected before another model
request. The permission layer will mediate that explicit gap.

`ZeazProviderClient` is the production model client. It sends non-streaming
requests to the gateway's `/v1/responses` endpoint using only stable
`zeaz-*` aliases. It disables upstream storage, allows plaintext HTTP only for
loopback, forbids URL credentials, does not follow redirects, bounds time and
response bytes, parses gateway output as untrusted data, and never places its
gateway client key in session state.

The wire shape follows the public OpenAI Responses API function-calling
contract: assistant `function_call` items are replayed with corresponding
`function_call_output` items on resumption. ZeaZ Provider translates these
items and Responses-style function definitions for non-native providers.

Public specification:

- https://platform.openai.com/docs/api-reference/responses
- https://platform.openai.com/docs/guides/function-calling

Streaming, automatic tool dispatch, permission policy, persistence, budgets,
and compaction are deliberately left to their separate roadmap tasks.
