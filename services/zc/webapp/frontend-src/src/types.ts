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

export type ProjectStatus = "planning" | "active" | "paused" | "done" | "archived";
export type TaskStatus = "todo" | "in_progress" | "done" | "blocked";

export interface ProjectTask {
  id: string;
  title: string;
  description: string;
  agent: string;
  priority: "low" | "medium" | "high" | "critical";
  status: TaskStatus;
  result: string;
}

export interface ProjectRecord {
  id: string;
  name: string;
  description: string;
  template: string;
  status: ProjectStatus;
  context: string;
  tasks: ProjectTask[];
  tags: string[];
  run_log: Array<{ task_id: string; response_id: string; status: string }>;
  created_at?: string;
  updated_at?: string;
}

export interface ArtifactVersion {
  version: number;
  content: string;
  checksum: string;
  response_id: string | null;
}

export interface ArtifactRecord {
  id: string;
  name: string;
  artifact_type: "code" | "document" | "config" | "test" | "schema" | "prompt" | "data" | "other";
  language: string;
  project_id: string | null;
  tags: string[];
  current_version: number;
  versions: ArtifactVersion[];
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
