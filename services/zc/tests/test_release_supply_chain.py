"""Release workflow checks for image supply-chain evidence."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def test_release_image_emits_sbom_and_max_provenance() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "provenance: mode=max" in workflow
    assert "sbom: true" in workflow
    assert "steps.build.outputs.digest" in workflow


def test_release_smoke_test_uses_the_published_image() -> None:
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "ghcr.io/${{ github.repository }}:${{ steps.version.outputs.value }}" in workflow
    assert 'python -c "from app.main import app; assert app.title == \'zcoder\'"' in workflow
