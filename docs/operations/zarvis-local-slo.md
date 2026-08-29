# Z.A.R.V.I.S. Local Service Objectives

These objectives apply to a single-owner Ubuntu/Linux host or VM under normal local load. They are not public-cloud availability claims.

## Availability and recovery

| Objective | Target | Automated evidence |
|---|---:|---|
| Loopback health requests | 100% success during bounded release sample | Local release acceptance |
| Owner status requests | 100% success during bounded release sample | Local release acceptance |
| Health/status p95 latency | ≤ 750 ms | Local release acceptance |
| Service restart recovery | ≤ 60 seconds | Restart drill |
| Durable action state after restart | Preserved | Restart and restore verification |
| Durable proactive state after restart | Preserved | Restart and restore verification |
| Backup integrity | SHA-256 verified before restore | Backup manifest and restore script |
| Old credentials after rotation | 100% rejected | Rotation verification |
| New scoped credentials after rotation | 100% accepted only at intended boundary | Rotation verification |

## Safety objectives

- zero autonomous proactive mutations;
- zero mutations without exact owner approval;
- zero configured credentials in response bodies or evidence artifacts;
- zero wildcard listeners for local Z.A.R.V.I.S. ports;
- zero unallowlisted capabilities or monitoring targets;
- emergency stop revokes all pending/approved local actions before resume;
- restored proactive handoffs remain `requires_owner_approval: true` and `executed: false`.

## Resource objectives

| Service | Memory limit | CPU limit | PID limit |
|---|---:|---:|---:|
| Action Gateway | 256 MiB | 1 CPU | 128 |
| Action Worker | 128 MiB | 0.5 CPU | 128 |
| Proactive Service | 256 MiB | 1 CPU | 128 |
| Proactive Worker | 128 MiB | 0.5 CPU | 128 |

All containers use read-only root filesystems, dropped Linux capabilities, no-new-privileges, bounded temporary filesystems, and bounded file descriptors.

## Measurement limitations

CI evidence is a reproducible release gate, not a benchmark of the owner's actual machine. CPU contention, disk performance, virtualization, antivirus, and host configuration can change observed latency. The manual owner checklist records actual-host results separately without weakening automated gates.
