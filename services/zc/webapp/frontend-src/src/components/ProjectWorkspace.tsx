import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { ZcApiClient, ZcApiError } from "../api";
import { Markdown } from "./Markdown";
import type { ProjectRecord, ProjectTask, ResponseOptions } from "../types";

interface ProjectWorkspaceProps {
  api: ZcApiClient;
  models: string[];
  options: ResponseOptions;
  onOpenArtifacts: (artifactId: string) => void;
  onOpenSettings: () => void;
}

const TEMPLATES = [
  ["blank", "Blank project"],
  ["web_app", "Web application"],
  ["api", "API service"],
  ["cli_tool", "CLI tool"],
  ["data_pipeline", "Data pipeline"],
  ["ml_model", "ML model"],
] as const;

function percentDone(project: ProjectRecord) {
  if (!project.tasks.length) return 0;
  return Math.round((project.tasks.filter((task) => task.status === "done").length / project.tasks.length) * 100);
}

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function ProjectWorkspace({ api, models, options, onOpenArtifacts, onOpenSettings }: ProjectWorkspaceProps) {
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [active, setActive] = useState<ProjectRecord | null>(null);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [planning, setPlanning] = useState(false);
  const [runningTask, setRunningTask] = useState(false);
  const [savingArtifact, setSavingArtifact] = useState(false);
  const [error, setError] = useState("");
  const [projectDialog, setProjectDialog] = useState(false);
  const [taskDialog, setTaskDialog] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  const [projectTemplate, setProjectTemplate] = useState("blank");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDescription, setTaskDescription] = useState("");
  const [taskAgent, setTaskAgent] = useState("code_generator");
  const [taskPriority, setTaskPriority] = useState<ProjectTask["priority"]>("medium");

  const reportError = (caught: unknown, fallback: string) => {
    if (caught instanceof ZcApiError && caught.status === 401) {
      setError("Connect with an application token to use project tools.");
      onOpenSettings();
    } else {
      setError(caught instanceof Error ? caught.message : fallback);
    }
  };

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await api.listProjects();
      setProjects(result);
      if (active) {
        const current = result.find((project) => project.id === active.id);
        if (current) setActive(current);
        else setActive(null);
      }
    } catch (caught) {
      reportError(caught, "Unable to load projects.");
    } finally {
      setLoading(false);
    }
  }, [active, api]);

  useEffect(() => {
    void loadProjects();
  }, []); // Load the project index once when this view opens.

  const selectedTask = useMemo(
    () => active?.tasks.find((task) => task.id === activeTaskId) ?? null,
    [active, activeTaskId],
  );

  const replaceProject = (project: ProjectRecord) => {
    setActive(project);
    setProjects((current) => [project, ...current.filter((item) => item.id !== project.id)]);
  };

  const createProject = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      const project = await api.createProject({
        name: projectName.trim(),
        description: projectDescription.trim(),
        template: projectTemplate,
      });
      replaceProject(project);
      setActiveTaskId(project.tasks[0]?.id ?? null);
      setProjectDialog(false);
      setProjectName("");
      setProjectDescription("");
      setProjectTemplate("blank");
      setError("");
    } catch (caught) {
      reportError(caught, "Unable to create project.");
    }
  };

  const createPlan = async () => {
    if (!active) return;
    setPlanning(true);
    setError("");
    try {
      const project = await api.planProject(active.id, options.model);
      replaceProject(project);
      setActiveTaskId(project.tasks.find((task) => task.status === "todo")?.id ?? null);
    } catch (caught) {
      reportError(caught, "Unable to create a plan.");
    } finally {
      setPlanning(false);
    }
  };

  const createTask = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!active) return;
    try {
      await api.createProjectTask(active.id, {
        title: taskTitle.trim(),
        description: taskDescription.trim(),
        agent: taskAgent,
        priority: taskPriority,
      });
      const project = await api.getProject(active.id);
      replaceProject(project);
      setActiveTaskId(project.tasks[project.tasks.length - 1]?.id ?? null);
      setTaskDialog(false);
      setTaskTitle("");
      setTaskDescription("");
      setTaskAgent("code_generator");
      setTaskPriority("medium");
      setError("");
    } catch (caught) {
      reportError(caught, "Unable to add task.");
    }
  };

  const runTask = async () => {
    if (!active || !selectedTask) return;
    setRunningTask(true);
    setError("");
    try {
      await api.runProjectTask(active.id, selectedTask.id, options.model);
      const project = await api.getProject(active.id);
      replaceProject(project);
    } catch (caught) {
      reportError(caught, "Unable to run this task.");
      const project = await api.getProject(active.id).catch(() => null);
      if (project) replaceProject(project);
    } finally {
      setRunningTask(false);
    }
  };

  const saveResultAsArtifact = async () => {
    if (!active || !selectedTask?.result) return;
    setSavingArtifact(true);
    setError("");
    try {
      const artifact = await api.createArtifact({
        name: selectedTask.title,
        artifact_type: "other",
        content: selectedTask.result,
        project_id: active.id,
      });
      onOpenArtifacts(artifact.id);
    } catch (caught) {
      reportError(caught, "Unable to save this result as an artifact.");
    } finally {
      setSavingArtifact(false);
    }
  };

  if (active) {
    const completion = percentDone(active);
    return (
      <section className="project-workspace">
        <div className="view-heading project-heading">
          <div>
            <button className="back-link" onClick={() => { setActive(null); setActiveTaskId(null); }}>← All projects</button>
            <span className="eyebrow">Project workspace</span>
            <h1>{active.name}</h1>
            <p>{active.description || "Add project context to keep the work focused."}</p>
          </div>
          <div className="heading-actions">
            <button className="button-secondary" onClick={() => void createPlan()} disabled={planning || !models.length}>
              {planning ? <><span className="spinner" /> Planning…</> : "✦ Plan with agent"}
            </button>
            <button className="button-primary" onClick={() => setTaskDialog(true)}>＋ Add task</button>
          </div>
        </div>

        {error && <div className="inline-error" role="alert"><span>{error}</span><button onClick={() => setError("")} aria-label="Dismiss error">×</button></div>}

        <div className="project-summary">
          <div className="progress-copy"><span>{label(active.status)}</span><strong>{completion}% complete</strong></div>
          <div className="progress-track"><span style={{ width: `${completion}%` }} /></div>
          <div className="summary-stats">
            <span><strong>{active.tasks.length}</strong> tasks</span>
            <span><strong>{active.tasks.filter((task) => task.status === "done").length}</strong> complete</span>
            <span><strong>{active.run_log.length}</strong> agent runs</span>
            <span className="template-chip">{label(active.template)}</span>
          </div>
        </div>

        <div className="task-workbench">
          <section className="task-list-panel" aria-label="Project tasks">
            <div className="section-heading"><div><span className="eyebrow">Execution plan</span><h2>Tasks</h2></div><span className="count-pill">{active.tasks.length}</span></div>
            {active.tasks.length ? (
              <div className="task-list">
                {active.tasks.map((task, index) => (
                  <button className={`task-row ${task.id === activeTaskId ? "selected" : ""}`} key={task.id} onClick={() => setActiveTaskId(task.id)}>
                    <span className={`task-check status-${task.status}`}>{task.status === "done" ? "✓" : task.status === "in_progress" ? "·" : index + 1}</span>
                    <span className="task-row-copy"><strong>{task.title}</strong><span>{task.agent || "General agent"} · {label(task.priority)} priority</span></span>
                    <span className={`status-label status-${task.status}`}>{label(task.status)}</span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="empty-inline"><strong>No tasks yet</strong><span>Ask the agent to draft a plan or add the first task yourself.</span></div>
            )}
            <button className="task-add-inline" onClick={() => setTaskDialog(true)}>＋ Add a task to this plan</button>
          </section>

          <aside className="task-detail-panel">
            {selectedTask ? (
              <>
                <div className="detail-topline"><span className="eyebrow">Task detail</span><span className={`status-label status-${selectedTask.status}`}>{label(selectedTask.status)}</span></div>
                <h2>{selectedTask.title}</h2>
                <p className="task-description">{selectedTask.description || "No task description."}</p>
                <div className="detail-meta"><span><small>Agent</small><strong>{selectedTask.agent || "General agent"}</strong></span><span><small>Priority</small><strong>{label(selectedTask.priority)}</strong></span>{options.model && <span><small>Model</small><strong>{options.model}</strong></span>}</div>
                {selectedTask.result ? (
                  <div className="task-result">
                    <div className="result-heading"><span className="eyebrow">Agent result</span><button className="quiet-button" onClick={() => void saveResultAsArtifact()} disabled={savingArtifact}>{savingArtifact ? <><span className="spinner" /> Saving…</> : "Save as artifact ↗"}</button></div>
                    <div className="markdown-body"><Markdown>{selectedTask.result}</Markdown></div>
                  </div>
                ) : (
                  <div className="result-placeholder"><span className="result-glyph">↳</span><strong>Ready for an agent run</strong><span>The agent will return a saved result for this task.</span></div>
                )}
                <button className="button-primary run-task-button" onClick={() => void runTask()} disabled={runningTask || !models.length}>
                  {runningTask ? <><span className="spinner" /> Running task…</> : selectedTask.status === "done" ? "↻ Run again" : "▶ Run with ZCoder"}
                </button>
                <p className="field-hint">Runs return an AI result and don’t edit repository files from this screen.</p>
                {!models.length && <p className="field-hint">Connect to the ZC API to load models and run tasks.</p>}
              </>
            ) : (
              <div className="detail-empty"><span className="detail-empty-icon">⌁</span><strong>Select a task</strong><span>Choose a task to review its instructions and agent result.</span></div>
            )}
          </aside>
        </div>

        {!!active.run_log.length && (
          <section className="recent-runs">
            <div className="section-heading"><div><span className="eyebrow">Project activity</span><h2>Recent agent runs</h2></div><span className="count-pill">{active.run_log.length}</span></div>
            <div className="run-log-list">
              {[...active.run_log].reverse().slice(0, 5).map((run, index) => {
                const task = active.tasks.find((item) => item.id === run.task_id);
                return <button key={`${run.response_id}-${index}`} onClick={() => task && setActiveTaskId(task.id)}><span className="run-dot" /><span><strong>{task?.title ?? "Task run"}</strong><small>{run.status === "done" ? "Result saved to this project" : label(run.status)}</small></span><span className="run-id">{run.response_id.slice(0, 12)}</span></button>;
              })}
            </div>
          </section>
        )}

        {taskDialog && (
          <div className="modal-backdrop" onMouseDown={() => setTaskDialog(false)}>
            <form className="modal-card" onSubmit={(event) => void createTask(event)} onMouseDown={(event) => event.stopPropagation()}>
              <div className="modal-title"><div><span className="eyebrow">Project plan</span><h2>Add a task</h2></div><button type="button" className="icon-button" onClick={() => setTaskDialog(false)} aria-label="Close">×</button></div>
              <label>Task title<input value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} maxLength={300} required autoFocus placeholder="Implement sign-in flow" /></label>
              <label>Instructions<textarea value={taskDescription} onChange={(event) => setTaskDescription(event.target.value)} rows={4} maxLength={20_000} placeholder="Describe the outcome and constraints" /></label>
              <div className="form-pair"><label>Agent<select value={taskAgent} onChange={(event) => setTaskAgent(event.target.value)}><option value="code_generator">Code generator</option><option value="code_reviewer">Code reviewer</option><option value="testing_agent">Testing agent</option><option value="documentation_agent">Documentation agent</option><option value="security_auditor">Security auditor</option><option value="full_stack">Full stack</option></select></label><label>Priority<select value={taskPriority} onChange={(event) => setTaskPriority(event.target.value as ProjectTask["priority"])}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select></label></div>
              <div className="modal-actions"><button type="button" className="button-secondary" onClick={() => setTaskDialog(false)}>Cancel</button><button type="submit" className="button-primary">Add task</button></div>
            </form>
          </div>
        )}
      </section>
    );
  }

  return (
    <section className="project-workspace">
      <div className="view-heading">
        <div><span className="eyebrow">ZCoder workspace</span><h1>Projects</h1><p>Turn a goal into a plan, then run focused tasks with an agent.</p></div>
        <button className="button-primary" onClick={() => setProjectDialog(true)}>＋ New project</button>
      </div>
      {error && <div className="inline-error" role="alert"><span>{error}</span><button onClick={() => setError("")} aria-label="Dismiss error">×</button></div>}
      {loading ? <div className="loading-state"><span className="spinner" /> Loading projects…</div> : projects.length ? (
        <div className="project-grid">
          {projects.map((project) => {
            const done = project.tasks.filter((task) => task.status === "done").length;
            return <button className="project-card" key={project.id} onClick={() => { setActive(project); setActiveTaskId(project.tasks[0]?.id ?? null); }}>
              <div className="project-card-top"><span className="project-icon">{project.name.slice(0, 1).toUpperCase()}</span><span className={`status-label status-${project.status}`}>{label(project.status)}</span></div>
              <h2>{project.name}</h2><p>{project.description || "No description added."}</p>
              <div className="project-card-progress"><span className="progress-track"><span style={{ width: `${percentDone(project)}%` }} /></span><small>{done}/{project.tasks.length} tasks</small></div>
              <div className="project-card-foot"><span>{label(project.template)}</span><span>Open project <b>↗</b></span></div>
            </button>;
          })}
        </div>
      ) : (
        <div className="empty-projects"><div className="empty-art"><span>⌘</span><i /><i /><i /></div><span className="eyebrow">Start with a goal</span><h2>Organize agent work around a project.</h2><p>Create a workspace, generate a task plan, and keep every result attached to it.</p><button className="button-primary" onClick={() => setProjectDialog(true)}>Create your first project</button></div>
      )}

      {projectDialog && (
        <div className="modal-backdrop" onMouseDown={() => setProjectDialog(false)}>
          <form className="modal-card" onSubmit={(event) => void createProject(event)} onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-title"><div><span className="eyebrow">ZCoder workspace</span><h2>New project</h2></div><button type="button" className="icon-button" onClick={() => setProjectDialog(false)} aria-label="Close">×</button></div>
            <label>Project name<input value={projectName} onChange={(event) => setProjectName(event.target.value)} maxLength={200} required autoFocus placeholder="Website redesign" /></label>
            <label>Goal and context<textarea value={projectDescription} onChange={(event) => setProjectDescription(event.target.value)} rows={4} maxLength={20_000} placeholder="What should the agent help you deliver?" /></label>
            <label>Starting template<select value={projectTemplate} onChange={(event) => setProjectTemplate(event.target.value)}>{TEMPLATES.map(([value, name]) => <option value={value} key={value}>{name}</option>)}</select></label>
            <div className="modal-actions"><button type="button" className="button-secondary" onClick={() => setProjectDialog(false)}>Cancel</button><button type="submit" className="button-primary">Create project</button></div>
          </form>
        </div>
      )}
    </section>
  );
}
