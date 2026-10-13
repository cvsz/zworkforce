# Kids Agent Contracts

Logical agents map to bounded operations (no autonomous permission grant):

- Director: episode plan + budget (`kids.episodes`, `kids.timelines`).
- Research/Script: structured script versions (`kids.scripts`).
- Character: Bible + locking (`kids.characters`, `kids.request_character_review`).
- Storyboard: timestamped scenes (`kids.storyboard`).
- Image/Animation: mock/synthetic assets in slice (`kids.assets`, provider `mock`).
- Voice/Music: track slots in timeline (`voice`, `music`, `sfx`); real TTS/music providers PENDING.
- Editor: timeline tracks video/overlay/voice/music/sfx/captions/branding.
- Quality: deterministic `kids_safety_check` + moderation row; human approval still mandatory.
- Publisher: approval-gated mock YouTube (`kids.publishing`).
- Analytics: synthetic snapshots labeled as such.

Every MCP mutation requires explicit role/scope. Outputs persist in DB, never only in chat memory.
