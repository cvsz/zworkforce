import { afterEach, describe, expect, it, vi } from "vitest";
import { ZcApiClient } from "./api";

afterEach(() => vi.restoreAllMocks());

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

  it("fetches every page of projects and artifacts", async () => {
    const projectRows = Array.from({ length: 200 }, (_, index) => ({ id: `project-${index}` }));
    const artifactRows = Array.from({ length: 200 }, (_, index) => ({ id: `artifact-${index}` }));
    const jsonResponse = (body: unknown) => new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ data: projectRows, meta: { total: 201, limit: 200, offset: 0 } }))
      .mockResolvedValueOnce(jsonResponse({ data: [{ id: "project-200" }], meta: { total: 201, limit: 200, offset: 200 } }))
      .mockResolvedValueOnce(jsonResponse({ data: artifactRows, meta: { total: 201, limit: 200, offset: 0 } }))
      .mockResolvedValueOnce(jsonResponse({ data: [{ id: "artifact-200" }], meta: { total: 201, limit: 200, offset: 200 } }));
    const client = new ZcApiClient(() => "");

    expect(await client.listProjects()).toHaveLength(201);
    expect(await client.listArtifacts("project-a")).toHaveLength(201);
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(String(fetchMock.mock.calls[1][0])).toContain("offset=200");
    expect(String(fetchMock.mock.calls[2][0])).toContain("project_id=project-a");
    expect(String(fetchMock.mock.calls[3][0])).toContain("offset=200");
  });

  it("sends the selected artifact version when requesting a revision", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: { id: "artifact-1" } }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = new ZcApiClient(() => "");

    await client.iterateArtifact("artifact-1", "Use the selected version", undefined, 2);

    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect(JSON.parse(String(init?.body))).toMatchObject({
      feedback: "Use the selected version",
      source_version: 2,
    });
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
