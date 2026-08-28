import { describe, expect, it, vi } from "vitest";
import { ZcApiClient } from "./api";

describe("ZcApiClient", () => {
  it("keeps provider credentials out of request contracts", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ data: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    const client = new ZcApiClient(() => "application-token");

    await client.listSessions();

    const [, init] = fetchMock.mock.calls[0];
    expect(init?.headers).toMatchObject({
      Authorization: "Bearer application-token",
    });
    expect(JSON.stringify(init)).not.toContain("ANTHROPIC_API_KEY");
    expect(JSON.stringify(init)).not.toContain("OPENAI_API_KEY");
  });

  it("parses fragmented SSE events and supports cancellation", async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            'event: response.output_text.delta\ndata: {"type":"response.output_text.delta",',
          ),
        );
        controller.enqueue(encoder.encode('"delta":"hello"}\n\n'));
        controller.enqueue(
          encoder.encode(
            'event: response.completed\ndata: {"type":"response.completed","response":{"id":"air_1","output_text":"hello","model":"zc-default","created_at":"2026-07-20T00:00:00Z","usage":{"input_tokens":1,"output_tokens":1}}}\n\n',
          ),
        );
        controller.close();
      },
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(body, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );
    const events: string[] = [];
    const client = new ZcApiClient(() => "");

    await client.streamResponse(
      "chat_1",
      "hello",
      { temperature: 0.3, max_tokens: 100 },
      new AbortController().signal,
      (event) => events.push(event.type),
    );

    expect(events).toEqual([
      "response.output_text.delta",
      "response.completed",
    ]);
  });
});
