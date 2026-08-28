import type {
  Capabilities,
  ChatSession,
  ResponseOptions,
  StreamEvent,
} from "./types";

interface Envelope<T> {
  data: T;
}

interface Page<T> extends Envelope<T[]> {
  meta: { total: number; limit: number; offset: number };
}

export class ZcApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export class ZcApiClient {
  constructor(private readonly token: () => string) {}

  private headers(json = false): HeadersInit {
    const headers: Record<string, string> = {};
    const token = this.token().trim();
    if (token) headers.Authorization = `Bearer ${token}`;
    if (json) headers["Content-Type"] = "application/json";
    return headers;
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(path, {
      credentials: "same-origin",
      ...init,
      headers: {
        ...this.headers(Boolean(init?.body)),
        ...init?.headers,
      },
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      const message =
        payload?.error?.message ??
        payload?.detail ??
        `Request failed with HTTP ${response.status}`;
      throw new ZcApiError(message, response.status);
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }

  async listSessions(): Promise<ChatSession[]> {
    return (await this.request<Page<ChatSession>>("/v1/chat/sessions")).data;
  }

  async getSession(id: string): Promise<ChatSession> {
    return (
      await this.request<Envelope<ChatSession>>(
        `/v1/chat/sessions/${encodeURIComponent(id)}`,
      )
    ).data;
  }

  async createSession(): Promise<ChatSession> {
    return (
      await this.request<Envelope<ChatSession>>("/v1/chat/sessions", {
        method: "POST",
        body: JSON.stringify({}),
      })
    ).data;
  }

  async renameSession(id: string, title: string): Promise<ChatSession> {
    return (
      await this.request<Envelope<ChatSession>>(
        `/v1/chat/sessions/${encodeURIComponent(id)}`,
        {
          method: "PATCH",
          body: JSON.stringify({ title }),
        },
      )
    ).data;
  }

  async deleteSession(id: string): Promise<void> {
    await this.request<void>(`/v1/chat/sessions/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  }

  async models(): Promise<string[]> {
    const result = await this.request<
      Envelope<Array<{ id: string; object: "model" }>>
    >("/v1/ai/models");
    return result.data.map((model) => model.id);
  }

  async capabilities(): Promise<Capabilities> {
    return (
      await this.request<Envelope<Capabilities>>("/v1/ai/capabilities")
    ).data;
  }

  async streamResponse(
    sessionId: string,
    prompt: string,
    options: ResponseOptions,
    signal: AbortSignal,
    onEvent: (event: StreamEvent) => void,
  ): Promise<void> {
    const body = {
      prompt,
      model: options.model || undefined,
      agent: options.agent || undefined,
      personality: options.personality || undefined,
      skill: options.skill || undefined,
      system: options.system || undefined,
      temperature: options.temperature,
      max_tokens: options.max_tokens,
    };
    const response = await fetch(
      `/v1/chat/sessions/${encodeURIComponent(sessionId)}/responses`,
      {
        method: "POST",
        credentials: "same-origin",
        headers: this.headers(true),
        body: JSON.stringify(body),
        signal,
      },
    );
    if (!response.ok || !response.body) {
      throw new ZcApiError(
        `Streaming request failed with HTTP ${response.status}`,
        response.status,
      );
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const data = frame
          .split("\n")
          .find((line) => line.startsWith("data: "));
        if (!data) continue;
        onEvent(JSON.parse(data.slice(6)) as StreamEvent);
      }
    }
  }
}
