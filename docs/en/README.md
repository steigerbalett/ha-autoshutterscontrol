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
   brightness and sun elevation, residents and self defense, positions, window, shading,
   slats, privacy,
   drive behaviour and manual override.
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

### Brightness and sun elevation

More modes for *Morning/Evening drive by*: **Brightness**, **Sun elevation** and **Brightness and sun
elevation**. The cover drives as soon as the condition is met between the earliest and the latest time and
stays met as long as *Condition must hold for* says (checked every minute). The latest time is the deadline: if the
condition is not met by then, the cover drives at that time. There is only one morning and one evening
drive per day.

| Setting | Meaning |
|---|---|
| Open from / Close below | Lux thresholds (default 500 / 300) for the brightness sensor (page *Sensors*). |
| Open from / Close below sun elevation | Degrees above the horizon (default 3 / 1). |
| Sun elevation threshold from | *Fixed*, *Sensor* (threshold from a sensor) or *Sensor + offset*. |
| Brightness and sun elevation combined with | *One of them (OR)* or *Both (AND)*. |

### Calendar

*Earliest and latest times from* = *Calendar* (calendar on the page *Sensors*): an event whose title contains *Calendar: title for opening* (default `open`) replaces
the earliest and latest opening of that day with the start and end of the event; *Calendar: title for
closing* (default `close`) does the same for the evening. Case does not matter, all-day events are ignored. Days
without a matching event and an unreadable calendar use the configured times.

## Window

Per cover on the page *Window*: an *open* contact, a *tilted* contact and/or a sensor with three states
(texts for open and tilted can be set). Open wins over tilted. The sensor *Window* shows closed, tilted or
open.

- **Ventilation**: when a window is opened or tilted and the cover is below *Ventilation position* (default 50 %), it
  moves up. When it is open while a drive down is due, the cover only goes to the ventilation position.
  *Ventilation only drives up* (default on) keeps an open window from moving a higher cover down.
- **Full ventilation (comfort)**: with the global switch *Comfort* on, a fully open window drives to
  *Comfort position* (default 70 %).
- **Window closed**: the cover drives to its target or, with *When the window is closed* = *Previous position*, back to
  where it was before ventilating. Only if it was driven because of the window.
- **Delay when opened / closed**: the state must last this many seconds.
- **Lock-out protection**: *Soft* or *hard*: while the door is open (tilted only with *Lock-out protection also when tilted*) the
  cover does not move down. A blocked drive is done as soon as the door is closed. In this version *hard*
  blocks the same as *soft*; the difference (weather protection waits too) comes with stage 4.

## Privacy

- *Evening: minutes before closing*: that long before the evening drive to *Privacy position (evening)*
  (default 50 %).
- *Morning: minutes before opening*: that long before the morning drive to *Privacy position (morning)*
  (empty = same as evening).
- *Evening: when darker than*: in the evening already earlier, as soon as it is darker than this value.

The sensor *Next privacy* shows the next privacy drive.

## Residents

Page *Residents and self defense*. *Sources of the house status* (global, profile or cover) and per cover
*Sources of the room status*. Every source is mapped to a state:

| Source | State |
|---|---|
| Person, device tracker | `home` = at home, otherwise absent; away longer than *Away longer than (gone)* = gone |
| Zone (e.g. `zone.home`) | 0 = absent, 1 or more = at home |
| Binary sensor, input boolean (bed, sleep mode) | on = asleep, off = awake |
| Alarm panel | away/vacation = gone, night = asleep, home/disarmed = at home |
| Sensor, select | states `asleep`, `gotosleep`, `awoken`, `home`, `absent`, `gone` |

*Own mapping of source values* maps more values, e.g. `Schlafen:asleep, Urlaub:gone`. Several sources:
asleep > going to sleep > awake > at home > absent > gone. A source that is unavailable keeps its last known
state.

Each cover uses the room status if it has sources, otherwise the house status:

- **Sleeping**: with *Close when the residents go to sleep* (default on) the cover drives to *Sleep position*
  (empty = closed), also by day. While the residents sleep there is no morning drive, no ventilation and no
  shading unless allowed (*… while asleep*).
- **Waking up**: with *Open when the residents wake up* (default on) the cover goes to its target by day.
- **Morning / evening drive**: *Always*, *only when someone is at home*, *only when nobody is at home* or
  *never* (ASC `ASC_Mode_Up`/`_Down`, uses the house status).
- New mode *Residents* for *Morning/Evening drive by*: open in the morning as soon as the residents are awake,
  close in the evening as soon as they sleep, between the earliest and the latest time (the latest time is
  the deadline).

## Self defense

With the switch *Self defense* of the central device on (default off), covers with an open or tilted window
close as soon as nobody is at home: when *gone* at once, when *absent* after the delay (mode *When nobody is
at home*). *Self defense closes every cover* includes covers without an open window. Self defense wins over
lock-out protection and manual override. When someone comes home or the window is closed, the cover goes to
its target again. Binary sensor *Self defense* per cover.

## Shading

Page *Shading*, default *off*. Turn it on with *Shading* = *Always* (or only when someone / nobody is at
home), best in the profile of the facade. The switch *Shading* of the central device turns it off for all.

**Conditions** (only when their sensor or threshold is set):

| Condition | Start | End (hysteresis) |
|---|---|---|
| Sun direction | between *from* and *to* (default 105–255°, also across north) | outside |
| Sun elevation | between *from* and *to* (default 25–90°) | outside |
| Brightness | from *Start from brightness* (35000 lx), optionally averaged | below *End below brightness* (20000 lx) |
| Outdoor temperature | from 18 °C | below 18 °C minus hysteresis (1 K) |
| Indoor temperature | from the threshold (empty = off) | below threshold minus hysteresis |
| Forecast temperature | today's maximum from the threshold (sensor or daily forecast of the weather entity) | below threshold minus hysteresis |
| Weather condition | state of the weather entity in the list (default sunny, partly cloudy) | not in the list |
| Own binary sensor | on | off |

*Must (all)* (default: all) and *Or (at least one)*: shading starts when all Must conditions and, if the Or
list has configured conditions, one of them are met. An unavailable sensor starts no shading but does not end
one either.

**Sequence** as in ASC: none → *starts soon* (*Wait before shading*, default 10 min) → shading → *ends soon*
(*Wait before ending*, default 20 min) → none. When the sun leaves the area it ends at once (can be turned
off). Checked every minute, only by day and within *Shading from/until*.

**Driving**: to *Shading position* (30 %), to the alternative position while *Entity for the alternative
position* is on. *Shading only drives down* (default on). At the end the cover goes back to its target, but
only if it is still at the shading position (not after a manual drive or when it is closed); *Open again after
shading* off keeps it there until the evening. An open window wins (ventilation position).

**Heat protection**: from *Heat protection from* (outdoor temperature) the cover shades, also without sun,
and keeps it until the evening.

The sensor *Shading* per cover shows the state and all inputs in its attributes (sun direction, elevation,
brightness, temperatures, forecast, weather condition).

## Slats

Page *Slats*, for covers with a tilt position (or an own slat entity per cover). One slat position per drive
(open, closed, sleep, ventilate, comfort, shading, privacy); empty = the slats stay. *Shading steps by sun
elevation*: up to 4 steps `elevation:slats`, e.g. `20:70, 35:50, 50:30`; when the step changes during
shading only the slats are adjusted.

*Order*: position, then slats when the cover stands still (default, with a time limit) or after the wait, or
slats first, then position (Z-Wave). *Close the slats before a new setting* and an own *Tolerance of the
slats* are available too. Moving the slats by hand counts as a manual drive (not with an own slat entity).

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
Pause, Comfort, Shading, Self defense; sensor House status; buttons Recalculate times, All covers to target.

**Per cover**: switches Automatic and Pause; binary sensors Day, Manual override and Self defense; sensors Next
opening, Next closing, Next privacy, Last drive reason, Target, Window, Residents, Shading; buttons Drive to target and End manual override;
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
| 1 | Base, inheritance, arbiter, schedule (time/sun/workday), positions, manual override, delay, EN/DE |
| 2 | Window contacts (ventilation, comfort, lock-out), brightness, sun elevation, privacy, calendar |
| 3 (this version) | Residents, self defence, shading with all conditions, slats |
| 4 | Rain (also with open window), wind, frost, force, party, advent, trigger, wiggle |
| 5 | Recovery after restart, validation, logbook, FHEM import, HACS default |

## Translating

Each language is one file in `custom_components/autoshutterscontrol/translations/`. Field texts are
written once in `options.step.<section>`; run `python script/expand_translations.py` to copy them
into the profile and cover pages. Pull requests with new languages are welcome.
