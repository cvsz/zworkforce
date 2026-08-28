# Operational Ownership

Initial state: `PENDING_OPERATOR`

Production release approval is invalid until accountable people, backups, escalation paths, and rollback authority are recorded. Group names must resolve to active on-call contacts.

## Ownership matrix

| Responsibility | Primary owner | Backup owner | Contact/on-call path | Authority |
|---|---|---|---|---|
| Incident command | `<owner>` | `<backup>` | `<channel-or-pager>` | Declare incident and coordinate response |
| Application operations | `<owner>` | `<backup>` | `<contact>` | Operate application services |
| Platform/infrastructure | `<owner>` | `<backup>` | `<contact>` | Operate cluster, network, data services |
| Security incident | `<owner>` | `<backup>` | `<contact>` | Containment and security escalation |
| Release operator | `<owner>` | `<backup>` | `<contact>` | Execute approved deployment only |
| Production approver | `<owner>` | `<backup>` | `<contact>` | Issue explicit GO/NO-GO |
| Rollback owner | `<owner>` | `<backup>` | `<contact>` | Trigger and supervise rollback |
| Communications | `<owner>` | `<backup>` | `<contact>` | Stakeholder and status communication |

## Escalation policy

| Severity | Initial response target | Escalation target | Decision authority |
|---|---|---|---|
| SEV-1 | `<minutes>` | `<path>` | `<role>` |
| SEV-2 | `<minutes>` | `<path>` | `<role>` |
| SEV-3 | `<minutes>` | `<path>` | `<role>` |

## Separation of duties

- The production approver must not silently substitute for the release operator.
- The release operator may deploy only the explicitly approved commit and image digests.
- The rollback owner has authority to halt or reverse the release when abort criteria are met.
- Exceptions require a documented, time-bounded risk acceptance by an authorized owner.

## Operator readiness gate

`PENDING_OPERATOR -> APPROVED_OPERATOR` requires:

1. every mandatory role has a named primary and backup;
2. contact paths have been tested or recently verified;
3. the production approver is authorized for the target environment;
4. incident and rollback authority are explicit;
5. the ownership record references the candidate release and approval window.

Approval reference: `<auditable-reference>`  
Approved by: `PHIPHAT PHOEMSUK` (CEO, ZeaZDev Company Limited; `seaza@msn.com`)
Approved at: `<ISO-8601>`
