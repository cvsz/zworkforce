const MAX_CURSOR = Number.MAX_SAFE_INTEGER;
const EVENT_NAME_RE = /^[A-Za-z0-9_.:-]{1,128}$/;

function safeCursor(value) {
  if (typeof value === "number") {
    return Number.isSafeInteger(value) && value >= 0 ? value : null;
  }
  if (typeof value !== "string" || !/^\d+$/.test(value.trim())) return null;
  const cursor = Number(value.trim());
  return Number.isSafeInteger(cursor) && cursor >= 0 && cursor <= MAX_CURSOR ? cursor : null;
}

export function parseSseBlock(block) {
  if (typeof block !== "string" || !block.trim()) return null;
  let id = null;
  let event = "message";
  const dataLines = [];
  for (const line of block.replaceAll("\r\n", "\n").split("\n")) {
    if (!line || line.startsWith(":")) continue;
    const separator = line.indexOf(":");
    const field = separator < 0 ? line : line.slice(0, separator);
    let value = separator < 0 ? "" : line.slice(separator + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "id") {
      id = safeCursor(value);
    } else if (field === "event") {
      event = value;
    } else if (field === "data") {
      dataLines.push(value);
    }
  }
  if (id === null || !EVENT_NAME_RE.test(event) || dataLines.length === 0) return null;
  let data;
  try {
    data = JSON.parse(dataLines.join("\n"));
  } catch {
    return null;
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) return null;
  return { id, event, data };
}

function defaultSleep(milliseconds, signal) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(done, milliseconds);
    function done() {
      signal?.removeEventListener("abort", aborted);
      resolve();
    }
    function aborted() {
      clearTimeout(timer);
      signal?.removeEventListener("abort", aborted);
      const error = new Error("request aborted");
      error.name = "AbortError";
      reject(error);
    }
    if (signal?.aborted) aborted();
    else signal?.addEventListener("abort", aborted, { once: true });
  });
}

function yieldToHost() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

function sessionParts(getSession) {
  const session = getSession?.() || {};
  return {
    key: String(session.key ?? session.apiKey ?? session.api_key ?? "").trim(),
    tenant: String(session.tenant ?? session.tenantId ?? "").trim(),
  };
}

export function createRealtimeClient(options = {}) {
  const endpoint = String(options.endpoint || "/api/v1/dashboard/events").split(/[?#]/, 1)[0];
  const getSession = options.getSession || (() => ({}));
  const fetchImpl = options.fetchImpl || globalThis.fetch;
  const sleep = options.sleep || defaultSleep;
  const random = options.random || Math.random;
  const statusListeners = new Set();
  const eventListeners = new Set();
  let state = "OFFLINE";
  let cursor = 0;
  let running = false;
  let generation = 0;
  let controller = null;
  let loopPromise = null;
  let identity = "";
  let failures = 0;

  function notifyStatus(nextState) {
    if (state === nextState) return;
    state = nextState;
    for (const listener of statusListeners) {
      try {
        listener(state);
      } catch {
        // A status renderer must not stop transport recovery.
      }
    }
  }

  function notifyEvent(event) {
    for (const listener of eventListeners) {
      try {
        listener(event);
      } catch {
        // A package invalidation must not stop the shared stream.
      }
    }
  }

  function currentSession() {
    const session = sessionParts(getSession);
    const nextIdentity = `${session.tenant}\u0000${session.key}`;
    if (identity && identity !== nextIdentity) {
      cursor = 0;
      failures = 0;
    }
    identity = nextIdentity;
    return session;
  }

  function headersFor(session) {
    const headers = {
      Accept: "text/event-stream",
      Authorization: `Bearer ${session.key}`,
      "X-ZWorkforce-Event-Cursor": String(cursor),
    };
    if (session.tenant) headers["X-Tenant-ID"] = session.tenant;
    return headers;
  }

  function handleEvent(parsed) {
    if (!parsed || !Number.isSafeInteger(parsed.id)) return;
    if (parsed.event === "resync.required") {
      const nextCursor = safeCursor(parsed.data?.cursor);
      if (nextCursor === null) return;
      cursor = nextCursor;
      notifyStatus("STALE");
      notifyEvent(parsed);
      return;
    }
    const duplicate = parsed.id <= cursor;
    if (parsed.id > cursor) cursor = parsed.id;
    if (parsed.event === "heartbeat" || !duplicate) {
      failures = 0;
      notifyStatus("LIVE");
      notifyEvent(parsed);
    }
  }

  async function consume(response, currentGeneration, signal) {
    if (!response?.body?.getReader) throw new Error("event stream body is unavailable");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    async function readChunk() {
      if (signal.aborted) return { done: true, value: undefined };
      return new Promise((resolve, reject) => {
        let settled = false;
        const finish = (callback, value) => {
          if (settled) return;
          settled = true;
          signal.removeEventListener("abort", onAbort);
          callback(value);
        };
        const onAbort = () => finish(resolve, { done: true, value: undefined });
        signal.addEventListener("abort", onAbort, { once: true });
        if (signal.aborted) {
          onAbort();
          return;
        }
        try {
          reader.read().then(
            (value) => finish(resolve, value),
            (error) => finish(reject, error),
          );
        } catch (error) {
          finish(reject, error);
        }
      });
    }
    try {
      while (running && generation === currentGeneration) {
        const result = await readChunk();
        if (result.done) break;
        buffer += decoder.decode(result.value, { stream: true });
        while (true) {
          const boundary = buffer.match(/\r?\n\r?\n/);
          if (!boundary) break;
          const block = buffer.slice(0, boundary.index);
          buffer = buffer.slice(boundary.index + boundary[0].length);
          handleEvent(parseSseBlock(block));
        }
      }
      buffer += decoder.decode();
      if (buffer.trim()) handleEvent(parseSseBlock(buffer));
    } finally {
      try {
        reader.releaseLock?.();
      } catch {
        // The stream may already have been released by the browser.
      }
    }
    if (signal.aborted || !running || generation !== currentGeneration) return;
    throw new Error("event stream ended");
  }

  function backoffDelay() {
    const exponential = Math.min(30000, 500 * 2 ** Math.min(6, Math.max(0, failures - 1)));
    return exponential + Math.round(exponential * 0.2 * Math.max(0, Math.min(1, Number(random()) || 0)));
  }

  async function run(currentGeneration) {
    while (running && generation === currentGeneration) {
      const session = currentSession();
      if (!session.key) {
        notifyStatus("OFFLINE");
        return;
      }
      notifyStatus(failures > 0 && failures >= 3 ? "POLLING" : "RECONNECTING");
      const requestController = new AbortController();
      controller = requestController;
      try {
        if (typeof fetchImpl !== "function") throw new Error("fetch is unavailable");
        const response = await fetchImpl(endpoint, {
          method: "GET",
          headers: headersFor(session),
          signal: requestController.signal,
        });
        if (!response || !response.ok || response.status < 200 || response.status >= 300) {
          throw new Error(`event stream HTTP ${response?.status || 0}`);
        }
        await consume(response, currentGeneration, requestController.signal);
      } catch (error) {
        if (!running || generation !== currentGeneration || requestController.signal.aborted || error?.name === "AbortError") return;
        failures += 1;
        notifyStatus(failures >= 3 ? "POLLING" : "RECONNECTING");
        try {
          await sleep(backoffDelay(), requestController.signal);
          await yieldToHost();
        } catch (sleepError) {
          if (sleepError?.name !== "AbortError") throw sleepError;
        }
      } finally {
        if (controller === requestController) controller = null;
      }
    }
  }

  function start() {
    if (running) return loopPromise;
    const session = currentSession();
    if (!session.key) {
      notifyStatus("OFFLINE");
      return null;
    }
    running = true;
    const currentGeneration = ++generation;
    loopPromise = run(currentGeneration).catch(() => {
      if (running && generation === currentGeneration) notifyStatus("STALE");
    });
    return loopPromise;
  }

  function stop() {
    running = false;
    generation += 1;
    controller?.abort();
    controller = null;
    notifyStatus("OFFLINE");
  }

  function markStale() {
    if (running) notifyStatus("STALE");
  }

  return {
    start,
    stop,
    restart() {
      stop();
      return start();
    },
    subscribeStatus(listener) {
      if (typeof listener !== "function") return () => {};
      statusListeners.add(listener);
      listener(state);
      return () => statusListeners.delete(listener);
    },
    subscribeEvents(listener) {
      if (typeof listener !== "function") return () => {};
      eventListeners.add(listener);
      return () => eventListeners.delete(listener);
    },
    getState: () => state,
    getCursor: () => cursor,
    markStale,
  };
}
