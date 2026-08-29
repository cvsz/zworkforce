# Z.A.R.V.I.S. Architecture

Status: **initial vertical slice**  
Epic: **#148**  
Name: **Z Platform Adaptive Reasoning, Voice, Intelligence & Service System**

Z.A.R.V.I.S. is an original Z Platform assistant architecture inspired by the general concept of cinematic multimodal assistants. It does not reproduce Marvel branding, voices, character personalities, visual identity, or copyrighted story elements.

## First vertical slice

```text
Browser microphone or text input
            |
            | transcript only
            v
apps/zarvis-console
            |
            | POST /v1/commands
            v
services/zarvis-orchestrator
      | intent: github.repository.status
      | capability: read_only
      v
GitHub REST API (fixed host)
            |
            v
normalized result + speech text + audit event
            |
            +--> browser speech synthesis
            +--> audit sink / stdout JSON event
```

The slice proves the end-to-end control plane without introducing autonomous mutation, durable memory, camera access, continuous listening, or device control.

## Components

### `apps/zarvis-console`

- Hosts a same-origin command UI.
- Uses browser speech recognition only when explicitly activated by the user.
- Sends a transcript, locale, modality, and opaque session ID.
- Proxies to one configured orchestrator origin.
- Uses browser speech synthesis for the returned `speech.text`.
- Displays the normalized repository result and audit event ID.

The console does not receive or forward provider credentials or GitHub credentials.

### `services/zarvis-orchestrator`

- Validates the versioned command contract.
- Resolves either an explicit read-only tool request or a constrained repository-status intent.
- Invokes a typed tool adapter.
- Produces a speech-ready summary.
- Emits a structured audit event for success and failure.
- Fails closed for unsupported and mutating tool names.

### `github.repository.status`

- Constructs the URL internally from validated `owner` and `repo` segments.
- Permits only `GET https://api.github.com/repos/{owner}/{repo}`.
- Rejects redirects.
- Applies an abort timeout.
- Normalizes the upstream response to an allowlisted result shape.
- Keeps the optional `GITHUB_TOKEN` exclusively in the orchestrator process.

### Contracts

The slice adds three JSON Schemas:

- `zarvis.command.requested.v1`
- `zarvis.command.completed.v1`
- `zarvis.audit.tool-executed.v1`

Contracts are additive and do not modify the existing agent job contracts.

## Trust boundaries

| Boundary | Untrusted input | Enforcement |
|---|---|---|
| Browser → console | Transcript and session fields | Same-origin POST, JSON media type, 32 KiB body limit |
| Console → orchestrator | Versioned command payload | Fixed upstream URL; no credential forwarding |
| Orchestrator → tool | Intent and repository target | Typed tool allowlist and strict segment validation |
| Tool → GitHub | Repository identifier | Internally constructed HTTPS URL, GET only, redirect denied |
| Tool result → user/audit | GitHub response | Allowlisted normalized fields; no raw headers or response body |

## Compatibility

- The existing `apps/zvoice`, `services/voice-gateway`, `services/voice-agent`, `services/agent-orchestrator`, and `services/ai-gateway` remain unchanged.
- The new console can later exchange browser speech recognition for the existing local real-time voice path without changing the command contract.
- The new orchestrator is a narrow façade for Z.A.R.V.I.S. sessions. Durable agent plans will reuse or adapt the existing agent-orchestrator boundary in a later vertical slice.

## Next slices

1. Connect `zvoice` streaming sessions to `zarvis.command.requested.v1`.
2. Persist command and audit events through the platform event/outbox boundary.
3. Add approval-state contracts before any mutating tool.
4. Add working-memory context with retention and user deletion controls.
5. Add document and screen perception only behind explicit session consent.
