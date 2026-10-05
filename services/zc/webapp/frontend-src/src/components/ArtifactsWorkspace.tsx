import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ZcApiClient, ZcApiError } from "../api";
import { Markdown } from "./Markdown";
import type { ArtifactRecord, ProjectRecord, ResponseOptions } from "../types";

interface ArtifactsWorkspaceProps {
  api: ZcApiClient;
  models: string[];
  options: ResponseOptions;
  onOpenSettings: () => void;
  initialArtifactId?: string;
  onArtifactOpened: () => void;
}

const ARTIFACT_TYPES: ArtifactRecord["artifact_type"][] = ["code", "document", "config", "test", "schema", "prompt", "data", "other"];

export function ArtifactsWorkspace({ api, models, options, onOpenSettings, initialArtifactId, onArtifactOpened }: ArtifactsWorkspaceProps) {
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [active, setActive] = useState<ArtifactRecord | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [iterating, setIterating] = useState(false);
  const [diffLoading, setDiffLoading] = useState(false);
  const [diff, setDiff] = useState<string | null>(null);
  const [diffVersions, setDiffVersions] = useState<{ from: number; to: number } | null>(null);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<ArtifactRecord["artifact_type"]>("code");
  const [language, setLanguage] = useState("typescript");
  const [projectId, setProjectId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [feedback, setFeedback] = useState("");
  const createSubmitLock = useRef(false);
  const iterateSubmitLock = useRef(false);

  const reportError = (caught: unknown, fallback: string) => {
    if (caught instanceof ZcApiError && caught.status === 401) {
      setError("Connect with an application token to use artifact tools.");
      onOpenSettings();
    } else {
      setError(caught instanceof Error ? caught.message : fallback);
    }
  };

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [nextArtifacts, nextProjects] = await Promise.all([api.listArtifacts(), api.listProjects()]);
      setArtifacts(nextArtifacts);
      setProjects(nextProjects);
      const requested = initialArtifactId ? nextArtifacts.find((item) => item.id === initialArtifactId) : undefined;
      if (requested) {
        setActive(requested);
        setSelectedVersion(requested.current_version);
        onArtifactOpened();
      } else if (active) {
        const current = nextArtifacts.find((item) => item.id === active.id) ?? null;
        setActive(current);
        if (current && selectedVersion === null) setSelectedVersion(current.current_version);
      }
    } catch (caught) {
      reportError(caught, "Unable to load artifacts.");
    } finally {
      setLoading(false);
    }
  }, [active, api]);

  useEffect(() => {
    void load();
  }, []); // Load the artifact index once when this view opens.

  const visible = artifacts.filter((artifact) =>
    `${artifact.name} ${artifact.artifact_type} ${artifact.language}`.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()),
  );

  const createArtifact = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (createSubmitLock.current) return;
    createSubmitLock.current = true;
    setCreating(true);
    setError("");
    try {
      const artifact = await api.createArtifact({
        name: name.trim(),
        artifact_type: kind,
        language: kind === "code" || kind === "config" || kind === "test" ? language.trim() : "",
        prompt: prompt.trim(),
        project_id: projectId || undefined,
        model: options.model,
      });
      setArtifacts((current) => [artifact, ...current]);
      setActive(artifact);
      setSelectedVersion(artifact.current_version);
      setDiff(null);
      setDiffVersions(null);
      setCreateOpen(false);
      setName("");
      setPrompt("");
      setProjectId("");
    } catch (caught) {
      reportError(caught, "Unable to create artifact.");
    } finally {
      createSubmitLock.current = false;
      setCreating(false);
    }
  };

  const iterate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!active || !feedback.trim() || iterateSubmitLock.current) return;
    const source = active.versions.find((version) => version.version === selectedVersion) ?? active.versions[active.versions.length - 1];
    if (!source) return;
    iterateSubmitLock.current = true;
    setIterating(true);
    setDiff(null);
    setDiffVersions(null);
    setError("");
    try {
      const updated = await api.iterateArtifact(active.id, feedback.trim(), options.model, source.version);
      setActive(updated);
      setSelectedVersion(updated.current_version);
      setArtifacts((current) => current.map((item) => item.id === updated.id ? updated : item));
      setFeedback("");
    } catch (caught) {
      reportError(caught, "Unable to revise artifact.");
    } finally {
      iterateSubmitLock.current = false;
      setIterating(false);
    }
  };

  const showDiff = async () => {
    if (!active || active.versions.length < 2) return;
    const selected = active.versions.find((version) => version.version === selectedVersion) ?? active.versions[active.versions.length - 1];
    if (!selected) return;
    const selectedIndex = active.versions.findIndex((version) => version.version === selected.version);
    const isLatest = selectedIndex === active.versions.length - 1;
    const adjacent = active.versions[isLatest ? selectedIndex - 1 : selectedIndex + 1];
    if (!adjacent) return;
    const fromVersion = isLatest ? adjacent.version : selected.version;
    const toVersion = isLatest ? selected.version : adjacent.version;
    setDiffLoading(true);
    setDiff(null);
    setDiffVersions(null);
    setError("");
    try {
      const nextDiff = await api.artifactDiff(active.id, fromVersion, toVersion);
      setDiffVersions({ from: fromVersion, to: toVersion });
      setDiff(nextDiff);
    } catch (caught) {
      reportError(caught, "Unable to load version diff.");
    } finally {
      setDiffLoading(false);
    }
  };

  const download = () => {
    if (!active) return;
    const current = active.versions.find((version) => version.version === selectedVersion) ?? active.versions[active.versions.length - 1];
    if (!current) return;
    const blob = new Blob([current.content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = active.name.replace(/[^\w.-]+/g, "-") || "artifact.txt";
    link.click();
    URL.revokeObjectURL(url);
  };

  const current = active?.versions.find((version) => version.version === selectedVersion) ?? active?.versions[active.versions.length - 1];
  const latestVersion = active?.versions[active.versions.length - 1];
  const linkedProject = active?.project_id ? projects.find((project) => project.id === active.project_id) : undefined;

  return (
    <section className={`artifact-workspace ${active ? "has-active-artifact" : ""}`}>
      <div className="view-heading">
        <div><span className="eyebrow">ZCoder workspace</span><h1>Artifacts</h1><p>Generated outputs with version history and reviewable diffs.</p></div>
        <button className="button-primary" onClick={() => setCreateOpen(true)}>＋ Generate artifact</button>
      </div>
      {error && <div className="inline-error" role="alert"><span>{error}</span><button onClick={() => setError("")} aria-label="Dismiss error">×</button></div>}

      {loading ? <div className="loading-state"><span className="spinner" /> Loading artifacts…</div> : (
        <div className="artifact-layout">
          <aside className="artifact-index">
            <label className="search-field artifact-search"><span aria-hidden="true">⌕</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search artifacts" aria-label="Search artifacts" /></label>
            <div className="artifact-index-label"><span>ALL OUTPUTS</span><span>{visible.length}</span></div>
            <div className="artifact-list">
              {visible.map((artifact) => <button key={artifact.id} className={`artifact-row ${artifact.id === active?.id ? "selected" : ""}`} onClick={() => { setActive(artifact); setSelectedVersion(artifact.current_version); setDiff(null); setDiffVersions(null); }}>
                <span className="file-glyph">{artifact.artifact_type === "code" ? "⌘" : artifact.artifact_type === "document" ? "¶" : "◇"}</span>
                <span className="artifact-row-copy"><strong>{artifact.name}</strong><small>{artifact.language || artifact.artifact_type} · v{artifact.current_version}</small></span>
              </button>)}
              {!visible.length && <p className="empty-sidebar">{search ? "No matching artifacts." : "No artifacts created yet."}</p>}
            </div>
          </aside>

          <main className="artifact-detail">
            {active && current ? (
              <>
                <div className="artifact-detail-header">
                  <div className="artifact-heading-copy"><span className="eyebrow">{linkedProject?.name ?? "Standalone output"}</span><h2>{active.name}</h2><div className="artifact-meta"><span className="template-chip">{active.artifact_type}</span>{active.language && <span>{active.language}</span>}<span>{current.version === latestVersion?.version ? "Latest" : "Viewing"} version {current.version}</span></div></div>
                  <div className="heading-actions"><button className="button-secondary" onClick={() => void showDiff()} disabled={active.versions.length < 2 || diffLoading}>{diffLoading ? <><span className="spinner" /> Loading…</> : "⇄ Compare versions"}</button><button className="icon-button" onClick={download} aria-label="Download current version" title="Download current version">↓</button></div>
                </div>
                <div className="version-strip"><span className="eyebrow">Version history</span>{active.versions.map((version) => <button className={`version-chip ${version.version === current.version ? "current" : ""}`} key={version.version} onClick={() => { setSelectedVersion(version.version); setDiff(null); setDiffVersions(null); }} disabled={diffLoading} title={`Version ${version.version}`}><span>v{version.version}</span><small>{version.checksum.slice(0, 7)}</small></button>)}</div>
                {diff !== null ? <div className="diff-view"><div className="diff-heading"><span>v{diffVersions?.from} <b>→</b> v{diffVersions?.to}</span><button className="quiet-button" onClick={() => { setDiff(null); setDiffVersions(null); }}>Show selected output</button></div><pre>{diff ? diff.split("\n").map((line, index) => <span className={line.startsWith("+") ? "diff-add" : line.startsWith("-") ? "diff-remove" : line.startsWith("@@") ? "diff-hunk" : ""} key={`${index}-${line}`}>{line || " "}{"\n"}</span>) : "No differences between these versions."}</pre></div> : (
                  <div className={`artifact-preview ${active.artifact_type === "document" || active.artifact_type === "prompt" ? "document-preview" : ""}`}>
                    {active.artifact_type === "document" || active.artifact_type === "prompt" ? <div className="markdown-body"><Markdown>{current.content}</Markdown></div> : <pre><code>{current.content}</code></pre>}
                  </div>
                )}
                <form className="iterate-form" onSubmit={(event) => void iterate(event)}>
                  <label htmlFor="artifact-feedback"><span className="eyebrow">Continue with ZCoder</span><span className="sr-only">Revision feedback</span></label>
                  <div className="iterate-input"><textarea id="artifact-feedback" value={feedback} onChange={(event) => setFeedback(event.target.value)} rows={2} maxLength={200_000} placeholder="Describe what to improve in the next version…" /><button className="send-button" type="submit" aria-label="Create revised version" disabled={iterating || !feedback.trim()}>{iterating ? <span className="spinner" /> : "↑"}</button></div>
                  <small>Creates a new saved version. The current output stays available in history.</small>
                </form>
              </>
            ) : (
              <div className="artifact-empty"><div className="empty-art"><span>⌘</span><i /><i /><i /></div><span className="eyebrow">Saved work</span><h2>Keep useful outputs close.</h2><p>Generate a code or document artifact, refine it with an agent, then compare revisions here.</p><button className="button-primary" onClick={() => setCreateOpen(true)}>Generate your first artifact</button></div>
            )}
          </main>
        </div>
      )}

      {createOpen && (
        <div className="modal-backdrop" onMouseDown={() => !creating && setCreateOpen(false)}>
          <form className="modal-card" onSubmit={(event) => void createArtifact(event)} onMouseDown={(event) => event.stopPropagation()}>
            <div className="modal-title"><div><span className="eyebrow">ZCoder workspace</span><h2>Generate an artifact</h2></div><button type="button" className="icon-button" onClick={() => setCreateOpen(false)} aria-label="Close" disabled={creating}>×</button></div>
            {error && <div className="inline-error" role="alert"><span>{error}</span><button type="button" onClick={() => setError("")} aria-label="Dismiss error">×</button></div>}
            <label>Name<input value={name} onChange={(event) => setName(event.target.value)} maxLength={200} required autoFocus placeholder="API contract" /></label>
            <div className="form-pair"><label>Type<select value={kind} onChange={(event) => setKind(event.target.value as ArtifactRecord["artifact_type"])}>{ARTIFACT_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}</select></label>{kind === "code" || kind === "config" || kind === "test" ? <label>Language<input value={language} onChange={(event) => setLanguage(event.target.value)} maxLength={64} placeholder="typescript" /></label> : <label>Project<select value={projectId} onChange={(event) => setProjectId(event.target.value)}><option value="">No project</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>}</div>
            {(kind === "code" || kind === "config" || kind === "test") && <label>Project<select value={projectId} onChange={(event) => setProjectId(event.target.value)}><option value="">No project</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>}
            <label>What should ZCoder create?<textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={5} maxLength={200_000} required placeholder="Describe the artifact, its requirements, and any constraints…" /></label>
            {!models.length && <p className="field-hint">No model selected; the ZC API will use its configured default.</p>}
            <div className="modal-actions"><button type="button" className="button-secondary" onClick={() => setCreateOpen(false)} disabled={creating}>Cancel</button><button type="submit" className="button-primary" disabled={creating}>{creating ? <><span className="spinner" /> Generating…</> : "Generate artifact"}</button></div>
          </form>
        </div>
      )}
    </section>
  );
}
