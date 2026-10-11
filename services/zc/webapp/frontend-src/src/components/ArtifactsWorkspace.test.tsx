import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ArtifactsWorkspace } from "./ArtifactsWorkspace";
import type { ZcApiClient } from "../api";
import type { ArtifactRecord } from "../types";

const artifactRecord = (): ArtifactRecord => ({
  id: "artifact-1",
  name: "API schema",
  artifact_type: "schema",
  language: "",
  project_id: null,
  tags: [],
  current_version: 3,
  versions: [1, 2, 3].map((version) => ({
    version,
    content: `content v${version}`,
    checksum: `checksum-${version}`,
    response_id: null,
  })),
});

function renderWorkspace(api: Partial<ZcApiClient>) {
  return render(
    <ArtifactsWorkspace
      api={api as ZcApiClient}
      models={[]}
      options={{ temperature: 0.3, max_tokens: 4096 }}
      onOpenSettings={vi.fn()}
      onArtifactOpened={vi.fn()}
    />,
  );
}

describe("ArtifactsWorkspace", () => {
  it("compares the selected version and creates a revision from it", async () => {
    const artifact = artifactRecord();
    const updated = { ...artifact, current_version: 4, versions: [...artifact.versions, { version: 4, content: "content v4", checksum: "checksum-4", response_id: null }] };
    const api = {
      listArtifacts: vi.fn().mockResolvedValue([artifact]),
      listProjects: vi.fn().mockResolvedValue([]),
      artifactDiff: vi.fn().mockResolvedValue("selected diff"),
      iterateArtifact: vi.fn().mockResolvedValue(updated),
    };
    renderWorkspace(api);

    fireEvent.click(await screen.findByRole("button", { name: /API schema/ }));
    fireEvent.click(screen.getByRole("button", { name: /v1/ }));
    fireEvent.click(screen.getByRole("button", { name: "⇄ Compare versions" }));
    await waitFor(() => expect(api.artifactDiff).toHaveBeenCalledWith("artifact-1", 1, 2));
    expect(await screen.findByText(/v1.*v2/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /v1/ }));
    const feedback = screen.getByPlaceholderText("Describe what to improve in the next version…");
    fireEvent.change(feedback, { target: { value: "Keep this version's structure" } });
    fireEvent.submit(feedback.closest("form")!);
    await waitFor(() => expect(api.iterateArtifact).toHaveBeenCalledWith("artifact-1", "Keep this version's structure", undefined, 1));
  });

  it("shows artifact creation errors in the open dialog and permits the server default model", async () => {
    const api = {
      listArtifacts: vi.fn().mockResolvedValue([]),
      listProjects: vi.fn().mockResolvedValue([]),
      createArtifact: vi.fn().mockRejectedValue(new Error("Generation failed")),
    };
    renderWorkspace(api);

    fireEvent.click(await screen.findByRole("button", { name: "＋ Generate artifact" }));
    const form = screen.getByRole("heading", { name: "Generate an artifact" }).closest("form")!;
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Contract" } });
    fireEvent.change(screen.getByLabelText("What should ZCoder create?"), { target: { value: "Create the API contract" } });
    expect(within(form).getByRole("button", { name: "Generate artifact" })).toBeEnabled();
    fireEvent.submit(form);

    expect(await within(form).findByRole("alert")).toHaveTextContent("Generation failed");
  });
});
