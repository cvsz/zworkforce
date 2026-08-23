"""Build a deterministic, secret-free source release archive."""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parent.parent
ALLOWED_PATHS = (
    "app",
    "web",
    "assets",
    "tests",
    "docs",
    ".github",
    "scripts",
    "README.md",
    "USER-MANUAL.md",
    "ADMIN-MANUAL.md",
    "DEV-MANUAL.md",
    "PROJECT-DOCUMENTATION.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "CHANGELOG.md",
    "database_schema.sql",
    "requirements.txt",
    "requirements-dev.txt",
    ".env.example",
    "export-manifest.json",
    "u_perfect_final_release_report.md",
)
EXCLUDED_NAMES = {"__pycache__", ".pytest_cache", ".venv", ".env", "uperfect.db"}


def iter_allowed_files() -> list[Path]:
    files: list[Path] = []
    for entry in ALLOWED_PATHS:
        path = ROOT / entry
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(item for item in path.rglob("*") if item.is_file())
    return sorted(
        path for path in files
        if not any(part in EXCLUDED_NAMES for part in path.relative_to(ROOT).parts)
        and path.name not in {"rewrite-uperfect.md"}
    )


def build_release_archive(output: Path) -> Path:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in iter_allowed_files():
            relative = path.relative_to(ROOT).as_posix()
            info = ZipInfo(relative, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = build_release_archive(args.output)
    print(f"created {output}")
    print(f"files {len(iter_allowed_files())}")


if __name__ == "__main__":
    main()
