# Production Deployment Runbook

Step-by-step production deployment guide for Zok.

---

## Table of Contents

1. [Pre-Deployment Checklist](#1-pre-deployment-checklist)
2. [Deployment Steps](#2-deployment-steps)
3. [Post-Deployment Verification](#3-post-deployment-verification)
4. [Rollback Procedure](#4-rollback-procedure)
5. [Incident Response Playbook](#5-incident-response-playbook)

---

## 1. Pre-Deployment Checklist

### Code Quality

- [ ] `npm test` passes (all server + frontend tests green)
- [ ] `npm run lint` passes (0 errors)
- [ ] `npm run typecheck` passes (0 errors)
- [ ] GPG-signed commit present on main
- [ ] `CHANGELOG.md` updated

### Infrastructure

- [ ] Production database migration scripts reviewed (`migrations/`)
- [ ] Database backup completed
- [ ] Environment variables configured in production secrets manager
- [ ] SSL certificates valid and not expiring within 7 days
- [ ] CDN cache invalidated (if applicable)
- [ ] Feature flags reviewed for production rollout

### Security

- [ ] Dependency audit clean (`npm audit` — no high/critical)
- [ ] Webhook secrets rotated and stored securely
- [ ] API keys scoped to minimum required permissions
- [ ] Rate limiting rules configured
- [ ] WAF rules reviewed

### Performance

- [ ] Bundle sizes within budget (`npm run analyze:bundle`)
- [ ] Core Web Vitals budgets validated in staging
- [ ] Database indexes verified on large tables
- [ ] Connection pool sized appropriately

### Communication

- [ ] Stakeholders notified of deployment window
- [ ] On-call engineer identified and briefed
- [ ] Incident bridge link created (e.g., Zoom, Slack huddle)
- [ ] Status page updated (if applicable)

---

## 2. Deployment Steps

### Step 1: Pull Latest Code

```bash
git fetch origin
git checkout main
git pull origin main
git log --oneline -5
```

### Step 2: Install Dependencies

```bash
npm ci --production=false
```

### Step 3: Run Full Test Suite

```bash
npm test
npm run lint
npm run typecheck
```

**Expected result**: All commands pass. If any fail, abort deployment and escalate.

### Step 4: Build Application

```bash
npm run build
```

**Expected result**: Build completes without errors. Dist artifacts generated.

### Step 5: Database Migrations

```bash
# Dry-run first (if supported by migration tool)
npm run db:migrate:dry

# Apply migrations
npm run db:migrate
```

**Expected result**: Migrations apply cleanly. No rollback required.

### Step 6: Deploy Application

```bash
# Example using PM2
pm2 stop zok
pm2 start server.js --name zok

# Or using Docker
docker compose up -d --force-recreate
```

### Step 7: Verify Health

```bash
curl -f https://zok.zeaz.dev/api/health
curl -f https://zok.zeaz.dev/api/observability/health
```

**Expected result**: `200 OK` from both endpoints.

### Step 8: Smoke Tests

```bash
# API smoke tests
npm run test:smoke

# Webhook verification (if applicable)
npm run test:webhook:smoke
```

---

## 3. Post-Deployment Verification

### Immediate Checks (0–5 min)

| Check | Command / Action | Expected |
|-------|------------------|----------|
| Server process running | `pm2 status` or `docker ps` | zok process up |
| Health endpoint | `curl /api/health` | 200 OK |
| Database connection | `curl /api/observability/db-health` | Connected |
| Error rate | Monitor dashboard | < 1% |
| Response time p95 | Monitor dashboard | < 200 ms |

### Short-term Checks (5–30 min)

- [ ] Core Web Vitals dashboard shows green metrics
- [ ] No spike in 5xx errors
- [ ] Campaign worker processing messages normally
- [ ] Webhook delivery rates normal
- [ ] Frontend bundle loaded successfully (check Network tab)

### Ongoing Monitoring (24h)

- [ ] Error budget tracking
- [ ] Database query performance
- [ ] Memory / CPU utilization
- [ ] Disk usage (especially if logs are local)
- [ ] Customer-reported issues

### Frontend Verification

```bash
# Lighthouse CI (if configured)
lhci autorun

# Accessibility audit
npm run test:a11y

# Performance test
npm run test:perf
```

---

## 4. Rollback Procedure

### When to Rollback

- Error rate > 5% sustained for 5 minutes
- Core Web Vitals failing for > 10% of users
- Database migration failure
- Critical feature completely broken
- Security vulnerability introduced

### Rollback Steps

1. **Alert the team**: Post in #incidents Slack channel
2. **Stop new traffic**: Enable maintenance mode if needed
3. **Revert code**:
   ```bash
   git revert HEAD
   git push origin main
   npm ci
   npm run build
   pm2 restart zok
   ```
4. **Revert database** (if migration caused issue):
   ```bash
   npm run db:migrate:rollback
   ```
5. **Verify rollback**:
   ```bash
   curl -f https://zok.zeaz.dev/api/health
   npm run test:smoke
   ```
6. **Confirm recovery**: Post status update
7. **Root cause analysis**: Schedule post-mortem within 24h

### Rollback Time Targets

| Phase | Target |
|-------|--------|
| Detect issue | 5 min |
| Decide to rollback | 5 min |
| Execute rollback | 10 min |
| Verify recovery | 5 min |
| **Total** | **25 min** |

---

## 5. Incident Response Playbook

### Severity Levels

| Level | Description | Response Time | Example |
|-------|-------------|---------------|---------|
| SEV1 | Complete outage | 15 min | API unreachable, DB down |
| SEV2 | Major degradation | 30 min | Error rate > 5%, slow responses |
| SEV3 | Minor impact | 2h | Single feature broken, non-critical |
| SEV4 | Cosmetic / future | Next business day | UI glitch, typo |

### SEV1 Playbook

1. **Incident commander assigned**
2. **Post in #incidents** with severity and brief description
3. **Assess impact** — users affected, revenue at risk
4. **Immediate mitigation** — rollback if code deploy; scale if infra
5. **Communication** — update status page every 15 min
6. **Resolution** — verify fix, confirm recovery
7. **Post-mortem** — RCA within 24h, action items in Jira

### SEV2 Playbook

1. **Incident lead assigned**
2. **Assess blast radius**
3. **Mitigate** — feature flag disable, rate limit adjust
4. **Monitor** — watch dashboards for 30 min
5. **Post-incident review** — if unresolved in 4h, escalate to SEV1

### SEV3 Playbook

1. **Acknowledge** in support queue
2. **Fix in next sprint** or hotfix if critical path
3. **Document** workaround for support team

### SEV4 Playbook

1. **Log ticket**
2. **Schedule fix** for next regular sprint

### Communication Templates

**Initial incident post**:
```
[SEV1] zok.app — API unreachable
Impact: All users
Started: <timestamp>
Incident commander: @<name>
Status: Investigating
```

**Update post**:
```
[SEV1] UPDATE — Identified root cause: database connection pool exhausted.
Mitigation: Restarting application servers.
ETA to recovery: 10 min.
```

**Resolved post**:
```
[SEV1] RESOLVED — Application servers restarted, pool size increased.
All systems operational.
Post-mortem scheduled for <date>.
```

---

## Appendix

### Emergency Contacts

| Role | Contact |
|------|---------|
| On-call engineer | Check PagerDuty / OpsGenie |
| Database admin | Check internal directory |
| Security officer | Check internal directory |
| Engineering lead | Check internal directory |

### Useful Links

- Production monitoring: `<monitoring-url>`
- Log aggregation: `<logging-url>`
- Deployment pipeline: `<ci-cd-url>`
- Status page: `<status-page-url>`

### Related Documents

- [`docs/gold-master-checklist.md`](../gold-master-checklist.md)
- [`docs/operator-runbook-postgresql-cutover.md`](../operator-runbook-postgresql-cutover.md)
- [`docs/architecture.md`](../architecture.md)
