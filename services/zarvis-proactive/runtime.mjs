import { createHash, randomUUID } from 'node:crypto';

export const ZARVIS_OWNER_GITHUB_ID = '4076926';
export const ZARVIS_OWNER_USER_ID = 'github:4076926';
export const ZARVIS_OWNER_TENANT_ID = 'owner-4076926';

const DEFAULT_POLICY = Object.freeze({
  schema_version: 'zarvis.proactive.policy.v1',
  owner_user_id: ZARVIS_OWNER_USER_ID,
  tenant_id: ZARVIS_OWNER_TENANT_ID,
  timezone: 'Asia/Bangkok',
  quiet_hours_start: '22:00',
  quiet_hours_end: '07:00',
  daily_notification_budget: 5,
  default_cooldown_minutes: 60,
  confidence_threshold: 0.7,
  updated_at: null,
});

const NOTIFY_ON = new Set(['unhealthy', 'status_change', 'always']);
const MISSED_RUN_POLICIES = new Set(['skip', 'run_once']);
const FEEDBACK = new Set(['useful', 'irrelevant', 'false_positive']);

export class ProactiveError extends Error {
  constructor(code, message, status = 400) {
    super(message);
    this.name = 'ProactiveError';
    this.code = code;
    this.status = status;
  }
}

function clone(value) {
  return structuredClone(value);
}

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stable(value[key])]));
  }
  return value;
}

function hash(value) {
  return createHash('sha256').update(JSON.stringify(stable(value))).digest('hex');
}

function assertTrustedInput(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    throw new ProactiveError('invalid_payload', 'Payload must be an object.');
  }
  if (input.untrusted_content === true || input.policy_effect || input.tool_grants) {
    throw new ProactiveError('confused_deputy_denied', 'Untrusted content cannot create proactive policy or schedules.', 403);
  }
}

function validateTimezone(timezone) {
  if (typeof timezone !== 'string' || timezone.length > 64) {
    throw new ProactiveError('invalid_timezone', 'Timezone is invalid.');
  }
  try {
    new Intl.DateTimeFormat('en-US', { timeZone: timezone }).format(new Date());
  } catch {
    throw new ProactiveError('invalid_timezone', 'Timezone must be a valid IANA timezone.');
  }
  return timezone;
}

function validateTime(value, field) {
  if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(value ?? '')) {
    throw new ProactiveError('invalid_quiet_hours', `${field} must use HH:MM.`);
  }
  return value;
}

function integer(value, min, max, code) {
  if (!Number.isInteger(value) || value < min || value > max) {
    throw new ProactiveError(code, `Value must be an integer between ${min} and ${max}.`);
  }
  return value;
}

function number(value, min, max, code) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max) {
    throw new ProactiveError(code, `Value must be between ${min} and ${max}.`);
  }
  return value;
}

function validatePolicy(input, current, now) {
  assertTrustedInput(input);
  const policy = {
    ...current,
    timezone: input.timezone ?? current.timezone,
    quiet_hours_start: input.quiet_hours_start ?? current.quiet_hours_start,
    quiet_hours_end: input.quiet_hours_end ?? current.quiet_hours_end,
    daily_notification_budget: input.daily_notification_budget ?? current.daily_notification_budget,
    default_cooldown_minutes: input.default_cooldown_minutes ?? current.default_cooldown_minutes,
    confidence_threshold: input.confidence_threshold ?? current.confidence_threshold,
    updated_at: now,
  };
  validateTimezone(policy.timezone);
  validateTime(policy.quiet_hours_start, 'quiet_hours_start');
  validateTime(policy.quiet_hours_end, 'quiet_hours_end');
  integer(policy.daily_notification_budget, 0, 20, 'invalid_notification_budget');
  integer(policy.default_cooldown_minutes, 1, 1440, 'invalid_cooldown');
  number(policy.confidence_threshold, 0, 1, 'invalid_confidence_threshold');
  return policy;
}

function zonedParts(iso, timezone) {
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  });
  const parts = Object.fromEntries(
    formatter.formatToParts(new Date(iso)).filter((part) => part.type !== 'literal').map((part) => [part.type, part.value]),
  );
  return {
    date: `${parts.year}-${parts.month}-${parts.day}`,
    minute: Number(parts.hour) * 60 + Number(parts.minute),
  };
}

function timeMinutes(value) {
  const [hour, minute] = value.split(':').map(Number);
  return hour * 60 + minute;
}

function inQuietHours(iso, policy) {
  const current = zonedParts(iso, policy.timezone).minute;
  const start = timeMinutes(policy.quiet_hours_start);
  const end = timeMinutes(policy.quiet_hours_end);
  if (start === end) return false;
  return start < end ? current >= start && current < end : current >= start || current < end;
}

function stateFromEvents(events) {
  let policy = clone(DEFAULT_POLICY);
  const subscriptions = new Map();
  const notifications = new Map();
  const feedback = new Map();
  const handoffs = new Map();
  for (const event of events) {
    if (event.policy) policy = event.policy;
    if (event.subscription?.subscription_id) subscriptions.set(event.subscription.subscription_id, event.subscription);
    if (event.notification?.notification_id) notifications.set(event.notification.notification_id, event.notification);
    if (event.feedback?.notification_id) feedback.set(event.feedback.notification_id, event.feedback);
    if (event.handoff?.notification_id) handoffs.set(event.handoff.notification_id, event.handoff);
  }
  return { policy, subscriptions, notifications, feedback, handoffs };
}

function validateSignal(signal, subscription) {
  if (!signal || typeof signal !== 'object') throw new ProactiveError('invalid_signal', 'Adapter signal is invalid.', 502);
  if (!['healthy', 'unhealthy'].includes(signal.status)) throw new ProactiveError('invalid_signal', 'Signal status is invalid.', 502);
  number(signal.confidence, 0, 1, 'invalid_signal');
  if (typeof signal.summary !== 'string' || signal.summary.length < 1 || signal.summary.length > 500) {
    throw new ProactiveError('invalid_signal', 'Signal summary is invalid.', 502);
  }
  return {
    schema_version: 'zarvis.proactive.signal.v1',
    signal_id: randomUUID(),
    subscription_id: subscription.subscription_id,
    signal_key: String(signal.signal_key).slice(0, 128),
    status: signal.status,
    severity: ['info', 'warning', 'high'].includes(signal.severity) ? signal.severity : 'warning',
    confidence: signal.confidence,
    summary: signal.summary,
    source_url: String(signal.source_url).slice(0, 512),
    evidence: clone(signal.evidence ?? {}),
    proposed_action: signal.proposed_action ? clone(signal.proposed_action) : null,
  };
}

function shouldTrigger(subscription, signal) {
  if (subscription.notify_on === 'always') return true;
  if (subscription.notify_on === 'unhealthy') return signal.status === 'unhealthy';
  return subscription.last_signal_status !== null && subscription.last_signal_status !== signal.status;
}

export class ZarvisProactiveRuntime {
  constructor({ store, adapter, now = () => new Date().toISOString(), idFactory = () => randomUUID() }) {
    if (!store || !adapter) throw new TypeError('store and adapter are required');
    this.store = store;
    this.adapter = adapter;
    this.now = now;
    this.idFactory = idFactory;
  }

  async initialize() {
    await this.store.initialize();
  }

  async #state() {
    return stateFromEvents(await this.store.readEvents());
  }

  async #append(event_type, payload, occurred_at = this.now()) {
    await this.store.appendEvent({ event_id: this.idFactory(), event_type, occurred_at, ...payload });
  }

  async getPolicy() {
    return clone((await this.#state()).policy);
  }

  async updatePolicy(input) {
    const state = await this.#state();
    const now = this.now();
    const policy = validatePolicy(input, state.policy, now);
    await this.#append('zarvis.proactive.policy-updated.v1', { policy }, now);
    return clone(policy);
  }

  async createSubscription(input) {
    assertTrustedInput(input);
    if (input.check !== 'local.service.health') {
      throw new ProactiveError('check_denied', 'Check is not in the read-only allowlist.', 403);
    }
    if (!this.adapter.allowedTargets.includes(input.target)) {
      throw new ProactiveError('target_denied', 'Target is not allowlisted.', 403);
    }
    const intervalMinutes = integer(input.interval_minutes, 1, 1440, 'invalid_interval');
    const notifyOn = input.notify_on ?? 'unhealthy';
    if (!NOTIFY_ON.has(notifyOn)) throw new ProactiveError('invalid_notify_on', 'notify_on is invalid.');
    const missedRunPolicy = input.missed_run_policy ?? 'run_once';
    if (!MISSED_RUN_POLICIES.has(missedRunPolicy)) throw new ProactiveError('invalid_missed_run_policy', 'missed_run_policy is invalid.');
    const cooldownMinutes = input.cooldown_minutes === undefined || input.cooldown_minutes === null
      ? null
      : integer(input.cooldown_minutes, 1, 1440, 'invalid_cooldown');

    const state = await this.#state();
    const subscriptionKey = `${input.check}:${input.target}`;
    const existing = [...state.subscriptions.values()].find(
      (subscription) => subscription.subscription_key === subscriptionKey && subscription.status === 'active',
    );
    if (existing) return { ...clone(existing), replayed: true };

    const now = this.now();
    const subscription = {
      schema_version: 'zarvis.proactive.subscription.v1',
      subscription_id: this.idFactory(),
      subscription_key: subscriptionKey,
      owner_user_id: ZARVIS_OWNER_USER_ID,
      tenant_id: ZARVIS_OWNER_TENANT_ID,
      check: 'local.service.health',
      target: input.target,
      interval_minutes: intervalMinutes,
      notify_on: notifyOn,
      cooldown_minutes: cooldownMinutes,
      missed_run_policy: missedRunPolicy,
      status: 'active',
      next_run_at: now,
      last_evaluated_at: null,
      last_signal_status: null,
      created_at: now,
      updated_at: now,
    };
    await this.#append('zarvis.proactive.subscription-created.v1', { subscription }, now);
    return { ...clone(subscription), replayed: false };
  }

  async listSubscriptions() {
    return [...(await this.#state()).subscriptions.values()]
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
      .map(clone);
  }

  async revokeSubscription(subscriptionId) {
    const state = await this.#state();
    const current = state.subscriptions.get(subscriptionId);
    if (!current) throw new ProactiveError('subscription_not_found', 'Subscription was not found.', 404);
    if (current.status === 'revoked') return { ...clone(current), replayed: true };
    const now = this.now();
    const subscription = { ...current, status: 'revoked', updated_at: now };
    await this.#append('zarvis.proactive.subscription-revoked.v1', { subscription }, now);
    return { ...clone(subscription), replayed: false };
  }

  async listNotifications() {
    const state = await this.#state();
    return [...state.notifications.values()]
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
      .map((notification) => ({
        ...clone(notification),
        feedback: clone(state.feedback.get(notification.notification_id) ?? null),
        handoff: clone(state.handoffs.get(notification.notification_id) ?? null),
      }));
  }

  async recordFeedback(notificationId, input) {
    assertTrustedInput(input);
    const state = await this.#state();
    if (!state.notifications.has(notificationId)) throw new ProactiveError('notification_not_found', 'Notification was not found.', 404);
    if (!FEEDBACK.has(input.rating)) throw new ProactiveError('invalid_feedback', 'Feedback rating is invalid.');
    const now = this.now();
    const feedback = {
      schema_version: 'zarvis.proactive.feedback.v1',
      notification_id: notificationId,
      owner_user_id: ZARVIS_OWNER_USER_ID,
      tenant_id: ZARVIS_OWNER_TENANT_ID,
      rating: input.rating,
      note: typeof input.note === 'string' ? input.note.slice(0, 500) : null,
      created_at: now,
    };
    await this.#append('zarvis.proactive.feedback-recorded.v1', { feedback }, now);
    return clone(feedback);
  }

  async createActionHandoff(notificationId) {
    const state = await this.#state();
    const notification = state.notifications.get(notificationId);
    if (!notification) throw new ProactiveError('notification_not_found', 'Notification was not found.', 404);
    if (!notification.proposed_action) throw new ProactiveError('no_action_proposed', 'Notification has no action proposal.', 409);
    const existing = state.handoffs.get(notificationId);
    if (existing) return { ...clone(existing), replayed: true };
    const now = this.now();
    const handoff = {
      schema_version: 'zarvis.proactive.action-handoff.v1',
      handoff_id: this.idFactory(),
      notification_id: notificationId,
      owner_user_id: ZARVIS_OWNER_USER_ID,
      tenant_id: ZARVIS_OWNER_TENANT_ID,
      destination: 'zarvis-action-gateway',
      requires_owner_approval: true,
      executed: false,
      request: clone(notification.proposed_action),
      created_at: now,
    };
    await this.#append('zarvis.proactive.action-handoff-created.v1', { handoff }, now);
    return { ...clone(handoff), replayed: false };
  }

  async tick() {
    const now = this.now();
    const state = await this.#state();
    const policy = state.policy;
    const subscriptions = state.subscriptions;
    const notifications = [...state.notifications.values()];
    const results = [];

    for (const current of subscriptions.values()) {
      if (current.status !== 'active' || current.next_run_at > now) continue;
      const intervalMs = current.interval_minutes * 60_000;
      const overdueMs = new Date(now).getTime() - new Date(current.next_run_at).getTime();
      if (overdueMs > intervalMs && current.missed_run_policy === 'skip') {
        const subscription = {
          ...current,
          next_run_at: new Date(new Date(now).getTime() + intervalMs).toISOString(),
          last_evaluated_at: now,
          updated_at: now,
        };
        const evaluation = {
          schema_version: 'zarvis.proactive.evaluation.v1',
          subscription_id: current.subscription_id,
          decision: 'missed_run_skipped',
          notification_id: null,
          evaluated_at: now,
        };
        await this.#append('zarvis.proactive.evaluated.v1', { evaluation }, now);
        await this.#append('zarvis.proactive.subscription-updated.v1', { subscription }, now);
        subscriptions.set(subscription.subscription_id, subscription);
        results.push(evaluation);
        continue;
      }

      const rawSignal = await this.adapter.evaluate(current, now);
      const signal = validateSignal(rawSignal, current);
      signal.signal_id = this.idFactory();
      const triggered = shouldTrigger(current, signal);
      const fingerprint = hash({
        subscription_id: current.subscription_id,
        signal_key: signal.signal_key,
        status: signal.status,
        summary: signal.summary,
      });
      let decision = triggered ? 'delivered' : 'not_triggered';

      if (triggered && signal.confidence < policy.confidence_threshold) decision = 'suppressed_confidence';
      if (triggered && decision === 'delivered' && inQuietHours(now, policy)) decision = 'suppressed_quiet_hours';

      const localDate = zonedParts(now, policy.timezone).date;
      const deliveredToday = notifications.filter(
        (notification) => notification.delivery_state === 'delivered'
          && zonedParts(notification.created_at, policy.timezone).date === localDate,
      ).length;
      if (triggered && decision === 'delivered' && deliveredToday >= policy.daily_notification_budget) {
        decision = 'suppressed_budget';
      }

      const cooldownMinutes = current.cooldown_minutes ?? policy.default_cooldown_minutes;
      const cooldownStart = new Date(new Date(now).getTime() - cooldownMinutes * 60_000).toISOString();
      const duplicate = notifications.some(
        (notification) => notification.delivery_state === 'delivered'
          && notification.fingerprint === fingerprint
          && notification.created_at >= cooldownStart,
      );
      if (triggered && decision === 'delivered' && duplicate) decision = 'suppressed_cooldown';

      let notification = null;
      if (triggered) {
        notification = {
          schema_version: 'zarvis.proactive.notification.v1',
          notification_id: this.idFactory(),
          subscription_id: current.subscription_id,
          owner_user_id: ZARVIS_OWNER_USER_ID,
          tenant_id: ZARVIS_OWNER_TENANT_ID,
          delivery_state: decision,
          fingerprint,
          severity: signal.severity,
          confidence: signal.confidence,
          title: signal.status === 'unhealthy' ? `${current.target} needs attention` : `${current.target} status changed`,
          summary: signal.summary,
          explanation: `Read-only ${current.check} evaluated ${current.target} at ${now}; status=${signal.status}; confidence=${signal.confidence}.`,
          source_url: signal.source_url,
          evidence: signal.evidence,
          proposed_action: signal.proposed_action,
          requires_owner_approval: signal.proposed_action !== null,
          created_at: now,
        };
        await this.#append('zarvis.proactive.notification-decided.v1', { notification }, now);
        notifications.push(notification);
      }

      const evaluation = {
        schema_version: 'zarvis.proactive.evaluation.v1',
        subscription_id: current.subscription_id,
        signal,
        decision,
        notification_id: notification?.notification_id ?? null,
        evaluated_at: now,
      };
      await this.#append('zarvis.proactive.evaluated.v1', { evaluation }, now);

      const subscription = {
        ...current,
        next_run_at: new Date(new Date(now).getTime() + intervalMs).toISOString(),
        last_evaluated_at: now,
        last_signal_status: signal.status,
        updated_at: now,
      };
      await this.#append('zarvis.proactive.subscription-updated.v1', { subscription }, now);
      subscriptions.set(subscription.subscription_id, subscription);
      results.push(evaluation);
    }

    return {
      schema_version: 'zarvis.proactive.tick-result.v1',
      local_only: true,
      evaluated: results.length,
      results: clone(results),
      occurred_at: now,
    };
  }

  async status() {
    const state = await this.#state();
    return {
      owner_user_id: ZARVIS_OWNER_USER_ID,
      tenant_id: ZARVIS_OWNER_TENANT_ID,
      local_only: true,
      autonomous_mutation: false,
      allowed_checks: ['local.service.health'],
      active_subscriptions: [...state.subscriptions.values()].filter((item) => item.status === 'active').length,
      notifications: state.notifications.size,
      policy: clone(state.policy),
    };
  }
}

export { DEFAULT_POLICY, hash as createProactiveFingerprint, inQuietHours, zonedParts };
