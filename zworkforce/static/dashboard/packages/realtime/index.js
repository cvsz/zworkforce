const STATUS_COPY = Object.freeze({
  LIVE: Object.freeze({ label: "LIVE", live: true }),
  RECONNECTING: Object.freeze({ label: "RECONNECTING", live: false }),
  POLLING: Object.freeze({ label: "POLLING", live: false }),
  STALE: Object.freeze({ label: "STALE", live: false }),
  OFFLINE: Object.freeze({ label: "OFFLINE", live: false }),
});

function getCopy(state) {
  return STATUS_COPY[state] || STATUS_COPY.STALE;
}

export function mountRealtimePackage({ root = globalThis.document, client }) {
  const scope = root || null;
  const dot = scope?.querySelector?.("#realtimeDot") || null;
  const text = scope?.querySelector?.("#realtimeText") || null;
  const region = scope?.querySelector?.("#realtimeStatus") || null;
  const unsub = client?.subscribeStatus?.((state) => {
    const copy = getCopy(state);
    if (dot) {
      dot.dataset.state = state;
      dot.setAttribute("aria-label", copy.label);
    }
    if (text) {
      text.textContent = copy.live ? "Realtime" : copy.label;
    }
    if (region) {
      region.textContent = copy.label;
      region.dataset.state = state;
    }
  });
  return {
    destroy() {
      unsub?.();
    },
  };
}

export { STATUS_COPY };
