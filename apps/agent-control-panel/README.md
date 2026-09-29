# zWorkforce Agent Control Panel

Next.js/React operator surface for the ZEAZ Center Control Plane.

The browser is a **view and approval surface**. It must not receive GitHub App
private keys, Cloudflare API tokens, provider credentials, database passwords,
or other server-side secrets.

See [ZEAZ Center Control Plane](../../docs/CENTER-CONTROL-PLANE.md).

## Planned operator surfaces

- Overview / SLO / queue / workforce state
- Repository fleet inventory
- Repository generator
- GitHub pull requests / Actions / security / releases
- Cloudflare hostname ownership and desired/effective state
- Production-readiness evidence
- AI agents / skills / automations
- Durable audit log

Mutation-capable controls must use the control-plane proposal/approval/execution
contract. The UI must not call privileged provider APIs directly.

## Dashboard theming

The application remains Next.js/React-native.

AdminLTE may be adopted as an optional visual/design adapter, but it is not a
required control-plane dependency. Any theme integration must preserve:

- Next.js routing and server/client boundaries;
- accessible keyboard/focus behavior;
- responsive layouts;
- existing auth/RBAC boundaries;
- testable loading/error/empty states;
- no secret-bearing browser configuration.

## Development

Use the repository package manager:

```bash
pnpm --filter agent-control-panel dev
pnpm --filter agent-control-panel lint
pnpm --filter agent-control-panel build
```

The local UI is not evidence that GitHub, Cloudflare, deployment, or production
mutation permissions are configured.
