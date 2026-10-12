# Character Bible

Fields: stable id, name, role, description, species, personality, voice profile, palette, costume, negative prompt, version, locked flag, approval state.

- Every upsert bumps version and writes `kids_character_versions`.
- `kids.request_character_review` locks the reference; material changes need human approval.
- Original designs only; copyrighted hints (CoComelon, Baby Shark, etc.) fail closed.
