# ZEAZDEV — RAG & Evaluator Production Evaluation Implementation

## ROLE

Act as an Autonomous Principal AI Engineer, RAG Architect, Evaluation Engineer, Security Auditor, and CI/CD Engineer.

Target repository: `cvsz/zworkforce`

Mission: Upgrade the existing retrieval and evaluation capabilities with a reproducible, evidence-based Retrieval Evaluation Framework.

**Do not rebuild or replace existing working RAG components. Extend them with the smallest safe changes.**

## PHASE 1 — INVESTIGATION

Read applicable `AGENTS.md` instructions and inspect:

- `zworkforce/rag.py`
- `zworkforce/evaluator.py`
- `zworkforce/evaluation_suite.py`
- Existing database interfaces and tenant-scoped memory tests
- Existing RAG/evaluation tests and fixtures
- Existing GitHub Actions workflows
- `.claude/ecc-tools.json`
- Existing model and provider configuration

Identify existing evaluation functionality before adding any code.

Preserve existing public APIs, security boundaries, database contracts, and deployment behavior.

## PHASE 2 — GOLDEN REFERENCE DATASET

Create versioned, synthetic, non-sensitive reference fixtures under `tests/evaluation/fixtures/`.

Include:

1. Document corpus with stable document identifiers.
2. Retrieval queries with explicit relevant document identifiers.
3. Graded relevance judgments.
4. Expected rankings for deterministic test cases.
5. Negative queries and empty-result cases.
6. Tenant-isolation cases.
7. Cases covering lexical ambiguity, synonyms, conflicting documents, and duplicate content.

Include a documented dataset schema, dataset version, provenance, and assumptions.

Do not fabricate benchmark results.

## PHASE 3 — EVALUATION METRICS

Implement reusable, independently tested metric functions:

- Recall@K
- Precision@K
- MRR@K
- NDCG@K
- Hit Rate@K

Verify calculations against hand-computed examples.

Handle zero relevant documents, empty retrieved rankings, duplicate identifiers, invalid K, and malformed relevance labels explicitly.

Report both per-query results and macro-averaged results.

## PHASE 4 — EXISTING RAG INTEGRATION

Integrate evaluation with existing:

- `LocalSemanticMemory`
- `QdrantSemanticMemory`, where an isolated test environment is available
- `FeatureHashEmbedder`
- Existing embedding interfaces

Use the real retrieval path and existing database contracts.

Do not replace actual retrieval calls with mocked successful results when claiming retrieval quality.

Use deterministic offline fixtures for the default CI gate.

Put external embedding and Qdrant integration tests behind explicit opt-in configuration.

Verify that tenant filters prevent cross-tenant data exposure.

## PHASE 5 — EVALUATOR INTEGRATION

Extend the evaluation reporting layer without breaking existing `evaluate()` contracts or EvaluationRunner behavior.

Produce machine-readable JSON results containing:

- Dataset version
- Repository commit SHA
- Retrieval backend
- Metric definitions
- Per-query metrics
- Aggregate metrics
- Regression comparison
- Evaluation environment
- Test execution timestamp

Introduce versioned baseline comparisons with explicit update procedures.

Do not silently regenerate golden expectations to make tests pass.

## PHASE 6 — TESTING

Implement focused regression coverage for:

- Exact-match retrieval
- Ambiguous and unrelated queries
- Expected ranking order
- Retrieval metric correctness
- Tenant isolation
- Agent-level isolation
- Backend error handling
- Missing or invalid embeddings
- Incorrect relevance judgments
- Stable deterministic evaluation
- Regression against previously approved reference results

Use the repository's existing testing conventions.

## PHASE 7 — CI QUALITY GATE

Integrate with existing GitHub Actions rather than introducing unnecessary duplicate workflows.

Run offline evaluation on pull requests when relevant files change.

Default CI must require no paid providers or external credentials.

Upload evaluation reports as CI artifacts.

Fail the relevant gate when deterministic contracts regress.

Introduce configurable quality thresholds only after obtaining an approved baseline.

Do not weaken existing CI or branch protection.

## PHASE 8 — ECC EVIDENCE

Produce genuine, reproducible evidence for ECC's RAG/Evaluator Comparison category.

Document:

- Fixture paths
- Golden reference cases
- Metric implementations
- Exact test commands
- CI workflow
- Evidence artifact paths
- Known limitations

Do not directly change ECC readiness scores or mark categories complete without matching validation evidence.

## PHASE 9 — VALIDATION

Run all relevant:

- Syntax checks
- Formatting/lint
- Unit tests
- Retrieval regression tests
- Tenant-isolation tests
- Full affected test suite
- Security review
- CI workflow validation

Report actual results and remaining limitations.

## PHASE 10 — GITHUB GOVERNANCE

Create a focused feature branch and Pull Request.

Use English for code, documentation, comments, commit messages, and PR descriptions.

Use Thai for operator-facing reports.

Follow the existing authorized reviewer and merge workflow:

- `policedbc`: independent review, subject to repository policy and genuine reviewer independence.
- `cvsz`: authorized merge after current-head CI and required approvals.

Never bypass branch protection, manufacture independent approval, or merge a failing PR.

## ACCEPTANCE CRITERIA

- Existing RAG functionality remains backward-compatible.
- Versioned golden fixtures are present.
- Retrieval metrics are independently unit tested.
- Offline evaluation exercises the actual LocalSemanticMemory implementation.
- Tenant-isolation regression tests pass.
- CI produces a reproducible evaluation artifact.
- Regression failures return nonzero exit codes.
- ECC evidence refers to actual tests and reports.
- No new paid infrastructure is required for default CI.
- Production readiness is not claimed without environment-specific evidence.

## EXECUTION

Begin immediately.

Inspect the existing implementation, establish baseline evidence, implement the smallest safe changes, run tests, and prepare a reviewable PR.

Do not stop after writing a plan when implementation is authorized and tools are available.

Report actual verified completion, blockers, and remaining tasks.
