"""Fill the repeated parts of the translation files.

Every field text is written once per language, in ``options.step.<section>``
(fields that do not exist on the global level in
``config_subentries.cover.step.<section>``). This script copies the texts into
the profile and cover steps, the reset lists and the config entities, and
writes ``strings.json`` from ``translations/en.json``.

Run from the repository root:  python script/expand_translations.py
Check only (used by the tests): python script/expand_translations.py --check
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "custom_components" / "autoshutterscontrol"
TRANSLATIONS = COMPONENT / "translations"

_spec = importlib.util.spec_from_file_location("asc_settings", COMPONENT / "engine" / "settings.py")
settings = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["asc_settings"] = settings
_spec.loader.exec_module(settings)  # type: ignore[union-attr]

INHERIT_MARK = "↳ {inh_%s}"


def expand(lang: dict) -> dict:
    """Return the expanded translation."""
    out = copy.deepcopy(lang)
    options_steps = out["options"]["step"]
    subs = out["config_subentries"]
    cover_steps = subs["cover"]["step"]

    labels: dict[str, str] = {}
    descriptions: dict[str, str] = {}
    # Not on the global level: texts live in the cover steps
    cover_only = {s.key for s in settings.SETTINGS if settings.LEVEL_GLOBAL not in s.levels}
    for section in (*settings.SECTIONS, settings.SEC_SUMMARY):
        source = options_steps.get(section, {})
        labels.update(source.get("data", {}))
        descriptions.update(source.get("data_description", {}))
        source = cover_steps.get(section, {})
        for key, text in source.get("data", {}).items():
            if key in cover_only:
                labels[key] = text
        for key, text in source.get("data_description", {}).items():
            text = text.split("\n↳")[0]
            if key in cover_only and not text.startswith("↳"):
                descriptions[key] = text

    # Global level never shows the inherit mark
    for section in settings.sections_for(settings.LEVEL_GLOBAL):
        step = options_steps[section]
        step["data"] = {
            s.key: labels[s.key] for s in settings.settings_for(settings.LEVEL_GLOBAL, section)
        }
        step["data_description"] = {
            s.key: descriptions[s.key]
            for s in settings.settings_for(settings.LEVEL_GLOBAL, section)
            if s.key in descriptions
        }

    # First setup shows the sensors page
    user = out["config"]["step"]["user"]
    user["data"] = dict(options_steps[settings.SEC_SENSORS]["data"])
    user["data_description"] = dict(options_steps[settings.SEC_SENSORS]["data_description"])

    section_description = cover_steps[settings.SEC_SCHEDULE]["description"]
    for sub_key, level in (("profile", settings.LEVEL_PROFILE), ("cover", settings.LEVEL_COVER)):
        steps = subs[sub_key]["step"]
        for section in settings.sections_for(level):
            step = steps.setdefault(section, {})
            step["title"] = options_steps[section]["title"]
            step["description"] = section_description
            step["data"] = {s.key: labels[s.key] for s in settings.settings_for(level, section)}
            step["data_description"] = {}
            for s in settings.settings_for(level, section):
                mark = INHERIT_MARK % s.key
                desc = descriptions.get(s.key)
                step["data_description"][s.key] = f"{desc}\n{mark}" if desc else mark
        steps["reset"] = copy.deepcopy(options_steps["reset"])
        steps["reset"]["description"] = subs[sub_key]["step"]["reset"].get(
            "description", options_steps["reset"].get("description", "")
        )

    selectors = out["selector"]
    inherit_label = selectors["tristate"]["options"]["inherit"]
    selectors["setting_key"] = {
        "options": {s.key: labels[s.key] for s in settings.SETTINGS if s.active}
    }
    for s in settings.SETTINGS:
        if not s.active or s.kind not in (settings.SELECT, settings.MULTI):
            continue
        opts = selectors[s.key]["options"]
        if s.kind == settings.SELECT:
            opts["inherit"] = inherit_label
        missing = [o for o in s.options if o not in opts]
        if missing:
            raise SystemExit(f"selector {s.key}: missing options {missing}")

    entity = out["entity"]
    for s in settings.SETTINGS:
        if not s.active or not s.entity:
            continue
        platform = entity.setdefault(s.entity, {})
        item: dict = {"name": labels[s.key]}
        if s.entity == "select":
            item["state"] = {
                "inherit": inherit_label,
                **{o: selectors[s.key]["options"][o] for o in s.options},
            }
        platform[s.key] = item
    return out


def _dump(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    check = "--check" in sys.argv
    changed = []
    for path in sorted(TRANSLATIONS.glob("*.json")):
        text = path.read_text(encoding="utf-8")
        new = _dump(expand(json.loads(text)))
        if new != text:
            changed.append(path)
            if not check:
                path.write_text(new, encoding="utf-8")
    strings = COMPONENT / "strings.json"
    en = (TRANSLATIONS / "en.json").read_text(encoding="utf-8")
    if not strings.exists() or strings.read_text(encoding="utf-8") != en:
        changed.append(strings)
        if not check:
            strings.write_text(en, encoding="utf-8")
    if check and changed:
        print("Not expanded:", ", ".join(str(p.relative_to(ROOT)) for p in changed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
