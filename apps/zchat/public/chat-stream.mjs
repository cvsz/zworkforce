const decoder = new TextDecoder();

function isAbortError(error) {
  return Boolean(error && typeof error === "object" && "name" in error && error.name === "AbortError");
}

function decodeEventData(data) {
  const trimmed = data.trim();
  if (!trimmed || trimmed === "[DONE]") return "";
  try {
    const payload = JSON.parse(trimmed);
    const choice = payload?.choices?.[0];
    const delta = choice?.delta?.content ?? choice?.message?.content ?? payload?.delta?.content ?? payload?.content;
    return typeof delta === "string" ? delta : "";
  } catch {
    return trimmed;
  }
}

export function extractDeltaText(chunk) {
  return chunk
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter((line) => line.startsWith("data:"))
    .map((line) => decodeEventData(line.slice(5)))
    .join("");
}

export async function readEventStream(response, onDelta, signal) {
  if (!response.body) {
    throw new Error("Streaming response unavailable");
  }

  const reader = response.body.getReader();
  let buffer = "";
  let emitted = "";
  let aborted = false;

  const cancelReader = () => {
    void reader.cancel(signal?.reason).catch(() => {});
  };

  if (signal) {
    if (signal.aborted) {
      await reader.cancel(signal.reason).catch(() => {});
      return emitted;
    }
    signal.addEventListener("abort", cancelReader, { once: true });
  }

  try {
    while (true) {
      let chunk;
      try {
        chunk = await reader.read();
      } catch (error) {
        if (signal?.aborted || isAbortError(error)) {
          aborted = true;
          break;
        }
        throw error;
      }

      const { value, done } = chunk;
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

      let boundaryIndex = buffer.indexOf("\n\n");
      while (boundaryIndex !== -1) {
        const event = buffer.slice(0, boundaryIndex);
        buffer = buffer.slice(boundaryIndex + 2);
        const delta = extractDeltaText(event);
        if (delta) {
          emitted += delta;
          onDelta(delta, emitted);
        }
        boundaryIndex = buffer.indexOf("\n\n");
      }

      if (done || signal?.aborted) {
        aborted = aborted || Boolean(signal?.aborted);
        break;
      }
    }

    if (!aborted && buffer.trim()) {
      const delta = extractDeltaText(buffer);
      if (delta) {
        emitted += delta;
        onDelta(delta, emitted);
      }
    }
    return emitted;
  } finally {
    if (signal) {
      signal.removeEventListener("abort", cancelReader);
    }
    try {
      reader.releaseLock();
    } catch {
      // Reader may already be released by cancellation.
    }
  }
}
