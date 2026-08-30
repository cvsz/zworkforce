const DEFAULT_DEFINITIONS = [
  { id: "overview", events: ["task.changed", "usage.changed", "provider.changed", "budget.changed"] },
  { id: "workforce", events: ["task.changed", "agent.changed", "agent_template.changed"] },
  { id: "governance", events: ["audit.changed", "policy.changed", "skill.changed"] },
  { id: "automation", events: ["workflow.changed", "schedule.changed", "event.changed"] },
  { id: "finops", events: ["usage.changed", "budget.changed", "provider.changed", "slo.changed"] },
  { id: "knowledge", events: ["memory.changed"] },
  { id: "zarvis", events: ["voice.changed"] },
  { id: "realtime", events: ["heartbeat", "resync.required"] },
];

export function createPackageRegistry(definitions = DEFAULT_DEFINITIONS, onInvalidate = () => {}) {
  const normalized = Array.isArray(definitions)
    ? definitions.filter((definition) => definition && typeof definition.id === "string")
    : [];
  const byEvent = new Map();
  for (const definition of normalized) {
    for (const eventType of definition.events || []) {
      if (!byEvent.has(eventType)) byEvent.set(eventType, new Set());
      byEvent.get(eventType).add(definition.id);
    }
  }
  const pending = new Map();
  let timer = null;

  function flush() {
    timer = null;
    for (const [packageId, event] of pending) onInvalidate(packageId, event);
    pending.clear();
  }

  return {
    dispatch(event) {
      const eventType = event?.event || event?.event_type;
      const packageIds = [...(byEvent.get(eventType) || [])];
      for (const packageId of packageIds) pending.set(packageId, event);
      if (packageIds.length && timer === null) timer = setTimeout(flush, 0);
      return packageIds;
    },
    list() {
      return normalized.map((definition) => ({ id: definition.id, events: [...(definition.events || [])] }));
    },
    destroy() {
      if (timer !== null) clearTimeout(timer);
      timer = null;
      pending.clear();
    },
  };
}

export { DEFAULT_DEFINITIONS };
