import assert from 'node:assert/strict';
import test from 'node:test';
import { createPgMembershipLookup } from '../pg-membership.mjs';

const identity = { login_role: 'zeaz_financial_membership_app_test', active_role: 'zeaz_financial_membership_app_test',
  rolsuper: false, rolbypassrls: false, rolcreaterole: false, rolcreatedb: false,
  rolreplication: false, financial_runtime_member: false };
const harness = ({ login = identity, rows = [{ membership_active: true, membership_role: 'billing_writer' }], fail = false } = {}) => {
  const queries = []; const releases = [];
  const client = { query: async (sql, params) => {
    queries.push({ sql, params });
    if (fail) throw new Error('database offline');
    return sql.includes('FROM pg_roles') ? { rows: [login] } : { rows };
  }, release: discarded => releases.push(discarded) };
  return { lookup: createPgMembershipLookup({ pool: { connect: async () => client },
    expectedLoginRole: 'zeaz_financial_membership_app_test' }), queries, releases };
};

test('reads active membership through parameterized security-definer function', async () => {
  const h = harness();
  assert.deepEqual(await h.lookup({ subject: 'subject-a', tenantId: 'tenant-a' }),
    { active: true, role: 'billing_writer' });
  assert.deepEqual(h.queries[1].params, ['subject-a', 'tenant-a']);
  assert.equal(h.queries[1].sql.includes('lookup_billing_membership($1, $2)'), true);
  assert.deepEqual(h.releases, [false]);
});
test('rejects untrusted input before connecting', async () => {
  let connects = 0;
  const lookup = createPgMembershipLookup({ pool: { connect: async () => { connects++; } },
    expectedLoginRole: 'zeaz_financial_membership_app_test' });
  for (const input of [{ subject: '', tenantId: 't' }, { subject: 'a', tenantId: ' t ' },
    { subject: 'a\n', tenantId: 't' }, { subject: 'a', tenantId: 'x'.repeat(129) }]) {
    await assert.rejects(lookup(input), e => e.status === 403);
  }
  assert.equal(connects, 0);
});
test('missing, revoked, and viewer memberships never confer billing write access', async () => {
  assert.deepEqual(await harness({ rows: [] }).lookup({ subject: 's', tenantId: 't' }), { active: false, role: null });
  assert.deepEqual(await harness({ rows: [{ membership_active: false, membership_role: 'billing_writer' }] }).lookup({ subject: 's', tenantId: 't' }), { active: false, role: 'billing_writer' });
  assert.deepEqual(await harness({ rows: [{ membership_active: true, membership_role: 'viewer' }] }).lookup({ subject: 's', tenantId: 't' }), { active: true, role: 'viewer' });
});
test('refuses privileged, wrong, or financial-runtime-member logins', async () => {
  for (const changed of [{ rolsuper: true }, { rolbypassrls: true },
    { financial_runtime_member: true }, { login_role: 'postgres' }, { active_role: 'zeaz_financial_runtime' }]) {
    const h = harness({ login: { ...identity, ...changed } });
    await assert.rejects(h.lookup({ subject: 's', tenantId: 't' }), e => e.status === 503);
    assert.deepEqual(h.releases, [true]);
  }
});
test('discards connections and fails closed on database failure or ambiguous rows', async () => {
  for (const options of [{ fail: true }, { rows: [{ membership_active: true, membership_role: 'billing_writer' }, { membership_active: true, membership_role: 'billing_writer' }] }, { rows: [{ membership_active: 'true', membership_role: 'billing_writer' }] }]) {
    const h = harness(options);
    await assert.rejects(h.lookup({ subject: 's', tenantId: 't' }), e => e.status === 503);
    assert.deepEqual(h.releases, [true]);
  }
});
test('rejects unsafe configuration', () => {
  assert.throws(() => createPgMembershipLookup({}), e => e.status === 503);
  assert.throws(() => createPgMembershipLookup({ pool: { connect() {} }, expectedLoginRole: 'postgres' }), e => e.status === 503);
});
