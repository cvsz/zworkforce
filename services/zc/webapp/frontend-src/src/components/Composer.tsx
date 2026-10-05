import { useEffect, useRef } from "react";

interface ComposerProps {
  value: string;
  busy: boolean;
  disabled: boolean;
  agent?: string;
  model?: string;
  onOpenSettings: () => void;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onStop: () => void;
}

export function Composer({
  value,
  busy,
  disabled,
  agent,
  model,
  onOpenSettings,
  onChange,
  onSubmit,
  onStop,
}: ComposerProps) {
  const input = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const element = input.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 220)}px`;
  }, [value]);

  return (
    <div className="composer-shell">
      <div className="composer">
        <textarea
          ref={input}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSubmit();
            }
          }}
          disabled={disabled}
          rows={1}
          maxLength={200_000}
          placeholder="Ask ZCoder to build, review, explain, or investigate…"
          aria-label="Message"
        />
        {busy ? (
          <button className="send-button stop" onClick={onStop} aria-label="Stop response">
            ■
          </button>
        ) : (
          <button
            className="send-button"
            onClick={onSubmit}
            disabled={disabled || !value.trim()}
            aria-label="Send message"
          >
            ↑
          </button>
        )}
      </div>
      <div className="composer-foot">
        <div className="composer-context">
          <button onClick={onOpenSettings}><span className="context-mark">◈</span>{agent || "General agent"}<span>⌄</span></button>
          <button onClick={onOpenSettings}>{model || "Default model"}<span>⌄</span></button>
        </div>
        <p>Enter to send <span>·</span> Shift + Enter for a new line</p>
      </div>
    </div>
  );
}
