# AutoShuttersControl for HA

## Installation

1. HACS → three dots → *Custom repositories* → `https://github.com/steigerbalett/ha-autoshutterscontrol`, type *Integration*.
2. Install *AutoShuttersControl for HA* and restart Home Assistant.
3. *Settings → Devices & services → Add integration → AutoShuttersControl for HA*.

Home Assistant 2026.10 or newer is needed.

## Setup

There is **one** entry for the whole house.

1. **Main entry**: choose the workday sensors (optional). Without a sensor Monday to Friday are workdays.
2. **Options** (gear icon of the entry): global settings, one page each for schedule, sensors,
   positions, drive behaviour and manual override.
3. **Profiles** (optional, *Add profile*): settings for a group of covers, e.g. "South side".
4. **Covers** (*Add covers*): choose one or more covers and a profile. Change only what differs
   with the cover's *Reconfigure* button.

### Inheritance

Every value is resolved as **cover → profile → global → default**. On profile and cover pages
an empty field inherits; the line `↳` below a field shows the inherited value. *Back to the
inherited value* empties fields. The sensor *Target* of each cover shows all effective values and
where they come from in the attribute `effective_config`.

## Schedule

| Setting | Meaning |
|---|---|
| Morning/Evening drive by | *Sun*: sun event plus offset, kept between earliest and latest time. *Time*: at the earliest time (as in ASC). |
| Sun event | Sunrise/sunset, civil, nautical, astronomical twilight or an own sun elevation. |
| Earliest/latest opening and closing | Separate for workdays and days off. |
| Evening by tomorrow's day type | On Friday evening the day-off times apply. |

The global switch *Weekend and holiday times* off uses the workday times every day.
The switches *Morning drive* and *Evening drive* turn these drives off for all covers.

## Manual override

A drive that did not come from AutoShuttersControl (app, button, wall switch, other automation)
starts a manual override. AutoShuttersControl recognises its own drives by the Home Assistant
context; position reports during the *drive time* after its own command also count as its own.

- *Blocked during the override*: which drives wait (default: ventilation and shading, as in ASC).
- *The override ends*: after a duration (default 20 min), at a fixed time, at the next scheduled
  drive, or only by hand (button *End manual override*).
- *Opening by hand counts as morning drive*: opened by hand between the earliest opening and the
  scheduled time: no second morning drive that day. The same for closing.

## Rules

- *Opening never drives down*, *Closing never drives up* (ASC direction rule).
- Tolerance: within this distance a position counts as reached; nothing is driven.
- Delay: fixed plus random seconds before a scheduled drive.

## Entities

**Central device**: switches Automatic, Weekend and holiday times, Morning drive, Evening drive,
Pause; buttons Recalculate times, All covers to target.

**Per cover**: switches Automatic and Pause; binary sensors Day and Manual override; sensors Next
opening, Next closing, Last drive reason, Target; buttons Drive to target and End manual override;
selects Morning/Evening drive by (with *Inherit*); disabled config entities for positions and times.

Pause: nothing is driven, the target is still tracked; when the pause ends the cover drives to its
target. Automatic off: nothing is driven, and nothing happens when it is turned on again.

## Actions

| Action | Purpose |
|---|---|
| `autoshutterscontrol.drive` | Drive to a position or a named position (`open`, `closed`, …). |
| `autoshutterscontrol.apply_target` | Drive to the current target using all rules. |
| `autoshutterscontrol.recalculate` | Recalculate the drive times. |
| `autoshutterscontrol.clear_override` | End the manual override. |
| `autoshutterscontrol.set_option` | Set one setting of covers or of a profile; without value it inherits again. |

All actions take `entity_id` (the controlled covers) and/or `profile` (name); empty means all.

Events: `autoshutterscontrol_drive` (every drive, with `reason` and `trigger`) and
`autoshutterscontrol_manual` (manual drive detected).

## Roadmap

| Stage | Content |
|---|---|
| 1 (this version) | Base, inheritance, arbiter, schedule (time/sun/workday), positions, manual override, delay, EN/DE |
| 2 | Window contacts (ventilation, comfort, lock-out), brightness, sun elevation, privacy, calendar |
| 3 | Residents, self defence, shading with all conditions, slats |
| 4 | Rain (also with open window), wind, frost, force, party, advent, trigger, wiggle |
| 5 | Recovery after restart, validation, logbook, FHEM import, HACS default |

## Translating

Each language is one file in `custom_components/autoshutterscontrol/translations/`. Field texts are
written once in `options.step.<section>`; run `python script/expand_translations.py` to copy them
into the profile and cover pages. Pull requests with new languages are welcome.
