# Kids Content Pipeline

`Brand -> Character (versioned) -> Episode -> Script (versioned) -> Storyboard (per-scene regen) -> Assets -> Timeline -> Render -> QA -> Approval -> Publishing (mock) -> Analytics (synthetic)`.

- Scene regen is per-scene (`POST .../scenes` with scene id); episode unaffected except that scene.
- Timeline versions are immutable with SHA checksum.
- Render is deterministic FFmpeg sample, labeled synthetic; real motion providers PENDING.
- Publishing is blocked until `kids.approvals/{id}/approve` sets state approved.
