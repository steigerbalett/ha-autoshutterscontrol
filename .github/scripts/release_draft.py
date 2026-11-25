"""Create or update the draft release for the version in manifest.json.

Used by .github/workflows/release-draft.yml. Needs the gh CLI with GH_TOKEN, REPO and TARGET set.
The draft gets autoshutterscontrol.zip (installed by HACS/Marketplace, counted as download).
A release that is already published is never touched.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "custom_components" / "autoshutterscontrol" / "manifest.json"
CHANGELOG = ROOT / "CHANGELOG.md"
ZIP_NAME = "autoshutterscontrol.zip"


def version() -> str:
    """Return the version from manifest.json."""
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]


def notes(ver: str, text: str) -> str:
    """Return the CHANGELOG section of a version, without its heading."""
    lines: list[str] = []
    found = False
    for line in text.splitlines():
        if line.startswith("## "):
            if found:
                break
            found = line[3:].strip() == ver
            continue
        if found:
            lines.append(line)
    return "\n".join(lines).strip()


def prerelease(ver: str) -> bool:
    """Tell whether a version is a pre-release: 0.x, beta, alpha or release candidate."""
    return ver.startswith("0.") or re.search(r"(a|b|rc)\d+$", ver) is not None


def build_zip(path: Path) -> None:
    """Zip the integration (its files at the top level, as HACS expects)."""
    component = MANIFEST.parent
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(component.rglob("*")):
            if file.is_file() and "__pycache__" not in file.parts:
                zf.write(file, file.relative_to(component).as_posix())


def gh(*args: str, data: dict | None = None) -> str:
    """Call the GitHub API with the gh CLI."""
    cmd = ["gh", "api", *args]
    if data is not None:
        cmd += ["--input", "-"]
    result = subprocess.run(
        cmd,
        input=json.dumps(data) if data is not None else None,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def main() -> int:
    """Create or update the draft."""
    repo = os.environ["REPO"]
    target = os.environ["TARGET"]
    ver = version()
    tag = f"v{ver}"
    body = notes(ver, CHANGELOG.read_text(encoding="utf-8"))
    if not body:
        print(f"::warning::CHANGELOG.md has no section '## {ver}'")
        body = f"Version {ver}"

    releases = json.loads(gh("--paginate", "--slurp", f"repos/{repo}/releases"))
    same = [r for page in releases for r in page if r["tag_name"] == tag]
    if any(not r["draft"] for r in same):
        print(f"{tag} is already published, nothing to do.")
        return 0

    data = {
        "tag_name": tag,
        "target_commitish": target,
        "name": tag,
        "body": body,
        "draft": True,
        "prerelease": prerelease(ver),
    }
    if same:
        gh("-X", "PATCH", f"repos/{repo}/releases/{same[0]['id']}", data=data)
        print(f"Updated the draft {tag}.")
    else:
        gh("-X", "POST", f"repos/{repo}/releases", data=data)
        print(f"Created the draft {tag}.")

    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / ZIP_NAME
        build_zip(archive)
        subprocess.run(
            ["gh", "release", "upload", tag, str(archive), "--clobber", "-R", repo], check=True
        )
    print(f"Uploaded {ZIP_NAME}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
