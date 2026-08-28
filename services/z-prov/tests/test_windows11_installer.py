from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def test_windows_installer_files_exist() -> None:
    ps1 = ROOT / "scripts" / "Install-ZEAZ-Windows11.ps1"
    cmd = ROOT / "scripts" / "Install-ZEAZ-Windows11.cmd"
    assert ps1.exists()
    assert cmd.exists()

def test_windows_ps1_contains_apply_and_dryrun() -> None:
    ps1_content = (ROOT / "scripts" / "Install-ZEAZ-Windows11.ps1").read_text(encoding="utf-8")
    assert "param (" in ps1_content
    assert "[switch]$Apply" in ps1_content
    assert "[switch]$DryRun" in ps1_content
    assert "LOCALAPPDATA" in ps1_content

def test_windows_cmd_launches_ps1() -> None:
    cmd_content = (ROOT / "scripts" / "Install-ZEAZ-Windows11.cmd").read_text(encoding="utf-8")
    assert "Install-ZEAZ-Windows11.ps1" in cmd_content
    assert "%PS_CMD%" in cmd_content
