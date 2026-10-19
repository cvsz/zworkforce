/**
 * M12 Tool Registry — spec §6
 *
 * Tools are deny-by-default. A tool call is only permitted when:
 * 1. The tool name is in the registry.
 * 2. The session's capability grants include the tool.
 * 3. Mutating tools have an explicit approval record attached to the session.
 *
 * No credentials are stored here. Tool implementations receive only the
 * args validated against their declared schema — never raw session/DB access.
 *
 * This module is pure domain logic with no I/O dependencies.
 */
"use strict";

class DuplicateToolError extends Error {
  constructor(name) {
    super(`Tool already registered: ${name}`);
    this.name = "DuplicateToolError";
  }
}

class ToolNotFoundError extends Error {
  constructor(name) {
    super(`Tool not found: ${name}`);
    this.name = "ToolNotFoundError";
  }
}

class ApprovalRequiredError extends Error {
  constructor(name) {
    super(`Mutating tool "${name}" requires an explicit approval record`);
    this.name = "ApprovalRequiredError";
  }
}

class ToolNotGrantedError extends Error {
  constructor(name) {
    super(`Tool not granted in session capabilities: ${name}`);
    this.name = "ToolNotGrantedError";
  }
}

class ToolRegistry {
  constructor() {
    this.tools = new Map();
  }

  register({ name, description, mutating, schema, handler }) {
    if (this.tools.has(name)) {
      throw new DuplicateToolError(name);
    }
    this.tools.set(name, { name, description, mutating, schema, handler });
  }

  get(name) {
    const tool = this.tools.get(name);
    if (!tool) {
      throw new ToolNotFoundError(name);
    }
    return tool;
  }

  list() {
    return Array.from(this.tools.values())
      .map(({ name, description, mutating }) => ({
        name,
        description,
        mutating,
      }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }

  async invoke(name, args, context, { approvalRecord = null } = {}) {
    const tool = this.get(name);

    if (tool.mutating && !approvalRecord) {
      throw new ApprovalRequiredError(name);
    }

    let validatedArgs = args;
    if (tool.schema) {
      try {
        // Handle Zod schema parsing or similar
        validatedArgs = tool.schema.parseAsync
          ? await tool.schema.parseAsync(args)
          : await tool.schema.validate(args);
      } catch (err) {
        throw this._sanitizeError(err, args);
      }
    }

    try {
      return await tool.handler(validatedArgs, context);
    } catch (error) {
      throw this._sanitizeError(error, args);
    }
  }

  assertGranted(name, sessionCapabilities) {
    if (!sessionCapabilities || !sessionCapabilities.includes(name)) {
      throw new ToolNotGrantedError(name);
    }
  }

  _sanitizeError(error, args) {
    if (!args || typeof args !== "object") return error;

    const credentialKeys = ["token", "secret", "key", "password"];
    let message = error.message;
    let changed = false;

    for (const key of credentialKeys) {
      if (args[key] && typeof args[key] === "string") {
        if (message.includes(args[key])) {
          message = message.split(args[key]).join("***");
          changed = true;
        }
      }
    }

    if (changed) {
      const newError = new error.constructor(message);
      newError.stack = error.stack;
      return newError;
    }
    return error;
  }
}

function createToolRegistry() {
  return new ToolRegistry();
}

function clampLimit(raw, fallback = 25, max = 100) {
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(Math.max(Math.trunc(parsed), 1), max);
}

function registerBuiltins(registry, { pool }) {
  registry.register({
    name: "queue.read",
    description: "Reads publication_queue",
    mutating: false,
    schema: null,
    handler: async (args) => {
      const status = typeof args.status === "string" ? args.status : null;
      const limit = clampLimit(args.limit, 25);
      const params = [limit];
      let where = "";
      if (status) {
        params.unshift(status);
        where = "WHERE status = $1";
      }
      const result = await pool.query(
        `SELECT id, status, message, created_at\n         FROM publication_queue\n         ${where}\n         ORDER BY created_at ASC\n         LIMIT $${status ? 2 : 1}`,
        params,
      );
      return {
        count: result.rowCount,
        status: status ?? "all",
        items: result.rows.map((row) => ({
          id: row.id,
          status: row.status,
          message: row.message,
          created_at: row.created_at,
        })),
      };
    },
  });

  registry.register({
    name: "session.status",
    description: "Reads operator session state",
    mutating: false,
    schema: null,
    handler: async (args, context) => {
      const { session } = context;
      return {
        id: session.id,
        state: session.state,
        mode: session.mode,
        generation: session.generation,
        last_sequence_id: session.lastSequenceId ?? 0,
      };
    },
  });

  registry.register({
    name: "events.recent",
    description: "Reads recent session events",
    mutating: false,
    schema: null,
    handler: async (args, context) => {
      const { session, repository } = context;
      const limit = clampLimit(args.limit, 25);
      const events = await repository.listEventsAfter(session.id, 0, limit);
      return {
        count: events.length,
        items: events.map((event) => ({
          event_id: event.event_id,
          sequence_id: event.sequence_id,
          type: event.type,
          occurred_at: event.occurred_at,
        })),
      };
    },
  });
}

module.exports = {
  ToolRegistry,
  DuplicateToolError,
  ToolNotFoundError,
  ApprovalRequiredError,
  ToolNotGrantedError,
  createToolRegistry,
  registerBuiltins,
};
