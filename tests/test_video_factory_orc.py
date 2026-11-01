"""Regression coverage for the opt-in local Video Factory ORC runtime (PR #288)."""
import importlib.util
import io
import json
import shutil
import subprocess
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Check for FFmpeg availability
HAS_FFMPEG = shutil.which("ffmpeg") is not None


def load_orc():
    spec = importlib.util.spec_from_file_location(
        "video_factory_orc", ROOT / "scripts" / "video_factory_orc.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


orc = load_orc()


def make_video(path: Path, seconds: int = 1) -> Path:
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size=64x64:rate=10",
            "-pix_fmt", "yuv420p", str(path),
        ],
        check=True,
    )
    return path


class VideoFactoryOrcTests(unittest.TestCase):
    def test_digest_is_stable_sha256(self):
        target = ROOT / "README.md"
        first = orc.digest(target)
        self.assertEqual(len(first), 64)
        self.assertEqual(first, orc.digest(target))

    def test_transition_rejects_wrong_stage(self):
        with self.assertRaises(orc.PipelineError):
            orc.transition({"stage": "CREATED"}, "MEDIA_READY", "RENDERED")

    def test_create_rejects_bad_tenant_before_probe(self):
        store = orc.Store(Path(self._tmp() / "jobs.sqlite"))
        try:
            with self.assertRaises(orc.PipelineError):
                orc.new_job(
                    "bad tenant!",
                    Path("/nonexistent.mp4"),
                    Path(self._tmp()),
                    store,
                )
        finally:
            store.close()

    def test_probe_rejects_unsupported_suffix(self):
        with self.assertRaises(orc.PipelineError):
            orc.probe(Path(__file__))

    def test_store_round_trip_and_tenant_isolation(self):
        base = Path(self._tmp())
        store = orc.Store(base / "jobs.sqlite")
        try:
            job = {"id": "job-1", "tenant": "t1", "stage": "CREATED"}
            store.save(job)
            self.assertEqual(store.load("t1", "job-1")["id"], "job-1")
            with self.assertRaises(orc.PipelineError):
                store.load("t2", "job-1")
        finally:
            store.close()

    def test_create_import_guards_and_cli_rights_gate(self):
        if not HAS_FFMPEG:
            self.skipTest("FFmpeg not available; skipping video factory ORC test")
        base = Path(self._tmp())
        db = base / "jobs.sqlite"
        out = base / "artifacts"
        source = make_video(base / "source.mp4")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = orc.main([
                "--db", str(db), "--output", str(out),
                "create", "--tenant", "t1", "--source", str(source),
            ])
        self.assertEqual(rc, 0)
        job = json.loads(buf.getvalue())
        self.assertEqual(job["stage"], "AWAITING_MANUAL_IMPORT")
        self.assertTrue(job["scene_plan"])
        self.assertIn("UNVERIFIED", job["scene_plan"][0]["description"])

        # Approve without --confirm-rights must fail closed.
        rc = orc.main([
            "--db", str(db), "--output", str(out),
            "approve", "--tenant", "t1", "--job", job["id"],
            "--actor", "operator-1",
        ])
        self.assertEqual(rc, 2)

        # Import while awaiting media works; a second import must fail.
        store = orc.Store(db)
        try:
            loaded = store.load("t1", job["id"])
            orc.import_asset(loaded, source, out, store)
            self.assertEqual(loaded["stage"], "MEDIA_READY")
            with self.assertRaises(orc.PipelineError):
                orc.import_asset(loaded, source, out, store)
        finally:
            store.close()

    def _tmp(self):
        tmp = Path(__file__).resolve().parent / ".tmp-orc"
        tmp.mkdir(exist_ok=True)
        sub = tmp / f"case-{id(self):x}"
        sub.mkdir(exist_ok=True)
        self.addCleanup(
            lambda: subprocess.run(["rm", "-rf", str(sub)], check=False)
        )
        return sub


if __name__ == "__main__":
    unittest.main()
