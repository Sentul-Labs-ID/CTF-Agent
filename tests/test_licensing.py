import tomllib
from pathlib import Path


def test_dual_license_files_and_package_metadata():
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    metadata = project["project"]

    assert metadata["license"] == "LicenseRef-Sentul-CDE-1.0 AND MIT"
    assert metadata["license-files"] == ["LICENSE", "NOTICE.md", "LICENSES/*"]
    assert "Required Sentul attribution" in (root / "LICENSE").read_text(encoding="utf-8")
    assert "Copyright (c) 2026 Veria Labs, Inc." in (
        root / "LICENSES" / "MIT-Veria-Labs.txt"
    ).read_text(encoding="utf-8")
    assert "use, copy, modify, merge, publish, distribute" in (
        root / "LICENSES" / "SENTUL-CDE-1.0.txt"
    ).read_text(encoding="utf-8")
