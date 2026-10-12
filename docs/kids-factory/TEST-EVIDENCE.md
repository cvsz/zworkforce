# Kids Factory Test Evidence

Run: `PYTHONPATH=. python3 -m unittest discover -s tests -p "test_kids_factory.py" -v`.

Covers: brand/character/episode/scene validation, copyright block, secret guard, safety block/pass, storyboard determinism, YouTube metadata + mock idempotency, brand/character versioning, tenant isolation, episode/render/publishing idempotency, per-scene regen isolation, approval-gated publishing (blocked then published), audit capture, overview liveness, cross-tenant 404, API end-to-end demo (LumiKids Colorful Learning Bus).

Full required checks: `python3 -m compileall -q zworkforce tests`, `PYTHONPATH=. python3 -m unittest discover -s tests -v`, `zworkforce doctor`.
External gates (real providers, YouTube OAuth, S3/Qdrant, OTLP, signing): PENDING EXTERNAL EVIDENCE.
