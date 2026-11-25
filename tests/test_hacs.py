"""Requirements of HACS/Marketplace default and of hassfest, checked offline.

The GitHub workflow "Validate" runs the real HACS action and hassfest. These tests
catch the same problems before a push.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import string
import struct
import sys

from awesomeversion import AwesomeVersion
import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "custom_components" / "autoshutterscontrol"
REPO = "https://github.com/steigerbalett/ha-autoshutterscontrol"

MANIFEST = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
HACS = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))

# hassfest (script/hassfest/manifest.py, translations.py)
IOT_CLASSES = {
    "assumed_state",
    "calculated",
    "cloud_polling",
    "cloud_push",
    "local_polling",
    "local_push",
}
INTEGRATION_TYPES = {"device", "entity", "hardware", "helper", "hub", "service", "system"}
MANIFEST_KEYS = {
    "after_dependencies",
    "bluetooth",
    "codeowners",
    "config_flow",
    "dependencies",
    "dhcp",
    "documentation",
    "domain",
    "homekit",
    "integration_type",
    "iot_class",
    "issue_tracker",
    "loggers",
    "mqtt",
    "name",
    "quality_scale",
    "requirements",
    "single_config_entry",
    "ssdp",
    "usb",
    "version",
    "zeroconf",
}
RE_TRANSLATION_KEY = re.compile(r"^(?!.+[_-]{2})(?![_-])[a-z0-9-_]+(?<![_-])$")
RE_COMBINED_REFERENCE = re.compile(r"(.+\[%)|(%\].+)")
RE_PLACEHOLDER_IN_SINGLE_QUOTES = re.compile(r"'{\w+}'")
RE_URL = re.compile(
    r"(((ftp|ftps|scp|http|https|mqtt|mqtts|socket|socks5):\/\/|www\.)"
    r"[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(\/.*)?)",
    re.IGNORECASE,
)
RE_HTML = re.compile(r"<[a-z].*?>", re.IGNORECASE)

# HACS (custom_components/hacs/utils/validate.py)
HACS_KEYS = {
    "content_in_root",
    "country",
    "filename",
    "hacs",
    "hide_default_branch",
    "homeassistant",
    "persistent_directory",
    "render_readme",
    "zip_release",
    "name",
}


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    return struct.unpack(">II", data[16:24])


# --- manifest.json (hassfest + HACS) -----------------------------------------


def test_manifest_required_keys() -> None:
    assert MANIFEST["domain"] == COMPONENT.name
    assert MANIFEST["name"]
    assert MANIFEST["codeowners"]
    assert all(re.fullmatch(r"@[\w-]+(/[\w-]+)?", owner) for owner in MANIFEST["codeowners"])
    assert MANIFEST["documentation"].startswith(REPO)
    assert MANIFEST["issue_tracker"] == f"{REPO}/issues"
    assert MANIFEST["iot_class"] in IOT_CLASSES
    assert MANIFEST["integration_type"] in INTEGRATION_TYPES
    assert MANIFEST["config_flow"] is True
    assert set(MANIFEST) <= MANIFEST_KEYS, set(MANIFEST) - MANIFEST_KEYS


def test_manifest_sorted() -> None:
    """hassfest: domain, name, then alphabetical order."""
    keys = list(MANIFEST)
    assert keys[:2] == ["domain", "name"]
    assert keys[2:] == sorted(keys[2:])


def test_manifest_version() -> None:
    version = AwesomeVersion(MANIFEST["version"])
    assert version.valid
    # The release draft takes its notes from this section
    first = re.search(r"^## (\S+)", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
    assert first and first.group(1) == MANIFEST["version"]


def test_no_requirements_from_outside() -> None:
    """Pure Python: nothing to install, nothing that can fail at setup."""
    assert MANIFEST["requirements"] == []
    assert MANIFEST["dependencies"] == []


# --- hacs.json ------------------------------------------------------------------


def test_hacs_json() -> None:
    assert set(HACS) <= HACS_KEYS, set(HACS) - HACS_KEYS
    assert HACS["name"] == MANIFEST["name"]
    assert AwesomeVersion(HACS["homeassistant"]).valid
    if HACS.get("zip_release"):
        assert HACS.get("filename"), "zip_release needs filename"
        script = (ROOT / ".github" / "scripts" / "release_draft.py").read_text(encoding="utf-8")
        assert f'ZIP_NAME = "{HACS["filename"]}"' in script


def test_minimum_home_assistant_is_tested() -> None:
    """The version in hacs.json is not newer than the one the tests run with."""
    from homeassistant.const import __version__

    assert AwesomeVersion(HACS["homeassistant"]) <= AwesomeVersion(__version__)


# --- repository files -----------------------------------------------------------


@pytest.mark.parametrize("name", ["README.md", "LICENSE", "CHANGELOG.md", "hacs.json"])
def test_repository_files(name: str) -> None:
    assert (ROOT / name).is_file()


def test_one_integration_only() -> None:
    """HACS: exactly one integration in custom_components."""
    dirs = [p.name for p in (ROOT / "custom_components").iterdir() if p.is_dir()]
    assert [d for d in dirs if d != "__pycache__"] == [COMPONENT.name]


def test_readme_links_exist() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for link in re.findall(r"\]\((?!https?://|#)([^)#]+)", readme):
        assert (ROOT / link).exists(), link


# --- brand (HACS check "brands", Home Assistant 2026.11 brand folder) ------------


@pytest.mark.parametrize(
    ("name", "size"),
    [
        ("icon.png", 256),
        ("icon@2x.png", 512),
        ("dark_icon.png", 256),
        ("dark_icon@2x.png", 512),
    ],
)
def test_brand_icons(name: str, size: int) -> None:
    path = COMPONENT / "brand" / name
    if name.startswith("dark_") and not path.exists():
        pytest.skip("optional")
    assert _png_size(path) == (size, size)


def test_brand_has_only_known_files() -> None:
    known = {
        "icon.png",
        "icon@2x.png",
        "dark_icon.png",
        "dark_icon@2x.png",
        "logo.png",
        "logo@2x.png",
        "dark_logo.png",
        "dark_logo@2x.png",
    }
    assert {p.name for p in (COMPONENT / "brand").iterdir()} <= known


# --- translations (hassfest translations.py) ------------------------------------


def _strings(data, path=()):
    for key, value in data.items():
        if isinstance(value, dict):
            yield from _strings(value, (*path, key))
        else:
            yield (*path, key), value


def _translation_keys(data) -> list[str]:
    """Keys hassfest checks with its translation key validator."""
    keys: list[str] = []
    for name, sel in data.get("selector", {}).items():
        keys.append(name)
        keys.extend(sel.get("options", {}))
    for platform in data.get("entity", {}).values():
        for key, entity in platform.items():
            keys.append(key)
            keys.extend(entity.get("state", {}))
            for attr in entity.get("state_attributes", {}).values():
                keys.extend(attr.get("state", {}))
    keys.extend(data.get("issues", {}))
    keys.extend(data.get("exceptions", {}))
    keys.extend(data.get("services", {}))
    return keys


FILES = [COMPONENT / "strings.json", *sorted((COMPONENT / "translations").glob("*.json"))]


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_translation_keys(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    bad = [k for k in _translation_keys(data) if not RE_TRANSLATION_KEY.match(k)]
    assert not bad


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_translation_values(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    problems = []
    for where, value in _strings(data):
        name = ".".join(where)
        if not isinstance(value, str) or not value:
            problems.append(f"{name}: empty")
            continue
        if RE_HTML.search(value):
            problems.append(f"{name}: HTML")
        if RE_PLACEHOLDER_IN_SINGLE_QUOTES.search(value):
            problems.append(f"{name}: placeholder in single quotes")
        if RE_COMBINED_REFERENCE.search(value):
            problems.append(f"{name}: combined reference")
        if value != value.strip():
            problems.append(f"{name}: leading or trailing spaces")
        if RE_URL.search(value):
            problems.append(f"{name}: URL")
        for _, field, _, _ in string.Formatter().parse(value):
            if field and not field.isidentifier():
                problems.append(f"{name}: placeholder {field}")
    assert not problems, "\n".join(problems)


def test_no_title_in_config() -> None:
    data = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
    assert "title" not in data.get("config", {})


# --- services (hassfest services.py, custom integration) -------------------------


def test_services_yaml() -> None:
    services = yaml.safe_load((COMPONENT / "services.yaml").read_text(encoding="utf-8"))
    strings = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
    for name, service in services.items():
        assert RE_TRANSLATION_KEY.match(name)
        assert strings["services"][name].get("name"), name
        assert strings["services"][name].get("description"), name
        for field in (service or {}).get("fields", {}):
            assert strings["services"][name]["fields"][field].get("name"), f"{name}.{field}"


# --- code that hassfest and HACS load ---------------------------------------------


def test_python_compiles() -> None:
    import py_compile

    for path in COMPONENT.rglob("*.py"):
        py_compile.compile(str(path), doraise=True)


def test_workflows_run_all_checks() -> None:
    """HACS default: the HACS action without ignored checks, and hassfest."""
    validate = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
    assert "hacs/action" in validate
    assert "category: integration" in validate
    assert not re.search(r"^\s*ignore:", validate, re.M)
    assert "home-assistant/actions/hassfest" in validate


def test_python_version() -> None:
    assert sys.version_info >= (3, 13)
