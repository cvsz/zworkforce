# Sandbox runtime and isolation policy

`zeaz-sandbox` uses a dedicated rootless Docker daemon. Startup calls
`docker info` through an absolute executable and an explicit rootless Unix
socket; the service refuses to run unless the daemon reports rootless,
built-in seccomp, and AppArmor support. A rootful daemon is never accepted as
a fallback.

## Container boundary

Before container creation, the backend verifies that the approved digest
reference appears in the locally installed image's `RepoDigests` and rejects
images declaring implicit volumes. It never pulls an image. Job argv is passed
with `--entrypoint` and an argument vector; no shell evaluates it.

Every job container has:

- UID/GID 65532, read-only root filesystem, and no inherited environment;
- all Linux capabilities dropped and `no-new-privileges`;
- built-in seccomp and an allow-listed AppArmor profile;
- private PID/IPC/UTS namespaces from the rootless runtime;
- CPU, memory plus swap, PID, file-size, descriptor, temporary-filesystem,
  output-byte, and wall-time limits;
- exactly one bind-mounted caller-owned, non-symlink workspace, read-only by
  default;
- a bounded `noexec,nosuid,nodev` temporary filesystem.

The backend labels every container for reconciliation. It force-removes the
container on timeout, output overflow, cancellation, output-consumer failure,
or normal completion.

## Egress

Normal jobs use `--network none`. Allow-list jobs receive a unique internal
Docker network with no external route. A separate, digest-pinned, non-root,
read-only SOCKS sidecar joins both that network and the rootless daemon's
external bridge. The job sees only the sidecar.

The proxy accepts exact approved host/port pairs. It resolves a domain once,
rejects non-global answers to prevent DNS rebinding into private services, and
connects directly to the validated IP. Loopback, link-local, multicast,
unspecified, and metadata addresses are always rejected. Explicit private IP
destinations remain possible only when the approval names that literal IP.
Connection count, idle time, and relayed bytes are bounded. The sidecar image
is built from `Dockerfile.sandbox-egress`, whose base image is digest-pinned.

## Output, receipts, and recovery

Stdout and stderr share one raw-byte budget. Literal secrets are redacted
before emission, including values split across read boundaries. Output sinks
have deadlines so a disconnected consumer cannot stall cleanup.

The private SQLite journal records a network lease before container creation
and the container ID immediately after creation. Every terminal attempt,
including invalid approval, cancellation, timeout, and cleanup failure,
produces a receipt bound to the approval, image digest, and complete policy
digest. Failed cleanup remains journaled. Startup reconciliation removes
labelled orphan containers, releases sidecar networks, and retains failures
for another retry.

## Host prerequisite

Production acceptance requires a live rootless daemon and the `docker-default`
AppArmor profile. This host currently has only a rootful system daemon and
Ubuntu's restricted unprivileged-user-namespace policy prevents starting a
rootless daemon without an administrator-installed AppArmor exception and
rootless networking helpers. The service correctly rejects that rootful
daemon; it must not be pointed at it for production.
