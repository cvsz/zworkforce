# v1.28.0 — Files API audit and implementation

**Scope:** `zc_files.py` and the Files-API integration point in
`zc_code_exec.py`, re-audited end to end against a live fetch of
`platform.zc.com/docs/en/build-with-zc/files` and
`platform.zc.com/docs/en/agents-and-tools/tool-use/code-execution-tool`
(fetched July 13, 2026), not against cached notes from prior cycles.

## Finding 1 — Files fed to the code execution tool used the wrong block type (🔴 P0)

**What it is:** `zc_code_exec.py`'s `execute()` attached every
`file_ids` entry to the sandbox using a `document` block:
```python
content.append({"type": "document", "source": {"type": "file", "file_id": fid}})
```
The docs' File type → Content block table is explicit that `container_upload`
is the block type for anything meant to go *into the sandbox's filesystem*
for Python/Bash to open (datasets, CSVs, spreadsheets, images to process
programmatically) — `document` is for PDFs/text zAICoder reads directly in
the conversation turn. The code execution tool's own docs show the intended
shape:
```python
{"type": "container_upload", "file_id": file_object.id}
```

**Why it was a gap:** `zc_code_exec.py` is wire's only call site that
attaches files to a code-execution request, and it predates this project's
adoption of the Files API in `zc_files.py`; nothing in the two modules'
overlap was re-checked when `container_upload` was documented. A grep for
`container_upload` across the tree matched zero call sites before this
cycle.

**Impact:** every `--code-exec` (or programmatic `execute(file_ids=...)`)
call that attached a file was not actually placing that file on the
sandbox's disk. zAICoder could only work from whatever it inferred about the
file from the `document` block's own (limited, non-code-execution) reading
of it — a silent correctness bug for exactly the workflow (analyze a
CSV/Excel file with real code) this file's own module docstring advertises
(`"Create files (Excel, PDFs, charts) returned as file_id"`).

**Fix:** switched to `{"type": "container_upload", "file_id": fid}`.

**Priority: 🔴 P0.** Believed-working code silently doing the wrong thing
outranks any of the unbuilt-feature findings below, same reasoning as prior
cycles' P0 calls.

## Finding 2 — No pagination on `list_files()` (🟠 P1)

**What it is:** `List Files` is a paginated endpoint (`limit`, default and
max 20 per docs example — up to 100 accepted, `before_id`/`after_id` for
adjacent pages, response includes `has_more`/`first_id`/`last_id`).
`zc_files.py`'s `list_files()` only ever requested a single page via
`limit` and returned `data.get("data", [])`, silently truncating any
account with more files than the page size — there was no way to see file
21 onward.

**Fix:** `list_files()` now returns the full paginated envelope
(`data`/`has_more`/`first_id`/`last_id`) and accepts `before_id`/`after_id`.
Added `list_files_all(max_items=None)` to auto-paginate, matching the docs'
description of SDK auto-pagination helpers and this project's own
`--max-items`-bounded CLI convention (already used elsewhere in the CLI).
`cmd_file_list()` now calls this instead of assuming a flat list.

**Priority: 🟠 P1** — real capability gap (files silently invisible past
the first page), not a regression.

## Finding 3 — No client-side filename/size validation before upload (🟠 P1)

**What it is:** The docs list precise, deterministic 400/413 rejection
rules: filenames must be 1-255 characters and exclude
`< > : " | ? * \ /` and Unicode control characters 0-31; files over 500 MB
are rejected. None of this was checked client-side — `upload()` read the
full file into memory and made a network round trip before finding out
from a 400/413 response that the upload was never going to succeed.

**Fix:** added `_validate_filename()` and a size check in `upload()` that
fail fast with the same message shape the API would have returned,
before reading the file into memory or opening a connection.

**Priority: 🟠 P1** — not a correctness bug (the API's own errors were
already surfaced via `AICoderError`), but wasted I/O and worse UX for the
common case of a garbage path or an oversized file.

## Finding 4 — `download()` always round-tripped instead of failing fast on undownloadable files (🟡 P2)

**What it is:** `downloadable` is `false` for every file *you* upload —
only Skills- or code-execution-created files are downloadable. Since
wire's `--file-download` command has no other purpose than fetching
your own uploads back, the *only* files a user would ever pass to it are
categorically un-downloadable, and the old code always made the network
call anyway, surfacing whatever raw error string the API happened to
return.

**Fix:** `download()` now calls `get_file()` first and raises a clear,
specific message when `downloadable` is `false`, before attempting the
content fetch.

**Priority: 🟡 P2** — cosmetic/UX, not a capability gap; the underlying
behavior (uploads can't be downloaded) was already correctly enforced
server-side.

## Finding 5 — No `container_upload` path in `ask_about_file()` (🟠 P1)

**What it is:** `FilesAPI.ask_about_file()` only ever built `image` or
`document` blocks. There was no way to ask a question about a file that
needs the code execution tool (CSV/XLSX analysis, chart generation) through
this method — `zc_code_exec.py` is a separate module with its own
(buggy, see Finding 1) path, so wire had two disconnected code paths for
"do something with an uploaded file" instead of one that covers the whole
File type → Content block table.

**Fix:** added `use_code_execution: bool = False` to `ask_about_file()`. When
set, it sends a `container_upload` block plus the `code_execution_20250825`
tool, matching the docs' worked example for analyzing an uploaded CSV.

**Priority: 🟠 P1.**

## Non-gaps checked this cycle

- **`purpose` param on upload** — a third-party gateway's SDK docs mention
  `purpose: Literal["batch", "user_data"]`. The current official ZaiCoder
  upload example and response schema (`id`, `type`, `filename`, `mime_type`,
  `size_bytes`, `created_at`, `downloadable`) have no `purpose` field at
  all. Not implementing this — it doesn't match the primary docs.
- **Workspace-scoping / cross-key visibility** — docs confirm files are
  scoped to the workspace of the API key that uploaded them and any key in
  that workspace can reference them. No client-side code path is affected;
  this is a server-side property, not something `zc_files.py` needs to
  model.
- **ZDR eligibility** — the Files API is explicitly *not* ZDR-eligible.
  Nothing in wire claims otherwise; no change needed.
- **Bedrock / Vertex AI** — Files API isn't available on either. wire
  doesn't target those platforms for this module; no change needed.

## Methodology note

Confirmed via a live fetch of `platform.zc.com/docs/en/build-with-zc/files`
and `platform.zc.com/docs/en/agents-and-tools/tool-use/code-execution-tool`
(not cached from a previous cycle), then grepping the source tree for
`container_upload`, `"type": "document"`, and `list_files(` to find every
call site touched by the File type → Content block table, rather than
trusting either module's docstrings. Finding 1 is filed as 🔴 P0 ahead of
the 🟠 P1 findings for the same reason prior cycles have used: it's code
that was silently doing the wrong thing, not code that was never written.
