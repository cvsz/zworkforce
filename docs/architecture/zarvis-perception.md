# Z.A.R.V.I.S. Consent-Based Perception Architecture

Epic: #148
Issue: #153

## Flow

```text
Owner purpose + modalities
  -> exact consent digest + nonce
  -> active time-bounded session
  -> one-shot upload/screen/camera snapshot
  -> in-memory validation and redaction
  -> encrypted analysis + provenance
  -> owner history/delete/retention purge
```

## Consent model

A perception session binds:

- purpose;
- allowed modalities;
- retention period;
- immutable owner identity;
- SHA-256 consent digest;
- one-time nonce;
- consent and active-session expiry.

Media submitted outside the allowed modalities, before activation, after stop, or after expiry is rejected.

## Capture boundary

The browser uses `getDisplayMedia` or `getUserMedia` only after an explicit owner click. One frame is copied to a canvas and all media tracks are stopped in `finally`. There is no polling loop, background capture, audio capture, wake-word capture, biometric matching, or persistent MediaStream.

## Data lifecycle

Raw media is decoded into a bounded in-memory buffer, validated, hashed, analyzed, then overwritten. The service persists only an AES-256-GCM encrypted event containing:

- redacted text excerpt/summary or image dimensions;
- untrusted-content and policy-isolation flags;
- provenance, SHA-256, media size, modality, media type, capture time, and analyzer version;
- retention expiry.

The journal path is fixed. Session IDs, filenames, and source names never influence filesystem paths.

## Prompt-injection isolation

Text extracted from documents is untrusted data. Injection-like phrases are replaced with `[UNTRUSTED_INSTRUCTION]`. Results always contain:

```json
{
  "untrusted_content": true,
  "policy_effect": "none",
  "tool_grants": [],
  "raw_media_retained": false
}
```

No perception result can mutate the system prompt, owner identity, capability registry, approval state, task queue, memory, or automation policy.

## Adapter boundary

The local adapter intentionally provides deterministic redaction and metadata analysis without a model dependency. A future vision/document model adapter must preserve the same pre-model redaction, exact consent, provenance, retention, encrypted persistence, and deletion semantics.
