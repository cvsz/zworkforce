from zipfile import ZipFile

from scripts.package_release import build_release_archive


def test_release_package_contains_core_artifacts_but_no_runtime_database(tmp_path):
    output = tmp_path / "release.zip"
    build_release_archive(output)

    with ZipFile(output) as archive:
        names = set(archive.namelist())
        content = "\n".join(archive.read(name).decode("utf-8", errors="ignore") for name in names)

    assert {"README.md", "database_schema.sql", "web/index.html", "u_perfect_final_release_report.md"} <= names
    assert ".env" not in names
    assert not any(name.endswith(".db") for name in names)
    assert "EAA" + "xZA" not in content
    assert "rft" + "_tk_" not in content
