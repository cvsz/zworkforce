from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
WINDOWS_APP = ROOT / "packages" / "zarvis" / "apps" / "zarvis-windows"
ROOT_WINDOWS_APP = ROOT / "apps" / "zarvis-windows"
ZARVIS_WORKFLOW = ROOT / ".github" / "workflows" / "zarvis.yml"


class ZarvisWindowsTargetingTests(unittest.TestCase):
    def test_linux_restore_is_enabled_for_all_windows_projects(self):
        for app_dir in (WINDOWS_APP, ROOT_WINDOWS_APP):
            props = app_dir / "Directory.Build.props"
            self.assertTrue(props.is_file(), f"{app_dir} must define shared build properties")
            root = ET.parse(props).getroot()
            values = [
                element.text.strip().lower()
                for element in root.iter("EnableWindowsTargeting")
                if element.text
            ]
            self.assertIn("true", values)

    def test_linux_ci_restores_source_and_test_projects(self):
        workflow = ZARVIS_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("zarvis-windows-linux-restore:", workflow)
        self.assertIn("dotnet restore src/ZARVIS.Windows/ZARVIS.Windows.csproj", workflow)
        self.assertIn("dotnet restore tests/ZARVIS.Windows.Tests/ZARVIS.Windows.Tests.csproj", workflow)


if __name__ == "__main__":
    unittest.main()
