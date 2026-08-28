import subprocess
import os

def test_script_execution():
    script_path = os.path.join("scripts", "zai-config-gen.py")
    result = subprocess.run(["python3", script_path, "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()
