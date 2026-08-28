import { mkdir, open, readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';

function clone(value) {
  return structuredClone(value);
}

function parseJsonLines(raw) {
  if (!raw.trim()) return [];
  return raw.split('\n').filter(Boolean).map((line) => JSON.parse(line));
}

export class FileProactiveStore {
  constructor({ dataDir = process.env.ZARVIS_PROACTIVE_DATA_DIR ?? './var/zarvis-proactive' } = {}) {
    this.dataDir = resolve(dataDir);
    this.eventsPath = join(this.dataDir, 'proactive-events.jsonl');
    this.writeChain = Promise.resolve();
  }

  async initialize() {
    await mkdir(this.dataDir, { recursive: true, mode: 0o700 });
    try {
      const handle = await open(this.eventsPath, 'wx', 0o600);
      await handle.close();
    } catch (error) {
      if (error?.code !== 'EEXIST') throw error;
    }
  }

  async readEvents() {
    await this.initialize();
    return parseJsonLines(await readFile(this.eventsPath, 'utf8'));
  }

  async appendEvent(event) {
    await this.initialize();
    const operation = async () => {
      const handle = await open(this.eventsPath, 'a', 0o600);
      try {
        await handle.writeFile(`${JSON.stringify(event)}\n`);
        await handle.sync();
      } finally {
        await handle.close();
      }
    };
    this.writeChain = this.writeChain.then(operation, operation);
    return this.writeChain;
  }
}

export class MemoryProactiveStore {
  constructor() {
    this.events = [];
  }

  async initialize() {}

  async readEvents() {
    return clone(this.events);
  }

  async appendEvent(event) {
    this.events.push(clone(event));
  }
}
