# ZEAZ Video Factory ORC — opt-in local runtime

This is an **isolated prototype vertical slice**, not a second platform orchestrator and not a provider API integration. The production zWorkforce DAG and durability foundation remains `zworkforce/workflow.py`. Registration into the governed workflow engine, tenant authentication and actual agent inventory require a separate integration PR.

## Safety and boundaries

- No secrets or provider credentials; no AiPASS browser automation, headless login, unofficial API/MCP calls or paid fallback.
- User-local state is SQLite; tenant is a caller-supplied logical partition, **not authenticated multi-tenant isolation**. Do not expose this CLI as a network-facing multi-user service.
- Input files are only locally trusted regular MP4, MOV and WebM. Always obtain necessary rights and consent. Provenance is operator-attested; no automated license checking.
- Scene plan is **timestamp heuristics**, not real boundary detection, pose detection or exact choreography extraction.
- The workflow copies the imported source through FFmpeg transcoding; it does not generate new footage.
- Local installer does not start a service, update a systemd unit, install dependencies, change GitHub CI, or deploy production.

## Install

```bash
bash scripts/install_video_factory_orc.sh --dry-run
bash scripts/install_video_factory_orc.sh
export PATH="$HOME/.local/bin:$PATH"
zeaz-video-factory --help
```

Requires Python >= 3.12 and ffmpeg/ffprobe already installed. Installer is idempotent for the local single-user runtime, preserves local SQLite/artifacts and will not overwrite a non-regular launcher.

## Run on a sample

```bash
zeaz-video-factory create --tenant demo --source ./reference.mp4
zeaz-video-factory status --tenant demo --job <JOB_ID>
# Optional AI material is produced manually using an authorized official UI.
zeaz-video-factory import --tenant demo --job <JOB_ID> --media ./approved-asset.mp4
zeaz-video-factory render --tenant demo --job <JOB_ID>
zeaz-video-factory approve --tenant demo --job <JOB_ID> --actor operator --confirm-rights
```

All state is under `~/.local/share/zeaz-video-factory/` by default. Keep source videos in an access-controlled directory, since this proof of concept stores their resolved paths.

## Release gates

- Run `python3 -m compileall -q zworkforce tests scripts/video_factory_orc.py` and the repository-native test suite.
- Conduct actual input-media, render, crash-recovery, malformed media, tenant boundary, and operator approval tests.
- Require real RBAC/tenant server authorization and governed workflow registration before deployment.
- Implement actual shot detection, typed scene schema, rights validation, secure import scanning, output retention, resource isolation and robust cancellable job queues in later PRs.
- Review by `policedbc`; merge by `cvsz` only with required CI and policy evidence. Do not label this feature production-ready.
