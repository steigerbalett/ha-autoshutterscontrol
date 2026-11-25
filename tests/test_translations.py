"""Every language file has every key of strings.json, and the expansion is current."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "custom_components" / "autoshutterscontrol"


def _keys(data, prefix=""):
    out = {}
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(_keys(value, path))
        else:
            out[path] = value
    return out


def test_strings_is_english():
    assert (COMPONENT / "strings.json").read_text(encoding="utf-8") == (
        COMPONENT / "translations" / "en.json"
    ).read_text(encoding="utf-8")


def test_all_languages_complete():
    reference = _keys(json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8")))
    for path in (COMPONENT / "translations").glob("*.json"):
        keys = _keys(json.loads(path.read_text(encoding="utf-8")))
        assert set(keys) == set(reference), path.name
        for key, text in reference.items():
            placeholders = set(re.findall(r"\{(\w+)\}", text))
            assert placeholders == set(re.findall(r"\{(\w+)\}", keys[key])), f"{path.name}: {key}"


def test_expansion_is_current():
    result = subprocess.run(
        [sys.executable, str(ROOT / "script" / "expand_translations.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout


def test_services_translated():
    import yaml

    services = yaml.safe_load((COMPONENT / "services.yaml").read_text(encoding="utf-8"))
    strings = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
    for name, service in services.items():
        assert name in strings["services"]
        assert set(service.get("fields", {})) == set(strings["services"][name]["fields"])
