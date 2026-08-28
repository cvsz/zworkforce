import { mkdir, open, readFile, rename, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';

const DEFAULT_STATE = Object.freeze({
  schema_version: 'zarvis.local-action-state.v1',
  emergency_stop: false,
  emergency_reason: null,
  preferences: {},
  updated_at: null,
});

function clone(value) {
  return structuredClone(value);
}

function parseJsonLines(raw) {
  if (!raw.trim()) return [];
  return raw
    .split('\n')
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

export class FileActionStore {
  constructor({ dataDir = process.env.ZARVIS_ACTION_DATA_DIR ?? './var/zarvis-action' } = {}) {
    this.dataDir = resolve(dataDir);
    this.eventsPath = join(this.dataDir, 'action-events.jsonl');
    this.statePath = join(this.dataDir, 'local-state.json');
    this.writeChain = Promise.resolve();
  }

  async initialize() {
    await mkdir(this.dataDir, { recursive: true, mode: 0o700 });
    await this.#ensureFile(this.eventsPath, '');
    try {
      await readFile(this.statePath, 'utf8');
    } catch (error) {
      if (error?.code !== 'ENOENT') throw error;
      await this.#atomicWrite(this.statePath, JSON.stringify(DEFAULT_STATE, null, 2));
    }
  }

  async #ensureFile(path, initial) {
    try {
      const handle = await open(path, 'wx', 0o600);
      await handle.writeFile(initial);
      await handle.close();
    } catch (error) {
      if (error?.code !== 'EEXIST') throw error;
    }
  }

  async #atomicWrite(path, content) {
    await mkdir(dirname(path), { recursive: true, mode: 0o700 });
    const temporaryPath = `${path}.tmp`;
    await writeFile(temporaryPath, content, { mode: 0o600 });
    await rename(temporaryPath, path);
  }

  async readEvents() {
    await this.initialize();
    return parseJsonLines(await readFile(this.eventsPath, 'utf8'));
  }

  async appendEvent(event) {
    await this.initialize();
    this.writeChain = this.writeChain.then(async () => {
      const handle = await open(this.eventsPath, 'a', 0o600);
      try {
        await handle.writeFile(`${JSON.stringify(event)}\n`);
        await handle.sync();
      } finally {
        await handle.close();
      }
    });
    return this.writeChain;
  }

  async readState() {
    await this.initialize();
    const parsed = JSON.parse(await readFile(this.statePath, 'utf8'));
    return {
      ...clone(DEFAULT_STATE),
      ...parsed,
      preferences: { ...(parsed.preferences ?? {}) },
    };
  }

  async writeState(state) {
    await this.initialize();
    this.writeChain = this.writeChain.then(() =>
      this.#atomicWrite(this.statePath, `${JSON.stringify(state, null, 2)}\n`),
    );
    await this.writeChain;
    return clone(state);
  }
}

export class MemoryActionStore {
  constructor() {
    this.events = [];
    this.state = clone(DEFAULT_STATE);
  }

  async initialize() {}

  async readEvents() {
    return clone(this.events);
  }

  async appendEvent(event) {
    this.events.push(clone(event));
  }

  async readState() {
    return clone(this.state);
  }

  async writeState(state) {
    this.state = clone(state);
    return this.readState();
  }
}
