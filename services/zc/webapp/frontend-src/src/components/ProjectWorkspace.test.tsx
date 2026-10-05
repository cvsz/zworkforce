import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProjectWorkspace } from "./ProjectWorkspace";
import type { ZcApiClient } from "../api";
import type { ProjectRecord, ProjectTask } from "../types";

const projectRecord = (tasks: ProjectTask[] = []): ProjectRecord => ({
  id: "project-1",
  name: "Workspace project",
  description: "",
  template: "blank",
  status: "planning",
  context: "",
  tasks,
  tags: [],
  run_log: [],
});

const taskRecord: ProjectTask = {
  id: "task-1",
  title: "Review API",
  description: "Inspect the API boundary",
  agent: "optimizer",
  priority: "medium",
  status: "todo",
  result: "",
};

function renderWorkspace(api: Partial<ZcApiClient>, agents = ["code_generator", "optimizer"]) {
  return render(
    <ProjectWorkspace
      api={api as ZcApiClient}
      models={[]}
      agents={agents}
      options={{ temperature: 0.3, max_tokens: 4096 }}
      onOpenArtifacts={vi.fn()}
      onOpenSettings={vi.fn()}
    />,
  );
}

describe("ProjectWorkspace", () => {
  it("uses discovered agents and allows the server default model", async () => {
    const project = projectRecord();
    const api = {
      listProjects: vi.fn().mockResolvedValue([]),
      createProject: vi.fn().mockResolvedValue(project),
      createProjectTask: vi.fn().mockResolvedValue(taskRecord),
    };
    renderWorkspace(api);

    fireEvent.click(await screen.findByRole("button", { name: "＋ New project" }));
    const projectForm = screen.getByRole("heading", { name: "New project" }).closest("form")!;
    fireEvent.change(screen.getByLabelText("Project name"), { target: { value: project.name } });
    fireEvent.submit(projectForm);
    await screen.findByRole("heading", { name: project.name });

    fireEvent.click(screen.getByRole("button", { name: "＋ Add task" }));
    expect(screen.getByRole("option", { name: "Optimizer" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Task title"), { target: { value: taskRecord.title } });
    fireEvent.change(screen.getByLabelText("Instructions"), { target: { value: taskRecord.description } });
    fireEvent.change(screen.getByLabelText("Agent"), { target: { value: "optimizer" } });
    const taskForm = screen.getByRole("heading", { name: "Add a task" }).closest("form")!;
    fireEvent.submit(taskForm);

    await waitFor(() => expect(api.createProjectTask).toHaveBeenCalledWith("project-1", expect.objectContaining({ agent: "optimizer" })));
    expect(screen.getByRole("button", { name: /Run with ZCoder/ })).toBeEnabled();
  });

  it("prevents a duplicate project request and shows failures inside the dialog", async () => {
    const project = projectRecord();
    let resolveCreate!: (value: ProjectRecord) => void;
    const pendingCreate = new Promise<ProjectRecord>((resolve) => { resolveCreate = resolve; });
    const createProject = vi.fn().mockReturnValue(pendingCreate);
    const api = { listProjects: vi.fn().mockResolvedValue([]), createProject };
    const firstRender = renderWorkspace(api);

    fireEvent.click(await screen.findByRole("button", { name: "＋ New project" }));
    const form = screen.getByRole("heading", { name: "New project" }).closest("form")!;
    fireEvent.change(screen.getByLabelText("Project name"), { target: { value: project.name } });
    fireEvent.submit(form);
    fireEvent.submit(form);

    expect(createProject).toHaveBeenCalledTimes(1);
    expect(within(form).getByRole("button", { name: "Creating…" })).toBeDisabled();
    resolveCreate(project);
    await screen.findByRole("heading", { name: project.name });
    firstRender.unmount();

    const failingApi = {
      listProjects: vi.fn().mockResolvedValue([]),
      createProject: vi.fn().mockRejectedValue(new Error("Project service unavailable")),
    };
    const { unmount } = renderWorkspace(failingApi);
    fireEvent.click(await screen.findByRole("button", { name: "＋ New project" }));
    const failingForm = screen.getByRole("heading", { name: "New project" }).closest("form")!;
    fireEvent.change(screen.getByLabelText("Project name"), { target: { value: "Fails" } });
    fireEvent.submit(failingForm);
    expect(await within(failingForm).findByRole("alert")).toHaveTextContent("Project service unavailable");
    unmount();
  });

  it("prevents duplicate task requests and shows task failures inside the dialog", async () => {
    const project = projectRecord();
    let resolveTask!: (value: ProjectTask) => void;
    const pendingTask = new Promise<ProjectTask>((resolve) => { resolveTask = resolve; });
    const createProjectTask = vi.fn().mockReturnValue(pendingTask);
    const api = { listProjects: vi.fn().mockResolvedValue([project]), createProjectTask };
    const firstRender = renderWorkspace(api);

    fireEvent.click(await screen.findByRole("button", { name: /Workspace project/ }));
    fireEvent.click(screen.getByRole("button", { name: "＋ Add task" }));
    const form = screen.getByRole("heading", { name: "Add a task" }).closest("form")!;
    fireEvent.change(screen.getByLabelText("Task title"), { target: { value: taskRecord.title } });
    fireEvent.submit(form);
    fireEvent.submit(form);

    expect(createProjectTask).toHaveBeenCalledTimes(1);
    expect(within(form).getByRole("button", { name: "Adding…" })).toBeDisabled();
    resolveTask(taskRecord);
    await screen.findByRole("heading", { name: taskRecord.title });
    firstRender.unmount();

    const failingApi = {
      listProjects: vi.fn().mockResolvedValue([project]),
      createProjectTask: vi.fn().mockRejectedValue(new Error("Task service unavailable")),
    };
    renderWorkspace(failingApi);
    fireEvent.click(await screen.findByRole("button", { name: /Workspace project/ }));
    fireEvent.click(screen.getByRole("button", { name: "＋ Add task" }));
    const failingForm = screen.getByRole("heading", { name: "Add a task" }).closest("form")!;
    fireEvent.change(screen.getByLabelText("Task title"), { target: { value: taskRecord.title } });
    fireEvent.submit(failingForm);

    expect(await within(failingForm).findByRole("alert")).toHaveTextContent("Task service unavailable");
  });
});
