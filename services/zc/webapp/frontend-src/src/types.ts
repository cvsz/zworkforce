export interface Usage {
  input_tokens: number | null;
  output_tokens: number | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  model: string | null;
  usage: Usage;
}

export interface ChatSession {
  id: string;
  object: "chat.session";
  title: string;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
}

export interface Capabilities {
  agents: string[];
  personalities: string[];
  skills: string[];
}

export interface ResponseOptions {
  model?: string;
  agent?: string;
  personality?: string;
  skill?: string;
  system?: string;
  temperature: number;
  max_tokens: number;
}

export type StreamEvent =
  | { type: "response.started"; response: { id: string; created_at: string } }
  | { type: "response.output_text.delta"; delta: string }
  | {
      type: "response.completed";
      response: {
        id: string;
        output_text: string;
        model: string;
        created_at: string;
        usage: Usage;
      };
    }
  | {
      type: "response.error";
      error: { code: string; message: string };
    };
