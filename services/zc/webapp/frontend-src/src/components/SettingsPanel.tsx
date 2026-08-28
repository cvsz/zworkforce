import type { Capabilities, ResponseOptions } from "../types";

interface SettingsPanelProps {
  open: boolean;
  token: string;
  models: string[];
  capabilities: Capabilities;
  options: ResponseOptions;
  onToken: (value: string) => void;
  onOptions: (value: ResponseOptions) => void;
  onClose: () => void;
}

export function SettingsPanel({
  open,
  token,
  models,
  capabilities,
  options,
  onToken,
  onOptions,
  onClose,
}: SettingsPanelProps) {
  if (!open) return null;
  const select = (
    key: "model" | "agent" | "personality" | "skill",
    value: string,
  ) => onOptions({ ...options, [key]: value });
  return (
    <div className="settings-backdrop" onMouseDown={onClose}>
      <section
        className="settings-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <span className="eyebrow">Workspace</span>
            <h2 id="settings-title">Response settings</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close settings">
            ×
          </button>
        </header>
        <label>
          Application bearer token
          <input
            type="password"
            value={token}
            onChange={(event) => onToken(event.target.value)}
            autoComplete="off"
            placeholder="Held in memory only"
          />
          <small>Provider credentials never enter the browser.</small>
        </label>
        <div className="settings-grid">
          <label>
            Model
            <select value={options.model ?? ""} onChange={(event) => select("model", event.target.value)}>
              <option value="">Server default</option>
              {models.map((model) => <option key={model}>{model}</option>)}
            </select>
          </label>
          <label>
            Agent
            <select value={options.agent ?? ""} onChange={(event) => select("agent", event.target.value)}>
              <option value="">None</option>
              {capabilities.agents.map((agent) => <option key={agent}>{agent}</option>)}
            </select>
          </label>
          <label>
            Personality
            <select value={options.personality ?? ""} onChange={(event) => select("personality", event.target.value)}>
              <option value="">Default</option>
              {capabilities.personalities.map((personality) => <option key={personality}>{personality}</option>)}
            </select>
          </label>
          <label>
            Skill
            <select value={options.skill ?? ""} onChange={(event) => select("skill", event.target.value)}>
              <option value="">None</option>
              {capabilities.skills.map((skill) => <option key={skill}>{skill}</option>)}
            </select>
          </label>
        </div>
        <label>
          System instruction
          <textarea
            rows={4}
            value={options.system ?? ""}
            onChange={(event) => onOptions({ ...options, system: event.target.value })}
            maxLength={100_000}
          />
        </label>
        <div className="settings-grid">
          <label>
            Temperature · {options.temperature.toFixed(1)}
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={options.temperature}
              onChange={(event) => onOptions({ ...options, temperature: Number(event.target.value) })}
            />
          </label>
          <label>
            Max tokens
            <input
              type="number"
              min="1"
              max="65536"
              value={options.max_tokens}
              onChange={(event) => onOptions({ ...options, max_tokens: Number(event.target.value) })}
            />
          </label>
        </div>
      </section>
    </div>
  );
}
