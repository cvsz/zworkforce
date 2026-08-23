---
name: zworkforce-zarvis-voice-ui
description: Implement and review zWorkforce Z.A.R.V.I.S. browser voice UI, push-to-talk, realtime audio, animated orb state, and voice BFF changes without weakening auth, secret, approval, or accessibility boundaries.
---

# zWorkforce Z.A.R.V.I.S. voice UI

Use this skill when changing the root zWorkforce dashboard voice card, ZVoice, browser audio capture/playback, voice session bootstrap, realtime event handling, or voice-related static assets.

## Required reading

Read the narrow relevant files before editing:

- `AGENTS.md`
- `packages/zarvis/AGENTS.md`
- `ROADMAPS.md`
- `exec-planning-zarvis.md`
- `packages/zarvis/docs/architecture/openjarvis-upgrade-map.md`
- `packages/zarvis/docs/architecture/voice-agent.md`
- `packages/zarvis/apps/zvoice/README.md`
- `packages/zarvis/apps/zvoice/public/app.js`
- `packages/zarvis/apps/zvoice/server.mjs`
- `zworkforce/static/index.html`
- `zworkforce/static/app.js`
- `zworkforce/static/styles.css`

## Architecture rules

1. Reuse the existing ZVoice realtime protocol and voice services. Do not create a parallel record/upload assistant stack unless a documented fallback explicitly requires it.
2. Do not iframe ZVoice by weakening its defensive frame policy. Build a dashboard-native presentation using shared browser-safe client logic.
3. Browser code MUST NOT receive provider keys, service tokens, edge secrets, database credentials, GitHub tokens, or internal action credentials.
4. Tenant and subject authority comes from authenticated server-side context. Never trust arbitrary client-supplied identity as authorization.
5. Spoken text is input, not mutation approval. Approval-required actions remain behind the existing task/action approval contracts.
6. Keep microphone capture visibly user-controlled. Stop tracks, AudioNodes, sockets, timers and queued playback on cancellation, navigation, disconnect and error paths.
7. Preserve interruption/barge-in behavior.
8. Static assets must be compatible with the repository CSP and must not require unsafe inline script/eval.

## Canonical voice state

Use one presentation-independent state model:

```text
idle
arming
listening
transcribing
thinking
approval_required
speaking
interrupted
muted
error
```

Do not infer security state from animation state. Authorization/approval comes from server responses/contracts.

## Push-to-talk requirements

- Pointer/touch press starts PTT after microphone/session readiness checks.
- Pointer release/cancel ends the turn.
- `Space` may act as hold-to-talk only when focus is outside editable/form controls.
- Ignore keyboard auto-repeat.
- Provide a click/toggle fallback for accessibility.
- `Escape` cancels assistant playback/current response, not an approval record.
- Prevent multiple simultaneous capture sessions.
- Show permission denied, backend unavailable, disconnected and retry states explicitly.

## Animated orb requirements

The orb is a state visualization, not decoration-only UI.

- `idle`: low-energy ambient motion.
- `arming`: bounded pulse/spinner.
- `listening`: microphone-level/reactive expansion where available.
- `transcribing`: directional scan or restrained activity.
- `thinking`: orbital/processing motion.
- `speaking`: response-reactive waveform/glow where available.
- `approval_required`: stable warning state; do not mimic success.
- `error`: explicit text/icon plus visual state.

Respect `prefers-reduced-motion`; all critical information must also be available as text/live-region state.

## Implementation workflow

1. Identify whether logic belongs to presentation, shared browser voice client, zWorkforce BFF, zvoice server, voice gateway, or voice agent.
2. Prefer extracting reusable protocol/audio logic from ZVoice over copying it into the dashboard.
3. Add the narrow test before or with behavior changes.
4. Test cleanup and failure paths, not only successful speech.
5. Inspect generated/static output for credential names, tokens or internal URLs that should not be exposed.
6. Update voice architecture/operations docs for contract/config changes.

## Required test cases

Cover as applicable:

- microphone unsupported/denied;
- PTT press, release, pointer cancel and keyboard lifecycle;
- session/ticket rejection and expiry;
- WebSocket connect/error/close;
- speech started/stopped;
- partial/final transcript handling;
- assistant audio/text response;
- barge-in/cancel;
- reconnect/cleanup;
- approval-required state;
- tenant/auth denial;
- upstream timeout/failure;
- reduced-motion/accessibility hooks;
- no server secret in browser payload/static assets.

## Validation

Run the smallest relevant tests, then:

```bash
python3 -m compileall -q zworkforce tests
PYTHONPATH=. python3 -m unittest discover -s tests -v
pnpm --dir packages/zarvis test
```

If voice runtime dependencies or containers change, also run the documented voice service health/smoke checks. GitHub Actions remains the final release gate.