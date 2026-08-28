const DEFAULT_RATE_LIMIT_WINDOW_MS = 60_000;
const DEFAULT_RATE_LIMIT_MAX = 60;

function positiveInteger(value, fallback, name) {
  const parsed = Number(value ?? fallback);
  if (!Number.isInteger(parsed) || parsed < 1) throw new Error(`${name} must be a positive integer`);
  return parsed;
}

export function rateLimitConfig(env = process.env) {
  return {
    windowMs: positiveInteger(env.AI_GATEWAY_RATE_LIMIT_WINDOW_MS, DEFAULT_RATE_LIMIT_WINDOW_MS, "AI_GATEWAY_RATE_LIMIT_WINDOW_MS"),
    limit: positiveInteger(env.AI_GATEWAY_RATE_LIMIT_MAX, DEFAULT_RATE_LIMIT_MAX, "AI_GATEWAY_RATE_LIMIT_MAX"),
    standardHeaders: "draft-8",
    legacyHeaders: false,
    message: { error: { code: "RATE_LIMITED", message: "Too many requests" } },
  };
}

export function corsConfig(value = process.env.CORS_ORIGIN) {
  const configured = typeof value === "string" ? value.split(",").map((origin) => origin.trim()).filter(Boolean) : [];
  if (configured.includes("*")) throw new Error("CORS_ORIGIN must not contain a wildcard");

  const allowed = new Set(configured.map((origin) => {
    const url = new URL(origin);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.origin !== origin) {
      throw new Error("CORS_ORIGIN entries must be exact HTTP(S) origins without credentials or paths");
    }
    return url.origin;
  }));

  return {
    credentials: false,
    origin(origin, callback) {
      callback(null, !origin || allowed.has(origin));
    },
  };
}
