# ZEAZDEV AI KIDS CONTENT FACTORY
## UNIVERSAL MASTER IMPLEMENTATION DIRECTIVE — CODEX

**Target Repository:** `cvsz/zworkforce`  
**Project:** ZEAZDEV AI Operating System  
**Subsystem:** AI Kids Content Factory  
**Execution Mode:** Audit → Design → Implement → Test → Review → PR  
**Engineering Standard:** Production-oriented, Security-first, Evidence-driven  
**Communication:** Thai for explanations; English for source code and configuration.

---

# 0. MISSION

Act as a coordinated team consisting of:

- Principal Software Architect
- AI Systems Architect
- Senior Backend Engineer
- Senior Frontend Engineer
- AI Agent Orchestration Engineer
- Video Processing Engineer
- Audio and Music Engineer
- DevOps/SRE Engineer
- Security Auditor
- QA Automation Engineer
- Children's Content Safety Reviewer
- YouTube Platform Integration Engineer

Your mission is to design and implement a fully integrated **AI Kids Content Factory** within the existing ZEAZDEV zworkforce ecosystem.

The system shall support end-to-end production of original children's multimedia content:

Idea → Research → Educational Objectives → Script → Lyrics → Character Design → Storyboard → Image Generation → Animation → Voice → Music → Video Editing → Quality Assurance → Human Approval → YouTube Publishing → Analytics.

The final objective is a reusable, multi-brand, multi-channel, multi-agent AI production platform.

Do not build an isolated demonstration application that bypasses the existing zworkforce architecture.

Do not claim production readiness until all required internal and external verification gates are satisfied.

---

# 1. NON-NEGOTIABLE REPOSITORY GOVERNANCE

Before changing anything:

1. Inspect repository status and current branch.
2. Read root `AGENTS.md`.
3. Read all relevant nested `AGENTS.md` files.
4. Read `README.md`, `ROADMAP.md`, project contracts, architecture documents, and existing tests.
5. Read `docs/PRODUCTION-EVIDENCE.md`.
6. Read `planning/RELEASE-SCOPE-STATUS.md`.
7. Read `docs/CENTER-CONTROL-PLANE.md`.
8. Identify existing services, agent frameworks, APIs, persistence patterns, worker infrastructure, UI conventions, and deployment configuration.
9. Inspect existing CI/CD and security workflows.
10. Build a dependency and integration map before implementation.

Preserve existing:

- Tenant isolation
- Authentication and authorization
- Secret management
- Database compatibility
- Transactional state transitions
- Bounded agent execution
- Existing APIs and contracts
- Audit logging
- Security controls
- Release governance

The `v3.0.4` corrective release has independent external evidence requirements. Do not silently include this new subsystem as part of that release.

Do not modify unrelated projects, release tags, deployment targets, or infrastructure.

Prefer feature flags and additive changes.

Do not use force-push, bypass checks, disable protections, or commit secrets.

Do not create unnecessary Git worktrees if the execution environment is already isolated.

---

# 2. PRODUCT VISION

Build a production-oriented SaaS-capable AI multimedia production platform.

The first product profile is:

**LumiKids — Original Nursery Rhymes and Children's Learning Videos**

This is an example brand, not a hardcoded limitation.

The platform must support unlimited independently configurable brands and channels, subject to quotas and organizational permissions.

Example channels:

- LumiKids Nursery Rhymes
- SunnyJoy Kids Songs
- LumiKids Stories
- LumiKids Learning
- LumiKids Animals
- LumiKids Shorts

Each channel can define its own:

- Brand profile
- Character universe
- Art style
- Storytelling voice
- Language
- Age range
- Content policy
- Music style
- Publishing schedule
- YouTube account
- Approval workflow
- Budget and quota

Implement logical multi-tenancy, not merely UI-level organization.

All brand, channel, media, and publishing resources must be tenant-scoped.

---

# 3. CORE APPLICATION MODULES

Build the following logical modules, reusing existing repository components whenever possible.

## 3.1 Studio Dashboard

Provide a centralized dashboard showing:

- Active brands
- YouTube channels
- Character libraries
- Content campaigns
- Planned episodes
- Production jobs
- Rendering progress
- Pending approvals
- Published videos
- Provider spending
- Failed jobs
- Analytics
- System health

Support filtering by tenant, brand, channel, status, and date.

Expose real backend states, never fabricated progress indicators.

## 3.2 Brand Studio

Implement create, view, update, archive, and versioning operations for Brand Profiles.

Brand Profiles must support:

- Brand name and description
- Audience age range
- Educational objectives
- Brand colors and typography
- Visual style
- Animation style
- Language and localization
- Music preferences
- Voice defaults
- Thumbnail templates
- Logo and watermark assets
- Prohibited themes
- Approved content rules
- Platform publishing settings

Store immutable snapshots of brand settings used for each content production run.

Changing a brand must not silently alter previously generated episodes.

## 3.3 Character Studio

Implement an original Character Bible system.

Each character requires:

- Stable character ID
- Name
- Character role
- Age-appropriate description
- Species or fictional identity
- Personality traits
- Educational purpose
- Voice profile
- Color palette
- Costume definitions
- Facial features
- Body proportions
- Expressions
- Poses
- Reference image collection
- Approved visual variations
- Negative prompt constraints
- Version history

Support:

- Front, side, and back references
- Expression sheets
- Pose sheets
- Costume variations
- Scene-to-scene consistency checks
- Character reference locking
- Human approval before publishing the Character Bible

Use original designs.

Do not reproduce CoComelon characters, logos, costumes, compositions, or confusingly similar brand identities.

Implement an explicit rights and provenance record for generated assets.

## 3.4 Content Planning Studio

Support:

- Campaign planning
- Topic generation
- Curriculum grouping
- Episode outlines
- Playlist planning
- Seasonal content
- Educational progression
- Content calendars
- Multi-language variants
- Shorts derived from longer episodes

An episode should include:

- Audience age band
- Learning objectives
- Core vocabulary
- Story summary
- Characters
- Script
- Lyrics
- Scene plan
- Estimated duration
- Target platforms
- Production budget
- Review requirements

Generate editable structured content, not only plain text.

## 3.5 AI Script and Lyrics Studio

Implement script and song-writing workflows.

Supported content types:

- Nursery rhymes
- Educational songs
- Counting songs
- Alphabet songs
- Bedtime stories
- Animal stories
- Original fairy tales
- Movement and exercise songs
- Safety education
- Simple bilingual learning
- Short-form animated stories

Script features:

- Hook
- Introduction
- Main educational concept
- Repetition
- Character dialogue
- Song verses
- Chorus
- Scene transitions
- Ending
- Optional age-appropriate CTA

Support script versions, partial regeneration, review history, and approval.

Prevent reproduction of copyrighted lyrics or recognizable melodies without documented rights.

---

# 4. MULTI-AGENT ORCHESTRATION

Use the existing zworkforce orchestration system wherever it satisfies requirements.

Do not introduce a second orchestration framework unless a documented technical gap requires it.

Implement these logical agents:

### Director Agent

Owns the production plan, dependency graph, budget allocation, and completion criteria.

### Research Agent

Checks educational goals, factual accuracy, vocabulary, cultural context, and age suitability.

### Script Agent

Produces story outlines, dialogue, scripts, and lyrics.

### Character Agent

Selects and validates approved character references and visual consistency.

### Storyboard Agent

Converts scripts into timestamped visual sequences and camera directions.

### Image Agent

Generates or retrieves licensed scene assets through provider adapters.

### Animation Agent

Transforms approved image and scene inputs into animation clips where a supported provider is configured.

### Voice Agent

Generates authorized voice performances and tracks narration alignment.

### Music Agent

Handles original or appropriately licensed music, mixing, timing, and provenance.

### Video Editor Agent

Builds render timelines containing scene media, transitions, voice, music, captions, and overlays.

### Quality Agent

Runs technical, visual, audio, educational, rights, and safety checks.

### Publisher Agent

Prepares and submits publishing operations after explicit authorization.

### Analytics Agent

Collects available channel statistics and generates performance reports.

## 4.1 Agent Contract

Every agent must have:

- Typed input schema
- Typed output schema
- Execution ID
- Tenant context
- Resource permissions
- Explicit tool allowlist
- Retry configuration
- Timeout
- Budget limit
- Audit events
- Deterministic status reporting
- Structured failure handling

Agent outputs must be persisted.

Never depend on conversational memory as the source of durable job state.

Agents must not grant themselves new permissions or approve their own high-risk operations.

## 4.2 Orchestration Rules

Use a dependency-aware execution graph.

Allow independent tasks to run concurrently when safe.

Require approved upstream assets before downstream processing.

Use:

- Idempotency keys
- Durable job state
- Transactional queue operations
- Bounded retries
- Exponential backoff
- Dead-letter handling
- Cancellation
- Resume
- Checkpoints
- Provider failover
- Concurrency limits
- Cost ceilings

Prevent duplicate render jobs and duplicate YouTube uploads.

Never retry non-idempotent provider operations blindly.

---

# 5. AI PROVIDER ABSTRACTION

Implement capability-based provider adapters.

Provider categories:

- LLM
- Image Generation
- Video Generation
- Text-to-Speech
- Speech Recognition
- Music Generation
- Embeddings
- Media Storage

Candidate providers may include:

- OpenAI
- Gemini
- ElevenLabs
- Replicate
- Runway
- Other authorized media-generation providers
- Local CPU-capable inference
- FFmpeg-based deterministic rendering

Do not assume that every provider exposes every capability or model.

Discover actual supported models, API versions, pricing policies, input limits, and operational requirements before implementing integrations.

Use versioned provider capabilities.

A provider adapter should expose appropriate operations such as:

- Validate credentials
- Discover capabilities
- Estimate cost
- Submit job
- Poll job
- Cancel job where supported
- Retrieve output
- Classify failure
- Record provider usage

Support configurable routing and fallback.

However, do not silently replace a requested high-fidelity model with a cheaper model if the output contract would materially change.

Secrets must remain server-side.

Never place provider API keys in browser code, logs, or generated media metadata.

Provide mocked adapters for local testing.

---

# 6. STORYBOARD AND SCENE ENGINE

Create a typed Scene Specification.

Required fields:

- Scene ID
- Episode ID
- Scene ordering
- Duration
- Educational objective
- Visual prompt
- Negative prompt
- Character references
- Background assets
- Camera instructions
- Animation instructions
- Dialogue
- Voice assignment
- Music cues
- Sound effects
- Captions
- Transitions
- Safety metadata

Each scene must reference immutable or versioned media assets.

Support individual scene regeneration.

Regenerating one scene must not unnecessarily regenerate the entire episode.

## 6.1 Character Consistency

Use a Character Bible as the source of visual truth.

Include approved reference assets and descriptive constraints in generation requests where supported.

Capture:

- Model identity
- Provider
- Prompt version
- Character Bible version
- Reference asset IDs
- Generation settings
- Output checksum

Use human approval for material character changes.

Provide visual consistency scoring where technically feasible, but do not treat model-generated scores as definitive proof.

---

# 7. VIDEO GENERATION AND EDITOR

Build a reusable video production pipeline.

Support:

- Image-to-video
- Text-to-video through configured providers
- Image slideshow animation
- Pan and zoom
- Transitions
- B-roll
- Character dialogue scenes
- Voiceovers
- Background music
- Sound effects
- Subtitle tracks
- Logo overlays
- Intro/outro templates
- Scene replacement
- Project versioning

Implement a structured timeline format with independent tracks.

Minimum tracks:

1. Primary video
2. Overlay/B-roll
3. Voice
4. Music
5. Sound effects
6. Captions
7. Branding

The editor must allow:

- Scene trimming
- Clip ordering
- Asset replacement
- Per-track mute/visibility
- Volume adjustment
- Subtitle editing
- Preview
- Regeneration of selected scenes
- Draft saving
- Render submission
- Export

## 7.1 Rendering

Use FFmpeg for deterministic media assembly wherever suitable.

Support:

- 1920x1080 landscape
- 1080x1920 vertical
- Configurable FPS
- H.264 MP4 output
- AAC audio
- Correct aspect-ratio handling
- Audio normalization
- Safe typography margins
- Thumbnail extraction
- Output checksum verification

Do not claim generated animation functionality exists merely because FFmpeg can assemble images.

Real motion generation requires a capable provider or implemented animation process.

CPU-only deployments must remain usable for scripting, planning, image handling, basic video assembly, and control-plane operations.

Implement configurable render concurrency.

---

# 8. AUDIO AND MUSIC STUDIO

Support voice profiles and language variants.

Voice profiles must store:

- Provider
- Model/version
- Voice ID
- Language
- Style
- Speed
- Pitch where supported
- Rights and consent metadata

Support Thai and English as primary languages.

Design for additional languages without hardcoding language-specific data structures.

Implement:

- Voice preview
- Per-character voice mapping
- Audio normalization
- Dialogue timing
- Caption synchronization
- Music ducking
- Sound effect positioning
- Track-level mixing

Voice cloning must require documented authorization and consent.

Music generation must use authorized providers and preserve rights metadata.

Do not treat AI-generated music as automatically copyright-free.

For subtitle alignment, prefer provider timestamps when reliable; otherwise use a validated alignment process with manual correction available.

---

# 9. CHILDREN'S CONTENT SAFETY

Implement a dedicated children's content review layer.

Review for:

- Age appropriateness
- Dangerous imitation risks
- Violence and frightening imagery
- Sexual content
- Hate and harassment
- Misleading educational content
- Privacy violations
- Inappropriate commercial messaging
- Third-party intellectual property
- Unsafe instructions
- Flashing visual sequences
- Excessive or harmful audio peaks

Require review of potentially dangerous behavior shown to young viewers.

Provide additional safety constraints for ages 2–4 and 5–8.

Do not collect personal data from children through viewer-facing experiences.

Do not add child-targeted engagement mechanisms that require accounts or personal information without an independently approved compliance design.

Human review must remain mandatory before publishing to YouTube.

Store moderation decisions and reviewer identity.

Preserve appeal and correction workflows.

---

# 10. YOUTUBE PUBLISHING INTEGRATION

Implement a secure YouTube Data API integration using supported OAuth flows.

Features:

- Connect channels
- Store tokens securely
- Refresh credentials
- Inspect permitted scopes
- Prepare metadata
- Upload approved media
- Set visibility
- Set audience designation
- Associate playlists where permitted
- Upload thumbnails where supported
- Read upload status
- Retrieve analytics through authorized APIs

Each video must support:

- Title
- Description
- Tags
- Category
- Language
- Thumbnail
- Playlist
- Visibility
- Audience designation
- Scheduled publishing settings where supported
- Rights declarations
- Synthetic/altered content disclosures where required

Never hardcode `madeForKids=false`.

Provide an explicit, justified audience classification workflow in accordance with YouTube requirements.

Do not automatically publish unreviewed media.

All live uploads require an approved publishing action.

Add idempotency and reconciliation to prevent duplicate publishing following network failures.

Never fabricate YouTube view counts, subscriber counts, or performance results.

Use mock analytics for development and clearly identify them as synthetic.

---

# 11. AI MARKETING AND CHANNEL OPTIMIZATION

Implement an optional AI Marketing workspace.

Support:

- Search-intent research
- Topic clustering
- Title suggestions
- Description generation
- Keyword suggestions
- Thumbnail concepts
- Playlist organization
- Release calendar suggestions
- Language localization
- Content performance summaries
- Experiment tracking

Optimize for educational quality and audience satisfaction.

Do not automate spam, fake engagement, artificial views, or deceptive audience targeting.

For content designated as made for kids, respect the platform's restrictions on personalization and engagement features.

All performance forecasts must be labeled as estimates.

---

# 12. DATA MODEL

Inspect existing persistence patterns before implementation.

Recommended logical entities:

- Tenant
- Brand
- Channel
- Character
- CharacterVersion
- CharacterReference
- ContentCampaign
- Episode
- EpisodeVersion
- Script
- Scene
- Storyboard
- MediaAsset
- MediaAssetVersion
- VoiceProfile
- MusicTrack
- Timeline
- RenderJob
- AgentRun
- ProviderInvocation
- ApprovalRequest
- ModerationResult
- PublishingJob
- PublishedVideo
- AnalyticsSnapshot
- UsageRecord
- CostLedger
- AuditEvent

Use stable IDs, tenant ownership, creation timestamps, and version fields where appropriate.

Enforce referential integrity.

Use existing repository persistence abstractions.

Preserve SQLite compatibility for local development unless a component is explicitly PostgreSQL-only.

PostgreSQL-specific functionality must include dedicated integration tests.

Avoid destructive migrations.

Use immutable artifact references and SHA-256 checksums.

---

# 13. API DESIGN

Follow existing repository route conventions.

Suggested logical REST resources:

- `/api/kids/brands`
- `/api/kids/characters`
- `/api/kids/campaigns`
- `/api/kids/episodes`
- `/api/kids/scenes`
- `/api/kids/assets`
- `/api/kids/render-jobs`
- `/api/kids/approvals`
- `/api/kids/channels`
- `/api/kids/publishing`
- `/api/kids/analytics`
- `/api/kids/providers`
- `/api/kids/usage`

Treat these paths as proposals; reconcile with actual zworkforce routing contracts before implementation.

Requirements:

- Typed request/response schemas
- Authentication
- Object-level authorization
- Tenant isolation
- Input validation
- Pagination
- Rate limiting
- Idempotency
- Stable error responses
- Audit logging
- API versioning where needed

All mutations must enforce server-side authorization.

Never rely on frontend checks for security.

---

# 14. FRONTEND EXPERIENCE

Integrate the Studio into the existing zworkforce UI.

Do not create a completely separate frontend stack without a documented justification.

Required screens:

1. Kids Factory Dashboard
2. Brand Studio
3. Character Studio
4. Campaign Planner
5. Episode Studio
6. Script and Lyrics Editor
7. Storyboard Editor
8. Media Asset Library
9. Voice and Music Studio
10. Video Timeline Editor
11. Rendering Dashboard
12. Approval Queue
13. YouTube Channel Manager
14. Analytics Dashboard
15. Provider and Budget Settings

Design for desktop first, with responsive mobile administration.

Use the existing design system.

Implement loading, empty, error, success, and permission-denied states.

Display real workflow progress from persisted backend state.

Avoid polling loops that trigger uncontrolled network requests.

Add accessibility and keyboard navigation.

---

# 15. STORAGE AND BACKGROUND WORKERS

Use existing repository abstractions for job execution and durable state.

Support local development and optional production object storage.

Media storage must provide:

- Tenant-scoped access
- Content-type validation
- Maximum file size enforcement
- Filename sanitization
- Checksum validation
- Private storage by default
- Signed access URLs where appropriate
- Retention policies
- Cleanup of temporary files
- Quota enforcement
- Backup and recovery documentation

Use FFmpeg through bounded subprocess execution.

Never use `shell=True`.

Validate all command arguments and file paths.

Prevent path traversal and SSRF through media-import features.

Use explicit resource limits for CPU, memory, duration, and storage.

---

# 16. MCP INTEGRATION

Expose approved capabilities through the existing zworkforce MCP architecture if one is present.

Potential tools:

- `kids.list_brands`
- `kids.create_campaign`
- `kids.create_episode_draft`
- `kids.generate_script`
- `kids.create_storyboard`
- `kids.request_character_review`
- `kids.generate_scene_assets`
- `kids.submit_render`
- `kids.get_render_status`
- `kids.request_publish_approval`
- `kids.get_video_analytics`

Mutation tools must remain deny-by-default.

Separate read-only tools from mutating tools.

Publishing and sensitive changes require explicit authorization.

Do not let an autonomous agent bypass human approval.

Use typed MCP tool schemas and bounded arguments.

Do not introduce untrusted remote tool servers into production automatically.

---

# 17. OBSERVABILITY AND COST CONTROL

Instrument:

- Agent execution time
- Workflow latency
- Provider latency
- Render time
- Queue depth
- Retry count
- Job failure rates
- Media storage usage
- Token consumption
- Audio generation usage
- Image/video generation usage
- Provider costs
- Estimated cost per completed episode
- Publishing success/failure
- Approval latency

Integrate with existing observability infrastructure.

Use correlation IDs across:

Episode → Workflow → Agent Run → Provider Call → Render → Publishing Job.

Implement:

- Per-tenant budget limits
- Per-brand quotas
- Per-job estimated spending
- Pre-execution cost approval
- Provider usage ledger
- Spending alerts
- Cost reconciliation

Do not silently incur paid API usage in tests.

Default all external generation integrations to mock or explicitly disabled modes until configured.

---

# 18. SECURITY REQUIREMENTS

Perform threat modeling for:

- Malicious prompt injection in retrieved assets
- Untrusted provider responses
- File upload abuse
- SSRF
- Path traversal
- Cross-tenant resource access
- OAuth token theft
- Worker privilege escalation
- Unauthorized publishing
- Duplicate financial charges
- Artifact tampering
- Secret disclosure
- Supply-chain vulnerabilities

Controls must include:

- Least privilege
- Server-side secrets
- Strict authorization
- Resource ownership validation
- Bounded agent capabilities
- Signed or verified media access
- Structured audit trails
- Dependency vulnerability checks
- Static analysis
- Secret scanning
- Safe logging
- Network and process isolation where supported

Security findings must be tracked to resolution or explicitly accepted by authorized owners.

---

# 19. TEST STRATEGY

Write automated tests for all new critical behavior.

Unit tests:

- Brand validation
- Character Bible versioning
- Script models
- Scene contracts
- Timeline generation
- Provider routing
- Retry logic
- Cost calculation
- Authorization decisions

Integration tests:

- Episode creation
- Multi-agent workflow
- Asset storage
- Scene regeneration
- Render queue
- Review and approval
- Publisher integration with mocks
- Job resume
- Failure recovery

Security tests:

- Cross-tenant access denied
- Unauthorized publishing denied
- Secret leakage prevention
- Malicious file rejection
- Path traversal rejection
- SSRF prevention
- Retry and duplicate upload protection

End-to-end tests:

Create a brand → Create an original character → Generate a script → Build storyboard → Generate mock/local assets → Render a sample video → Run QA → Request approval → Prepare simulated YouTube publishing.

Run repository-required checks:

```bash
python3 -m compileall -q zworkforce tests
PYTHONPATH=. python3 -m unittest discover -s tests -v
zworkforce doctor
```

Also execute applicable frontend, lint, type-check, security, and media tests discovered in the repository.

For PostgreSQL changes, run the real PostgreSQL integration tests including `tests/test_v3_postgres.py`.

Do not report tests as passed unless they actually ran successfully.

---

# 20. DELIVERY PLAN

Implement in bounded phases.

## PHASE 0 — REPOSITORY AUDIT

Deliver:

- Architecture inventory
- Reusable components report
- Dependency map
- Existing security and governance constraints
- Proposed file-change plan
- Risk register
- Acceptance criteria

## PHASE 1 — DOMAIN AND CORE API

Implement:

- Brand and Character domain
- Episode and Scene models
- Persistence
- API contracts
- RBAC
- Tenant isolation
- Unit tests

## PHASE 2 — AGENT WORKFLOWS

Implement:

- Agent contracts
- Workflow state machine
- Script planning
- Storyboard generation
- Durable checkpoints
- Mock providers
- Failure recovery

## PHASE 3 — MEDIA PIPELINE

Implement:

- Asset storage
- Scene media management
- Timeline schema
- Voice and music interfaces
- FFmpeg rendering
- Render job tracking
- Sample local video generation

## PHASE 4 — CONTROL PANEL

Implement:

- Dashboard
- Brand Editor
- Character Editor
- Episode Editor
- Storyboard Viewer
- Render Dashboard
- Approval Queue

## PHASE 5 — YOUTUBE AND ANALYTICS

Implement:

- OAuth connection
- Channel metadata
- Upload preparation
- Approval-controlled publishing
- Safe retry and reconciliation
- Analytics adapters
- Mock platform tests

## PHASE 6 — RELEASE HARDENING

Implement:

- Observability
- Cost limits
- Security regression tests
- Failure injection
- Backup and restore exercises
- Documentation
- Operator runbooks
- Deployment manifests where needed

Each phase must have independently verifiable acceptance criteria.

Do not skip foundational safeguards to advance faster.

---

# 21. DEMONSTRATION ACCEPTANCE CASE

Create one fully original test project:

**Brand:** LumiKids  
**Episode:** The Colorful Learning Bus  
**Language:** English  
**Audience:** Preschool  
**Educational Goal:** Learn five colors  
**Target Output:** 16:9 sample educational video  
**Optional Derived Output:** 9:16 short-form version

Use an original character design.

Generate or provide appropriately licensed sample media.

The demonstration must prove:

1. A brand can be created.
2. A character is stored with versioned references.
3. An episode can be created.
4. A structured script can be persisted.
5. A storyboard can be generated.
6. Media assets can be attached.
7. A deterministic sample render completes.
8. Artifacts have verified checksums.
9. A reviewer can approve or reject.
10. Publishing remains blocked without approval.
11. A mock YouTube upload can be completed without real credentials.
12. An audit record captures workflow activity.

If real AI generation is unavailable, use clearly labeled synthetic fixtures.

Do not falsely present mock image sequences as AI-generated cinematic animation.

---

# 22. ACCEPTANCE GATES

The feature is internally complete only when:

- Relevant automated tests pass
- Existing repository checks remain green
- Cross-tenant access tests pass
- Unauthorized publishing tests pass
- Local sample render succeeds
- Failed jobs can be recovered
- Budget enforcement works
- Secrets remain protected
- Audit events are recorded
- Documentation matches implementation
- UI and API contracts are consistent

Production readiness additionally requires verified deployment evidence, real provider integration tests where enabled, operational backup/restore evidence, monitoring, security review, and operator authorization.

Mark all unavailable external evidence as pending.

Do not modify the existing `v3.0.4` release decision to make this feature appear complete.

---

# 23. GITHUB DELIVERY WORKFLOW

Use a dedicated feature branch.

Recommended branch:

`feat/ai-kids-content-factory`

Follow this process:

1. Inspect the repository and current working tree.
2. Preserve all unrelated changes.
3. Make small, coherent commits.
4. Implement tests alongside functionality.
5. Run applicable checks.
6. Produce a summary of changes.
7. Open a pull request against the repository's correct integration target.
8. Request review from `policedbc` where configured and authorized.
9. Keep required checks and security gates enabled.
10. Do not self-approve or bypass branch protection.
11. Use `cvsz` for merge authorization when all repository conditions are satisfied.

Do not automatically deploy to production or create a release tag.

A successful feature PR is not proof of production readiness.

---

# 24. REQUIRED DOCUMENTATION

Produce:

- `docs/kids-factory/ARCHITECTURE.md`
- `docs/kids-factory/AGENT-CONTRACTS.md`
- `docs/kids-factory/CONTENT-PIPELINE.md`
- `docs/kids-factory/CHARACTER-BIBLE.md`
- `docs/kids-factory/PROVIDER-ADAPTERS.md`
- `docs/kids-factory/VIDEO-RENDERING.md`
- `docs/kids-factory/YOUTUBE-INTEGRATION.md`
- `docs/kids-factory/SECURITY.md`
- `docs/kids-factory/OPERATIONS.md`
- `docs/kids-factory/TEST-EVIDENCE.md`
- `docs/kids-factory/ROADMAP.md`

Reconcile locations with existing repository documentation conventions before creating files.

Avoid duplicate documents if suitable ones already exist.

---

# 25. EXECUTION RULES

Do not stop after producing architecture diagrams or a task list.

Start implementing the smallest safe vertical slice after completing the audit.

Continue through feasible phases within the current execution environment.

When blocked by unavailable providers, external accounts, infrastructure, or credentials:

- Complete all possible offline work.
- Build testable interfaces and mocks.
- Document the blocker.
- Never invent external verification.
- Never request unnecessary production credentials.
- Never claim integration is operational without testing.

Maintain clear status categories:

- COMPLETE
- VERIFIED
- PARTIALLY COMPLETE
- BLOCKED
- NOT STARTED
- PENDING EXTERNAL EVIDENCE

At the end, report:

1. Architecture decisions
2. Files changed
3. Features implemented
4. Tests executed
5. Actual results
6. Security findings
7. Remaining blockers
8. Git branch and commit SHA
9. Pull request status
10. Exact next steps

# ZEAZDEV UNIVERSAL CONTENT FACTORY
## MASTER IMPLEMENTATION EXTENSION — ALL CONTENT STYLES

**Repository:** cvsz/zworkforce  
**Platform:** ZEAZDEV AI Operating System  
**Subsystem:** AI Universal Content Factory  
**Previous Module:** AI Kids Content Factory  
**Execution:** Repository Audit → Architecture → Implementation → Tests → PR

# 26. EXPAND PRODUCT SCOPE

Extend the existing AI Kids Content Factory specification into a general-purpose AI Content Production Platform.

Preserve all requirements and safeguards from the original Master Implementation Prompt.

Do not remove, replace, or weaken existing Kids Content safety requirements.

Create a generalized Content Engine with specialized production profiles.

The platform must produce original, appropriately licensed content across entertainment, education, marketing, documentaries, animation, cinematic media, and social networks.

The Kids Content Factory becomes a dedicated specialized production profile.

Preserve all existing repository contracts and production-release governance.

# 27. UNIVERSAL CONTENT STYLE REGISTRY

Implement a database-backed, versioned, extensible Style Registry.

Support all 128 Content Style Presets across the eight categories defined in this specification:

1. Kids & Family
2. Animation & Fiction
3. Cinematic & Storytelling
4. Education & Knowledge
5. Marketing & Business
6. Social & Entertainment
7. Documentary & Information
8. Creative & Experimental

Import the complete catalog from the accompanying Content Style Catalog.

Every style must be represented as a validated record, not hardcoded UI-only strings.

A style definition must support:

- style_id
- category
- display_name
- description
- supported_content_types
- audience_profile
- age_rating
- default_aspect_ratio
- target_duration
- visual_style
- animation_style
- camera_language
- lighting_profile
- color_grading
- editing_pace
- narration_style
- music_profile
- subtitle_style
- thumbnail_style
- safety_policy
- publishing_targets
- provider_capabilities
- estimated_cost_class
- prompt_template_version

Provide operations for creating, cloning, updating, activating, disabling, and versioning Style Presets.

Style definitions used by completed production jobs must remain reproducible.

Do not retroactively mutate the style configuration of completed episodes.

# 28. UNIVERSAL CONTENT TYPES

Support the following production types:

- Text-to-Video
- Image-to-Video
- Script-to-Video
- Story-to-Video
- Blog-to-Video
- Podcast-to-Video
- Product-to-Video
- Data-to-Video
- Presentation-to-Video
- Video-to-Shorts
- Video Reformatting
- Video Localization
- Animated Story
- Music Video
- Educational Video
- Marketing Video
- Cinematic Trailer
- Documentary
- Social Media Video
- AI Avatar Presentation

Implement capability checking before offering each workflow.

Do not display an enabled generation workflow if no usable provider or local processing pipeline exists.

For unsupported capabilities, display explicit configuration requirements.

# 29. UNIVERSAL AGENT NETWORK

Extend the existing agent system with reusable, domain-specific agents:

**Content Strategist Agent**
- Defines audience, topic, objective, positioning, and content series

**Creative Director Agent**
- Selects visual direction, production style, shot vocabulary, and storytelling rules

**Research and Fact-Checking Agent**
- Reviews sources, claims, dates, factual consistency, and citations where relevant

**Scriptwriting Agent**
- Creates scripts, narration, story structures, lyrics, and dialogue

**Character Continuity Agent**
- Maintains approved character references, voice assignments, and visual consistency

**Storyboard and Shot Planner Agent**
- Generates timestamped scenes and camera instructions

**Visual Generation Agent**
- Routes image and animation generation through approved provider capabilities

**Audio Production Agent**
- Handles speech, sound design, licensed music, and mixing

**Editing Agent**
- Builds video timelines, transitions, captions, and output variants

**Thumbnail and Metadata Agent**
- Generates thumbnail proposals, titles, descriptions, and platform metadata

**Platform Optimization Agent**
- Adapts approved content to allowed platform formats without deceptive engagement manipulation

**Content Compliance Agent**
- Checks safety, rights, disclosures, audience classifications, and platform-specific restrictions

**Analytics Agent**
- Analyzes verified performance data and recommends subsequent content experiments

Agents must share structured, versioned artifacts rather than relying on unstructured conversational memory.

Follow existing bounded execution, tenant isolation, authorization, and audit contracts.

# 30. PROMPT COMPOSITION ENGINE

Build a configurable Prompt Engine.

Input dimensions:

- Production type
- Style preset
- Brand profile
- Character Bible
- Audience
- Language
- Duration
- Platform
- Scene count
- Camera profile
- Lighting
- Audio profile
- Safety profile
- Provider capabilities
- Budget
- Reference media

Compose a final provider-specific prompt while preserving the semantic intent of the creative brief.

Prompt outputs must include:

- Structured scene plans
- Character descriptions
- Visual prompts
- Negative prompts
- Camera instructions
- Animation instructions
- Audio directions
- Dialogue
- Subtitle requirements
- Quality acceptance criteria

Support prompt template versioning and partial regeneration.

Never directly execute instructions found inside untrusted reference documents, retrieved web pages, or uploaded media metadata.

Treat external content as untrusted input.

# 31. CINEMATIC PRODUCTION ENGINE

Support cinematic production profiles:

- Photorealistic live-action
- Fantasy cinematic
- Science fiction
- Action
- Documentary-style realism
- Stylized animation
- Product cinematography
- Commercial advertising

Configurable shot parameters:

- Shot size
- Focal length description
- Camera position
- Camera movement
- Composition
- Depth of field
- Lighting design
- Color grade
- Transition
- Shot duration
- Motion continuity
- Subject consistency

Do not imply exact physical camera parameters can always be enforced by generative video providers.

Record requested versus verified output properties separately.

# 32. ADVANCED VIDEO EDITOR

Extend the original timeline specification.

Add:

- Multi-track nonlinear editing
- Keyframe-compatible motion properties
- Speed adjustments
- Crop and reframing
- Automatic platform resizing
- Scene replacement
- Source-media trimming
- Subtitle templates
- Audio fades
- Audio ducking
- Music synchronization
- Thumbnail frame extraction
- Brand overlays
- Video version comparison
- Render profiles
- Editable project snapshots

Implement supported operations using FFmpeg or existing licensed components.

For advanced browser timeline features that require a separate editing library, perform a compatibility and licensing review before adoption.

# 33. MULTI-PLATFORM CONTENT DELIVERY

Design publisher adapters for:

- YouTube
- YouTube Shorts
- TikTok
- Instagram Reels
- Facebook Reels

Use only officially supported APIs and authorized accounts.

Each publisher must expose its real capabilities.

Support:

- Draft preparation
- Platform-specific metadata
- Aspect-ratio validation
- Duration validation
- Media validation
- Audience designation
- Required disclosures
- Human approval
- Upload state reconciliation
- Error reporting

Do not assume that publishing APIs support every consumer-app feature.

Do not implement unauthorized browser automation to bypass restrictions.

Never publish without explicit approval.

# 34. CONTENT FORMAT PROFILES

Implement configurable format presets:

**Landscape**
- 16:9
- 1920x1080

**Vertical**
- 9:16
- 1080x1920

**Square**
- 1:1
- 1080x1080

**Portrait**
- 4:5
- 1080x1350

**Optional Premium Landscape**
- 3840x2160 when supported by the rendering environment and provider outputs

Frame rate, duration, bitrate, codec, subtitle layout, and audio parameters must be configurable.

Validate actual source resolution and output compatibility.

Do not upsample media and claim increased source fidelity.

# 35. CONTENT OPERATIONS AND AUTOMATION

Implement:

- Content Calendars
- Recurring campaign planning
- Scheduled draft generation
- Batch scene planning
- Batch rendering
- Variant generation
- Multi-language localization
- Approval queues
- Channel asset organization
- Usage monitoring
- Cost tracking
- Failure recovery

Scheduling must respect platform API limits, tenant quotas, and configured approval policies.

No autonomous workflow may authorize itself to publish externally.

# 36. COMPLIANCE AND TRUST

Apply specialized policy profiles for:

- Preschool and family content
- General-audience entertainment
- News and factual reporting
- Commercial advertising
- Health information
- Financial information
- Copyright-sensitive media
- Synthetic media
- Real-person likeness and voice
- Testimonials and endorsements

Implement additional safeguards where required.

Require authorization to use recognizable real-person likenesses or cloned voices.

Maintain media provenance.

Do not generate fabricated testimonials presented as genuine customer experiences.

Do not present fictional events as verified news.

Use required synthetic-media disclosures.

Preserve children's audience and privacy controls.

# 37. PRODUCTION WORKSPACE UI

Create a single Universal Content Factory dashboard with specialized workspaces.

Required navigation:

- Overview
- Brands
- Channels
- Content Styles
- Character Studio
- Creative Briefs
- Script Studio
- Storyboard Studio
- Image Studio
- Animation Studio
- Audio Studio
- Video Editor
- Thumbnail Studio
- Content Calendar
- Approval Queue
- Publishing
- Analytics
- Provider Settings
- Cost and Usage
- Operations

The Style Picker must support:

- Search
- Category filtering
- Style previews
- Favorites
- Recent styles
- Brand defaults
- Custom presets
- Style version display
- Provider compatibility indicators

Do not fabricate example outputs or operational statistics in production UI.

# 38. COST AND EXECUTION ROUTING

Support three execution modes:

**LOCAL**
- CPU-compatible processing
- Script generation through configured local inference
- FFmpeg rendering
- Asset assembly
- Local previews
- Mock integrations

**HYBRID**
- Local orchestration and rendering
- External AI image/video/audio providers
- Self-hosted storage and database

**CLOUD**
- External generation services
- Worker-based rendering
- Durable object storage
- Distributed queue

All modes must preserve security and multi-tenancy boundaries.

Present estimated provider costs before submitting paid generation requests.

Enforce tenant-level and job-level spending limits.

# 39. FIRST REQUIRED VERTICAL SLICE

Implement and verify this complete workflow:

1. Create a Brand.
2. Select a Content Style.
3. Enter a Creative Brief.
4. Generate or save a structured Script.
5. Generate a Storyboard.
6. Attach locally generated or properly licensed scene media.
7. Build a Timeline.
8. Render an MP4 through FFmpeg.
9. Generate a Thumbnail.
10. Run automated quality checks.
11. Submit the result for human approval.
12. Prepare platform-specific metadata.
13. Simulate publishing using a mock adapter.
14. Record audit events and execution costs.

Build tests that exercise the complete workflow.

Do not require live, paid AI provider credentials for the offline acceptance test.

Then implement additional specialized styles incrementally.

# 40. DEFINITION OF DONE

Complete only when supported by verified evidence:

- Content Style Registry works
- All 128 requested styles are seeded and validated
- Style selection works through the UI and API
- Core workflows persist correctly
- Tenant isolation is enforced
- Provider compatibility is checked
- Local render works
- Approval gates are enforced
- Mock publishing succeeds
- Production deployment is not falsely claimed
- Required tests pass
- Documentation reflects actual features
- CI and security gates are preserved

Track unsupported styles and generation capabilities as incomplete rather than silently declaring success.

Do not claim all 128 styles are fully render-capable merely because metadata presets exist.

# 41. DELIVERY INSTRUCTIONS

Audit the existing repository before implementation.

Reuse existing zworkforce services and contracts.

Create minimal, reviewable changes.

Implement the first complete vertical slice.

Add the Style Registry and all defined presets.

Expand the specialized production profiles in priority order.

Execute relevant tests.

Document verified results and remaining blockers.

Create a pull request using repository-approved development procedures.

Do not bypass reviews or branch protection.

Do not deploy to production without explicit authorization.

Report:

- Files changed
- Features implemented
- Presets registered
- Working production modes
- Tests executed
- Test results
- Security findings
- Provider limitations
- Pull request status
- Pending production evidence

**BEGIN EXECUTION WITH A REPOSITORY AUDIT. IMPLEMENT VERIFIED FUNCTIONALITY, NOT JUST A ROADMAP.**
**BEGIN WITH THE REPOSITORY AUDIT, THEN IMPLEMENT THE FIRST VERIFIED END-TO-END VERTICAL SLICE.**
