# Z.A.R.V.I.S. Local Proactive Threat Model

| Threat | Control |
|---|---|
| Remote scheduler access | Loopback bind and loopback client enforcement |
| Worker changes owner policy | Worker has no owner token; internal route exposes tick only |
| Scheduler executes mutation | No action token, no action HTTP client, handoff fixes `executed: false` |
| Arbitrary URL monitoring | Fixed target registry; loopback HTTP `/healthz` validation only |
| SSRF and redirects | Non-loopback hosts, alternate paths, credentials, query, fragment, and redirects rejected |
| Prompt-injected schedule | Untrusted-content, policy-effect, and tool-grant fields fail closed |
| Notification flooding | Daily delivered budget, cooldown, fingerprint deduplication, confidence threshold |
| Quiet-hours bypass | Timezone and quiet-hours evaluation occurs server-side on every tick |
| Restart notification storm | Durable `next_run_at`, missed-run policy, last signal status, and cooldown history |
| Hidden continuous capture | No microphone, camera, screen, file, or media subscription adapter |
| Stale or duplicated schedule | Active check+target subscription is idempotent; owner can revoke immediately |
| Silent suppression | Every evaluation and suppression reason is append-only audited and visible |
| Cross-user notification | Immutable owner and tenant constants in policy, subscriptions, notifications, feedback, and handoff |
| Request-controlled path | One fixed event journal; IDs and targets are data only |
| Secret exposure | Health and notification payloads omit owner/worker tokens; adapter sends no credentials |

## Explicitly unavailable

The proactive service does not perform mutation, shell execution, web browsing, arbitrary HTTP checks, email/calendar operations, financial actions, device control, continuous sensing, or unattended destructive work.
