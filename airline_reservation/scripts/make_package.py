"""Create a clean source-and-deliverables ZIP for the AeroReserve submission."""

from __future__ import annotations

import stat
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "AeroReserve_Submission.zip"
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".hypothesis",
    "__pycache__",
    "node_modules",
    "build",
    "dist",
    "coverage",
    "htmlcov",
    "target",
    "out",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3"}


def should_include(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if path == OUT or any(
        part in EXCLUDED_DIRS or part.endswith(".egg-info") for part in relative.parts
    ):
        return False
    if path.name == ".env" or path.name == ".coverage" or path.suffix in EXCLUDED_SUFFIXES:
        return False
    return path.is_file()


def main() -> None:
    files = sorted(path for path in ROOT.rglob("*") if should_include(path))
    if not files:
        raise RuntimeError("No project files found")
    with ZipFile(OUT, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(ROOT)
            archive_name = str(Path(ROOT.name) / relative).replace("\\", "/")
            archive.write(path, archive_name)
            mode = stat.S_IMODE(path.stat().st_mode)
            archive.getinfo(archive_name).external_attr = mode << 16
    with ZipFile(OUT, "r") as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise RuntimeError(f"ZIP CRC validation failed for {bad_member}")
    print(f"Wrote {OUT} ({OUT.stat().st_size:,} bytes; {len(files)} files)")


if __name__ == "__main__":
    main()
