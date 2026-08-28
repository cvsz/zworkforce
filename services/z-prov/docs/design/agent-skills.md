# Local skill package design

Status: versioned local loading and resource validation implemented.

Each skill is a directory named with a portable lowercase identifier and
contains `skill-manifest.json`. Schema version `1` declares the skill semantic
version, description, fixed `SKILL.md` entrypoint, and every package resource
with exact byte size and SHA-256.

`LocalSkillLoader` accepts only a configured root plus a validated skill name.
It never accepts an arbitrary package path. The root and package must be real
directories. Resource paths are normalized portable relative paths; absolute
paths, dot segments, hidden segments, backslashes, encoded traversal,
duplicates, links, devices, and undeclared files are rejected.

Manifest, file, package-total, and resource-count limits are enforced before a
`LoadedSkill` is returned. Every declared resource must be a regular no-follow
file with matching size and hash. `SKILL.md` must be UTF-8 without NUL bytes.
CommonMark inline and reference-style local links must resolve to declared
resources; external HTTP(S) and mail links are recorded text only and are never
fetched.

Loading is strictly data-only. Executable mode bits have no effect and no
resource is imported, sourced, spawned, or evaluated.

Markdown link syntax reference:

- https://spec.commonmark.org/current/
