import { createHash, randomUUID } from 'node:crypto';

export const ZARVIS_OWNER_GITHUB_ID = '4076926';
export const ZARVIS_OWNER_USER_ID = 'github:4076926';
export const ZARVIS_OWNER_TENANT_ID = 'owner-4076926';
export const LOCAL_CAPABILITY = 'sandbox.preference.set';

const APPROVAL_TTL_MS = 15 * 60 * 1000;
const KEY_PATTERN = /^[a-z][a-z0-9_.-]{0,63}$/;
const TERMINAL_STATUSES = new Set(['executed', 'rolled_back', 'expired', 'revoked', 'failed']);

export class ActionError extends Error {
  constructor(code, message, status = 400) {
    super(message);
    this.name = 'ActionError';
    this.code = code;
    this.status = status;
  }
}

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stable(value[key])]));
  }
  return value;
}

function digest(value) {
  return createHash('sha256').update(JSON.stringify(stable(value))).digest('hex');
}

function sameValue(left, right) {
  return JSON.stringify(left ?? null) === JSON.stringify(right ?? null);
}

function validatePreferenceInput(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    throw new ActionError('invalid_action', 'Action payload must be an object.');
  }
  if (input.capability !== LOCAL_CAPABILITY) {
    throw new ActionError('capability_denied', 'Capability is not in the local allowlist.', 403);
  }
  if (!KEY_PATTERN.test(input.key ?? '')) {
    throw new ActionError('invalid_preference_key', 'Preference key is invalid.');
  }
  if (typeof input.value !== 'string' || input.value.length > 512) {
    throw new ActionError('invalid_preference_value', 'Preference value must be a string up to 512 characters.');
  }
  if (input.untrusted_content === true || input.policy_effect || input.tool_grants) {
    throw new ActionError('confused_deputy_denied', 'Untrusted content cannot request local capabilities.', 403);
  }
  return { capability: LOCAL_CAPABILITY, key: input.key, value: input.value };
}

function latestActions(events) {
  const actions = new Map();
  for (const event of events) {
    if (event?.action?.action_id) actions.set(event.action.action_id, event.action);
  }
  return actions;
}

function publicAction(action, replayed = false) {
  return { ...structuredClone(action), replayed };
}

export class ZarvisLocalActionRuntime {
  constructor({ store, now = () => new Date().toISOString(), idFactory = () => randomUUID() }) {
    if (!store) throw new TypeError('store is required');
    this.store = store;
    this.now = now;
    this.idFactory = idFactory;
  }

  async initialize() {
    await this.store.initialize();
  }

  async #actions() {
    return latestActions(await this.store.readEvents());
  }

  async #record(eventType, action, occurredAt = this.now()) {
    await this.store.appendEvent({
      event_id: this.idFactory(),
      event_type: eventType,
      occurred_at: occurredAt,
      action,
    });
    return action;
  }

  async #expire(current, now) {
    const expired = { ...current, status: 'expired', failure_code: 'approval_expired', updated_at: now };
    await this.#record('zarvis.action.expired.v1', expired, now);
    return expired;
  }

  async getAction(actionId) {
    const action = (await this.#actions()).get(actionId);
    if (!action) throw new ActionError('action_not_found', 'Action was not found.', 404);
    return publicAction(action);
  }

  async listActions() {
    return [...(await this.#actions()).values()]
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
      .map((action) => publicAction(action));
  }

  async preview(input) {
    const request = validatePreferenceInput(input);
    const state = await this.store.readState();
    if (state.emergency_stop) {
      throw new ActionError('emergency_stop_active', 'Local actions are disabled by emergency stop.', 423);
    }

    const now = this.now();
    const actionId = this.idFactory();
    const approvalNonce = this.idFactory();
    const approvalExpiresAt = new Date(new Date(now).getTime() + APPROVAL_TTL_MS).toISOString();
    const previousValue = Object.hasOwn(state.preferences, request.key) ? state.preferences[request.key] : null;
    const approvalDigest = digest({
      schema_version: 'zarvis.action.approval-payload.v1',
      action_id: actionId,
      capability: request.capability,
      key: request.key,
      previous_value: previousValue,
      next_value: request.value,
      owner_user_id: ZARVIS_OWNER_USER_ID,
      tenant_id: ZARVIS_OWNER_TENANT_ID,
      expires_at: approvalExpiresAt,
    });

    const action = {
      schema_version: 'zarvis.action.snapshot.v1',
      action_id: actionId,
      capability: request.capability,
      scope: 'owner-sandbox/preferences',
      mutating: true,
      reversible: true,
      status: 'pending_approval',
      owner_user_id: ZARVIS_OWNER_USER_ID,
      tenant_id: ZARVIS_OWNER_TENANT_ID,
      key: request.key,
      previous_value: previousValue,
      next_value: request.value,
      impact: {
        target: 'local owner sandbox preference store',
        external_side_effects: false,
        network_access: false,
        filesystem_scope: 'operator-controlled fixed local state file',
      },
      approval_digest: approvalDigest,
      approval_nonce: approvalNonce,
      approval_expires_at: approvalExpiresAt,
      approval_consumed_at: null,
      execution_id: null,
      executed_at: null,
      rollback_digest: null,
      rollback_nonce: null,
      rolled_back_at: null,
      failure_code: null,
      created_at: now,
      updated_at: now,
    };
    await this.#record('zarvis.action.previewed.v1', action, now);
    return publicAction(action);
  }

  async approve(actionId, { approval_digest: approvalDigest, approval_nonce: approvalNonce }) {
    const current = (await this.#actions()).get(actionId);
    if (!current) throw new ActionError('action_not_found', 'Action was not found.', 404);
    if (current.status === 'approved') return publicAction(current, true);
    if (current.status !== 'pending_approval') {
      throw new ActionError('invalid_action_state', 'Only pending actions can be approved.', 409);
    }

    const now = this.now();
    if (now > current.approval_expires_at) {
      await this.#expire(current, now);
      throw new ActionError('approval_expired', 'Approval window has expired.', 410);
    }
    if (approvalDigest !== current.approval_digest || approvalNonce !== current.approval_nonce) {
      throw new ActionError('approval_mismatch', 'Approval proof does not match the exact preview.', 403);
    }

    const approved = {
      ...current,
      status: 'approved',
      approval_consumed_at: now,
      approval_nonce: null,
      updated_at: now,
    };
    await this.#record('zarvis.action.approved.v1', approved, now);
    return publicAction(approved);
  }

  async execute(actionId) {
    const current = (await this.#actions()).get(actionId);
    if (!current) throw new ActionError('action_not_found', 'Action was not found.', 404);
    if (current.status === 'executed') return publicAction(current, true);
    if (current.status !== 'approved') {
      throw new ActionError('invalid_action_state', 'Action must be approved before execution.', 409);
    }

    const now = this.now();
    if (now > current.approval_expires_at) {
      await this.#expire(current, now);
      throw new ActionError('approval_expired', 'Approved action expired before worker execution.', 410);
    }

    const state = await this.store.readState();
    if (state.emergency_stop) {
      throw new ActionError('emergency_stop_active', 'Local actions are disabled by emergency stop.', 423);
    }
    const observed = Object.hasOwn(state.preferences, current.key) ? state.preferences[current.key] : null;
    if (!sameValue(observed, current.previous_value)) {
      throw new ActionError('stale_preview', 'Local state changed after preview; create a new preview.', 409);
    }

    const executionId = this.idFactory();
    const rollbackNonce = this.idFactory();
    await this.store.writeState({
      ...state,
      preferences: { ...state.preferences, [current.key]: current.next_value },
      updated_at: now,
    });

    const rollbackDigest = digest({
      schema_version: 'zarvis.action.rollback-payload.v1',
      action_id: current.action_id,
      execution_id: executionId,
      key: current.key,
      previous_value: current.previous_value,
      next_value: current.next_value,
      owner_user_id: ZARVIS_OWNER_USER_ID,
      tenant_id: ZARVIS_OWNER_TENANT_ID,
    });
    const executed = {
      ...current,
      status: 'executed',
      execution_id: executionId,
      executed_at: now,
      rollback_digest: rollbackDigest,
      rollback_nonce: rollbackNonce,
      updated_at: now,
    };
    await this.#record('zarvis.action.executed.v1', executed, now);
    return publicAction(executed);
  }

  async rollback(actionId, { rollback_digest: rollbackDigest, rollback_nonce: rollbackNonce }) {
    const current = (await this.#actions()).get(actionId);
    if (!current) throw new ActionError('action_not_found', 'Action was not found.', 404);
    if (current.status === 'rolled_back') return publicAction(current, true);
    if (current.status !== 'executed') {
      throw new ActionError('invalid_action_state', 'Only executed actions can be rolled back.', 409);
    }
    if (rollbackDigest !== current.rollback_digest || rollbackNonce !== current.rollback_nonce) {
      throw new ActionError('rollback_mismatch', 'Rollback proof does not match the execution.', 403);
    }

    const state = await this.store.readState();
    const observed = Object.hasOwn(state.preferences, current.key) ? state.preferences[current.key] : null;
    if (!sameValue(observed, current.next_value)) {
      throw new ActionError('rollback_state_conflict', 'Local state changed after execution.', 409);
    }

    const now = this.now();
    const preferences = { ...state.preferences };
    if (current.previous_value === null) delete preferences[current.key];
    else preferences[current.key] = current.previous_value;
    await this.store.writeState({ ...state, preferences, updated_at: now });

    const rolledBack = {
      ...current,
      status: 'rolled_back',
      rollback_nonce: null,
      rolled_back_at: now,
      updated_at: now,
    };
    await this.#record('zarvis.action.rolled-back.v1', rolledBack, now);
    return publicAction(rolledBack);
  }

  async emergencyStop(reason = 'owner_requested') {
    const now = this.now();
    const state = await this.store.readState();
    await this.store.writeState({
      ...state,
      emergency_stop: true,
      emergency_reason: String(reason).slice(0, 256),
      updated_at: now,
    });

    let revoked = 0;
    for (const current of (await this.#actions()).values()) {
      if (TERMINAL_STATUSES.has(current.status)) continue;
      await this.#record('zarvis.action.revoked.v1', { ...current, status: 'revoked', updated_at: now }, now);
      revoked += 1;
    }
    return { emergency_stop: true, revoked, occurred_at: now };
  }

  async resume({ confirmation }) {
    if (confirmation !== 'RESUME_LOCAL_ACTIONS') {
      throw new ActionError('resume_confirmation_required', 'Exact resume confirmation is required.', 403);
    }
    const now = this.now();
    const state = await this.store.readState();
    await this.store.writeState({
      ...state,
      emergency_stop: false,
      emergency_reason: null,
      updated_at: now,
    });
    return { emergency_stop: false, occurred_at: now };
  }

  async status() {
    const state = await this.store.readState();
    return {
      owner_user_id: ZARVIS_OWNER_USER_ID,
      tenant_id: ZARVIS_OWNER_TENANT_ID,
      local_only: true,
      bind_default: '127.0.0.1',
      emergency_stop: state.emergency_stop,
      emergency_reason: state.emergency_reason,
      allowed_capabilities: [LOCAL_CAPABILITY],
      external_side_effects: false,
    };
  }
}

export { digest as createActionDigest };
