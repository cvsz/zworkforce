#!/usr/bin/env node

import { readFile } from "node:fs/promises";
import process from "node:process";

const DEFAULT_FILE = "API-KEY.txt";
const DEFAULT_TIMEOUT_MS = 10_000;
const PLACEHOLDER_PATTERN = /^(?:|replace(?:-?me)?|changeme|your[-_ ]?(?:api[-_ ]?)?key|example|test|dummy|null|undefined|<.*>|\$\{.*\})$/i;

const PROVIDERS = {
  NVIDIA_NIM_API_KEY: {
    name: "NVIDIA NIM",
    baseEnv: "NVIDIA_NIM_BASE_URL",
    defaultBase: "https://integrate.api.nvidia.com/v1",
    path: "/models",
    auth: "bearer",
  },
  GROQ_API_KEY: {
    name: "Groq",
    baseEnv: "GROQ_BASE_URL",
    defaultBase: "https://api.groq.com/openai/v1",
    path: "/models",
    auth: "bearer",
  },
  CEREBRAS_API_KEY: {
    name: "Cerebras",
    baseEnv: "CEREBRAS_BASE_URL",
    defaultBase: "https://api.cerebras.ai/v1",
    path: "/models",
    auth: "bearer",
  },
  SAMBANOVA_API_KEY: {
    name: "SambaNova",
    baseEnv: "SAMBANOVA_BASE_URL",
    defaultBase: "https://api.sambanova.ai/v1",
    path: "/models",
    auth: "bearer",
  },
  OPENROUTER_API_KEY: {
    name: "OpenRouter",
    baseEnv: "OPENROUTER_BASE_URL",
    defaultBase: "https://openrouter.ai/api/v1",
    path: "/auth/key",
    auth: "bearer",
  },
  MISTRAL_API_KEY: {
    name: "Mistral La Plateforme",
    baseEnv: "MISTRAL_BASE_URL",
    defaultBase: "https://api.mistral.ai/v1",
    path: "/models",
    auth: "bearer",
  },
  CODESTRAL_API_KEY: {
    name: "Codestral",
    baseEnv: "CODESTRAL_BASE_URL",
    defaultBase: "https://codestral.mistral.ai/v1",
    path: "/models",
    auth: "bearer",
  },
  GEMINI_API_KEY: {
    name: "Google AI Studio / Gemini",
    baseEnv: "GEMINI_BASE_URL",
    defaultBase: "https://generativelanguage.googleapis.com/v1beta",
    path: "/models",
    auth: "google-header",
  },
  DASHSCOPE_API_KEY: {
    name: "Alibaba DashScope / Qwen",
    baseEnv: "DASHSCOPE_BASE_URL",
    defaultBase: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    path: "/models",
    auth: "bearer",
  },
  DEEPSEEK_API_KEY: {
    name: "DeepSeek",
    baseEnv: "DEEPSEEK_BASE_URL",
    defaultBase: "https://api.deepseek.com/v1",
    path: "/models",
    auth: "bearer",
  },
  FIREWORKS_API_KEY: {
    name: "Fireworks AI",
    baseEnv: "FIREWORKS_BASE_URL",
    defaultBase: "https://api.fireworks.ai/inference/v1",
    path: "/models",
    auth: "bearer",
  },
  OPENCODE_API_KEY: {
    name: "OpenCode Zen",
    baseEnv: "OPENCODE_ZEN_BASE_URL",
    defaultBase: "https://opencode.ai/zen/v1",
    path: "/models",
    auth: "bearer",
  },
  KIMI_API_KEY: {
    name: "Moonshot AI / Kimi",
    baseEnv: "KIMI_BASE_URL",
    defaultBase: null,
    path: "/models",
    auth: "bearer",
    requiresBase: true,
  },
  ZAI_API_KEY: {
    name: "Z.ai",
    baseEnv: "ZAI_BASE_URL",
    defaultBase: null,
    path: "/models",
    auth: "bearer",
    requiresBase: true,
  },
  SCALEWAY_API_KEY: {
    name: "Scaleway Generative APIs",
    baseEnv: "SCALEWAY_BASE_URL",
    defaultBase: null,
    path: "/models",
    auth: "bearer",
    requiresBase: true,
  },
  OVHCLOUD_API_KEY: {
    name: "OVHcloud AI Endpoints",
    baseEnv: "OVHCLOUD_BASE_URL",
    defaultBase: null,
    path: "/models",
    auth: "bearer",
    requiresBase: true,
  },
  WAFER_API_KEY: {
    name: "Wafer",
    baseEnv: "WAFER_BASE_URL",
    defaultBase: null,
    auth: "bearer",
    unsupportedReason: "No confirmed read-only key validation endpoint is configured.",
  },
};

function parseArgs(argv) {
  const options = {
    file: DEFAULT_FILE,
    timeoutMs: DEFAULT_TIMEOUT_MS,
    json: false,
    strict: false,
    syntaxOnly: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--file") {
      options.file = argv[++index];
    } else if (arg === "--timeout-ms") {
      options.timeoutMs = Number(argv[++index]);
    } else if (arg === "--json") {
      options.json = true;
    } else if (arg === "--strict") {
      options.strict = true;
    } else if (arg === "--syntax-only") {
      options.syntaxOnly = true;
    } else if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  if (!options.file) throw new Error("--file requires a path");
  if (!Number.isFinite(options.timeoutMs) || options.timeoutMs < 1000) {
    throw new Error("--timeout-ms must be a number >= 1000");
  }
  return options;
}

function printHelp() {
  console.log(`Usage: node scripts/validate-api-keys.mjs [options]\n\nOptions:\n  --file PATH       Input file (default: API-KEY.txt)\n  --timeout-ms N    Per-request timeout (default: 10000)\n  --syntax-only     Validate populated *_API_KEY entries without network calls\n  --strict          Exit non-zero for unsupported/unverified keys as well\n  --json            Emit JSON only\n  -h, --help        Show this help\n\nThe script never prints API-key values and performs read-only validation requests.`);
}

function parseEnvFile(source) {
  const values = {};
  const errors = [];
  const lines = source.replace(/^\uFEFF/, "").split(/\r?\n/);

  lines.forEach((rawLine, index) => {
    const lineNumber = index + 1;
    const trimmed = rawLine.trim();
    if (!trimmed || trimmed.startsWith("#")) return;

    const match = rawLine.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/);
    if (!match) {
      errors.push({ line: lineNumber, message: "Expected KEY=VALUE syntax" });
      return;
    }

    const [, key, rawValue] = match;
    let value = rawValue.trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    } else {
      value = value.replace(/\s+#.*$/, "").trim();
    }

    if (Object.hasOwn(values, key)) {
      errors.push({ line: lineNumber, message: `Duplicate variable: ${key}` });
    }
    values[key] = value;
  });

  return { values, errors };
}

function isPlaceholder(value) {
  return PLACEHOLDER_PATTERN.test(value.trim());
}

function joinUrl(base, path) {
  return `${base.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
}

function requestHeaders(auth, key) {
  const headers = {
    Accept: "application/json",
    "User-Agent": "z-platform-api-key-validator/1.0",
  };
  if (auth === "bearer") headers.Authorization = `Bearer ${key}`;
  if (auth === "google-header") headers["x-goog-api-key"] = key;
  return headers;
}

function classifyStatus(status) {
  if (status >= 200 && status < 300) return "valid";
  if (status === 401 || status === 403) return "invalid";
  if (status === 429) return "rate-limited";
  if (status >= 500) return "unverified";
  return "unverified";
}

async function validateNetwork(keyName, keyValue, config, env, timeoutMs) {
  if (config.unsupportedReason) {
    return { status: "skipped", detail: config.unsupportedReason };
  }

  const baseUrl = env[config.baseEnv] || config.defaultBase;
  if (!baseUrl) {
    return {
      status: "skipped",
      detail: `Set ${config.baseEnv} to a verified provider base URL before testing.`,
    };
  }

  let parsedBase;
  try {
    parsedBase = new URL(baseUrl);
  } catch {
    return { status: "invalid-config", detail: `${config.baseEnv} is not a valid URL.` };
  }
  if (parsedBase.protocol !== "https:" && parsedBase.hostname !== "localhost" && parsedBase.hostname !== "127.0.0.1") {
    return { status: "invalid-config", detail: "Refusing a non-HTTPS remote endpoint." };
  }
  const configuredOrigins = (env.VALIDATED_PROVIDER_ORIGINS ?? "")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean);
  const allowedOrigins = new Set(configuredOrigins.length ? configuredOrigins : [new URL(config.defaultBase).origin]);
  if (!allowedOrigins.has(parsedBase.origin)) {
    return { status: "invalid-config", detail: "Provider endpoint origin is not allowlisted." };
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const startedAt = Date.now();

  try {
    const response = await fetch(joinUrl(baseUrl, config.path), {
      method: "GET",
      headers: requestHeaders(config.auth, keyValue),
      redirect: "error",
      signal: controller.signal,
    });
    const durationMs = Date.now() - startedAt;
    const status = classifyStatus(response.status);
    await response.body?.cancel().catch(() => {});
    return {
      status,
      httpStatus: response.status,
      durationMs,
      endpoint: `${parsedBase.origin}/…`,
      detail: status === "valid" ? "Provider accepted the credential." : "Provider did not confirm the credential.",
    };
  } catch (error) {
    return {
      status: "unverified",
      durationMs: Date.now() - startedAt,
      endpoint: `${parsedBase.origin}/…`,
      detail: error.name === "AbortError" ? `Timed out after ${timeoutMs} ms.` : `Network validation failed: ${error.message}`,
    };
  } finally {
    clearTimeout(timeout);
  }
}

function renderTable(results, parseErrors) {
  if (parseErrors.length) {
    console.error("Parse errors:");
    for (const error of parseErrors) console.error(`  line ${error.line}: ${error.message}`);
    console.error("");
  }

  const rows = results.map((result) => ({
    Variable: result.variable,
    Provider: result.provider,
    Status: result.status,
    HTTP: result.httpStatus ?? "-",
    "Time(ms)": result.durationMs ?? "-",
    Detail: result.detail,
  }));
  console.table(rows);
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const source = await readFile(options.file, "utf8");
  const { values, errors } = parseEnvFile(source);
  const entries = Object.entries(values).filter(([key]) => key.endsWith("_API_KEY"));

  const results = [];
  for (const [keyName, keyValue] of entries) {
    const config = PROVIDERS[keyName];
    if (!keyValue || isPlaceholder(keyValue)) {
      results.push({
        variable: keyName,
        provider: config?.name ?? "Unknown",
        status: "empty",
        detail: "No usable credential is configured.",
      });
      continue;
    }

    if (!config) {
      results.push({
        variable: keyName,
        provider: "Unknown",
        status: "skipped",
        detail: "No safe read-only validator is registered for this variable.",
      });
      continue;
    }

    if (options.syntaxOnly) {
      results.push({
        variable: keyName,
        provider: config.name,
        status: "syntax-valid",
        detail: "Populated and not recognized as a placeholder; no network call made.",
      });
      continue;
    }

    const result = await validateNetwork(keyName, keyValue, config, values, options.timeoutMs);
    results.push({ variable: keyName, provider: config.name, ...result });
  }

  if (entries.length === 0) {
    results.push({
      variable: "-",
      provider: "-",
      status: "empty",
      detail: "No *_API_KEY variables were found.",
    });
  }

  const summary = results.reduce((counts, result) => {
    counts[result.status] = (counts[result.status] ?? 0) + 1;
    return counts;
  }, {});
  const output = { file: options.file, checked: entries.length, parseErrors: errors, summary, results };

  if (options.json) console.log(JSON.stringify(output, null, 2));
  else {
    renderTable(results, errors);
    console.log("Summary:", summary);
  }

  const hardFailureStatuses = new Set(["invalid", "invalid-config"]);
  if (options.strict) {
    hardFailureStatuses.add("skipped");
    hardFailureStatuses.add("unverified");
    hardFailureStatuses.add("rate-limited");
  }
  const failed = errors.length > 0 || results.some((result) => hardFailureStatuses.has(result.status));
  process.exitCode = failed ? 1 : 0;
}

main().catch((error) => {
  console.error(`API key validation failed: ${error.message}`);
  process.exitCode = 2;
});
