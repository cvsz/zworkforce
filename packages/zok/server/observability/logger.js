const SENSITIVE_FIELD_PATTERNS = [
  /password/i,
  /token/i,
  /secret/i,
  /authorization/i,
  /cookie/i,
  /csrf/i,
  /api[_-]?key/i,
  /private[_-]?key/i,
  /access[_-]?token/i,
  /refresh[_-]?token/i,
  /credentials/i,
];

function isSensitiveField(fieldName) {
  return SENSITIVE_FIELD_PATTERNS.some(pattern => pattern.test(fieldName));
}

function redactValue(value) {
  if (value === undefined || value === null) return value;
  if (typeof value === 'string') return '[REDACTED]';
  if (typeof value === 'number' || typeof value === 'boolean') return value;
  if (Array.isArray(value)) return value.map(redactValue);
  if (typeof value === 'object') {
    const output = {};
    for (const [key, val] of Object.entries(value)) {
      if (isSensitiveField(key)) {
        output[key] = '[REDACTED]';
      } else {
        output[key] = redactValue(val);
      }
    }
    return output;
  }
  return '[REDACTED]';
}

function sanitize(obj) {
  if (!obj || typeof obj !== 'object') return obj;
  if (Array.isArray(obj)) return obj.map(sanitize);
  const out = {};
  for (const [key, value] of Object.entries(obj)) {
    if (isSensitiveField(key)) {
      out[key] = '[REDACTED]';
    } else {
      out[key] = sanitize(value);
    }
  }
  return out;
}

class Logger {
  constructor(context = {}) {
    this.context = context;
  }

  child(context = {}) {
    return new Logger({ ...this.context, ...context });
  }

  log(level, message, meta = {}) {
    const entry = {
      level,
      timestamp: new Date().toISOString(),
      message,
      ...this.context,
      ...sanitize(meta),
    };

    for (const key of Object.keys(entry)) {
      if (entry[key] === undefined) {
        delete entry[key];
      }
    }

    const line = JSON.stringify(entry);
    if (level === 'error') {
      process.stderr.write(line + '\n');
    } else {
      process.stdout.write(line + '\n');
    }
  }

  debug(message, meta) {
    this.log('debug', message, meta);
  }

  info(message, meta) {
    this.log('info', message, meta);
  }

  warn(message, meta) {
    this.log('warn', message, meta);
  }

  error(message, meta) {
    this.log('error', message, meta);
  }
}

const rootLogger = new Logger();

export function createLogger(context = {}) {
  return rootLogger.child(context);
}

export { rootLogger };
