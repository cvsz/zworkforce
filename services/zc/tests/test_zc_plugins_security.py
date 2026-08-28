import io
import stat
import zipfile
from pathlib import Path

import pytest

from wire.zc_plugins import _safe_extract_zip


def _archive(entries: dict[str, bytes], *, symlink: str | None = None) -> zipfile.ZipFile:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
        if symlink is not None:
            info = zipfile.ZipInfo(symlink)
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, "../target")
    stream.seek(0)
    return zipfile.ZipFile(stream)


def test_safe_extract_zip_accepts_regular_files(tmp_path: Path) -> None:
    with _archive({"plugin/manifest.json": b"{}"}) as archive:
        _safe_extract_zip(archive, tmp_path)

    assert (tmp_path / "plugin" / "manifest.json").read_bytes() == b"{}"


@pytest.mark.parametrize("name", ["../escape", "/absolute", "dir/../../escape"])
def test_safe_extract_zip_rejects_path_traversal(
    tmp_path: Path,
    name: str,
) -> None:
    with _archive({name: b"unsafe"}) as archive:
        with pytest.raises(ValueError, match="escapes destination"):
            _safe_extract_zip(archive, tmp_path)


def test_safe_extract_zip_rejects_symlinks(tmp_path: Path) -> None:
    with _archive({}, symlink="plugin/link") as archive:
        with pytest.raises(ValueError, match="symlink"):
            _safe_extract_zip(archive, tmp_path)
