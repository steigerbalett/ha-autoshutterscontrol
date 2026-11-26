# AutoShuttersControl for HA

## Installation

1. *Settings → Marketplace* (Home Assistant 2026.11 and newer, before that HACS) → three dots → *Custom
   repositories* → `https://github.com/steigerbalett/ha-autoshutterscontrol`, type *Integration*. Or press the
   button in the [README](../../README.md#installation).
2. Versions 0.x are pre-releases: switch on *Show beta versions* for the repository.
3. Install *AutoShuttersControl for HA* and restart Home Assistant.
4. *Settings → Devices & services → Add integration → AutoShuttersControl for HA*.

Home Assistant 2026.10 or newer is needed.

## Setup

New here? The [setup guide](setup.md) explains everything step by step, with recipes for typical rooms.

There is **one** entry for the whole house.

1. **Main entry**: choose the sensors of the house (workday, brightness, weather, all optional). Without a
   workday sensor Monday to Friday are workdays.
2. **Options** (gear icon of the entry): global settings, one page each for schedule, sensors,
   brightness and sun elevation, residents and self defense, positions, window, shading,
   slats, privacy, rain/wind/frost, special functions, drive behaviour, manual override, extra
   conditions and actions, and *Import from FHEM*.
3. **Profiles** (optional, *Add profile*): settings for a group of covers, e.g. "South side".
4. **Covers** (*Add covers*): choose one or more covers and a profile. Change only what differs
   with the cover's *Reconfigure* button.
5. Changes on the pages are kept only with **💾 Save and close** in the menu.

### Inheritance

Every value is resolved as **cover → profile → global → default**. On profile and cover pages
an empty field inherits; the line `↳` below a field shows the inherited value. *Back to the
inherited value* empties fields. The sensor *Target* of each cover shows all effective values and
where they come from in the attribute `effective_config`.

### Alternative profile (e.g. summer/winter)

On the cover, page *Cover*: *Alternative profile*, an *Entity for the alternative profile* and its *Value*
(default `on`). While the entity shows the value, the cover inherits from the alternative profile instead of
the normal one, e.g. with an input boolean "Winter" or an input select "Season". When it switches, the cover
drives to the new target, in any direction. If the entity is briefly unavailable, its last state counts. The
sensor *Target* shows the active profile in the attribute `profile`.

Instead of or in addition to the entity, a period of the year works: *Alternative profile from* and *until* as
DD.MM., e.g. `1.11.` to `31.3.` for winter (across the new year, both days included). At midnight it is checked
whether the period begins or ends. With both entity and period, the alternative profile applies as soon as
either one applies.

## Schedule

| Setting | Meaning |
|---|---|
| Morning/Evening drive by | *Sun*: sun event plus offset, kept between earliest and latest time. *Time*: at the earliest time (as in ASC). *Entity*: at the time of an entity plus offset, kept between earliest and latest time. |
| Morning/Evening time from entity | For *Entity*: an `input_datetime`, a time entity or a timestamp sensor, e.g. *Next alarm* of the Home Assistant app, `sensor.sun_next_rising`/`_setting` or an own template. A timestamp counts only on its own day; without a usable value the latest time applies in the morning, the earliest in the evening. Once the drive ran the day is done, even when the alarm already shows the next day. |
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
  cover does not move down. A blocked drive is done as soon as the door is closed. *Hard* also makes
  rain and wind protection wait and can lock the actuator (see *Hardware lock*).

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

### Guests

At the cover (page *Residents*): *Guests in this room* takes persons, device trackers or a switch/input
boolean (`home` or on = guest present). The switch **Guest present** at the cover sets a guest by hand.
*If a guest is present* (default *No morning drive*):

- *No morning drive*: the cover does not open in the morning (not for shading or privacy either); closing,
  ventilation and protection stay.
- *No morning and evening drive*: the schedule does not drive at all.
- *Only manual drives*: no automatic drives except force and protection (rain, wind, water, frost, self
  defense); *Not driven because* shows *Guest*.

When the guest is gone or the switch is off, the cover goes to its target at once (the morning opening is
caught up). Binary sensor *Guest* per cover.

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

**Hot day** (*Hot day: shading position in the morning*, default off): when the forecast of today reaches
*Hot day from* (default 26 °C, forecast sensor or daily forecast of the weather entity) and, with *only with
sunny forecast*, one of the weather conditions for shading, the morning drive does not open completely but
goes straight to the shading position, as long as the sun will still shine on the window today (sun
direction and elevation of the shading). Nothing moves to shading at night, so the rooms can cool down as
much as possible. The cover stays at the shading position until the sun has passed the window or the normal
shading of the day ends; then it returns as after shading. The binary sensor *Hot day* per cover shows
whether it applies now.

**Horizon**: buildings and trees hide a low sun at different heights in different directions. Press the
button *Sun has left the window* of the cover at the moment the sun disappears behind something. The direction
and elevation of the sun become a point of the horizon (field *Horizon of the window*, e.g. `200:18, 230:25`,
editable there), and the shading ends at once. A new point within 3° replaces the old one. Between the points
the horizon is interpolated, beyond the outermost points their value holds for 15°. Below the horizon the
sun does not shine on the window, for shading, glare protection and the hot day.

**Shading by the depth of the sun**: with *Window sill above the floor* and *Window height* (per cover) and
*Sun may reach into the room*, the shading goes down only so far that direct sun falls at most that far over
the floor. It uses the profile angle of the sun to the *Window direction*. A high summer sun leaves most of the
window open, a low sun closes it to the shading position, never lower. The position is rounded down to 10 %
and changes at most every 15 minutes. With a sill of 90 cm, a window of 130 cm and 2 m, and the sun straight in
front of the window: 40° sun elevation gives 50 %, from 55° the cover stays open.

**Glare protection** (*Glare protection*, default off): when bright sun shines on the window (sun direction,
elevation and horizon of the shading), the cover goes to the *Glare position* (40 %) after *Glare protection
after* (5 min), whatever the temperature, also in winter. Bright means from *Glare from brightness* (50000 lx,
brightness sensor of the shading); without a brightness sensor a sunny weather decides. It ends below *Glare
ends below brightness* (35000 lx) after *Glare protection ends after* (20 min), at once when the sun leaves the
window. Only by day and not while nobody is at home. Together with shading the lower position wins. Binary
sensor *Glare protection* per cover.

**Nobody at home**: with *Nobody at home: heat limits lower by* (default 0 = off) AutoShuttersControl shades
earlier while the house status is absent or gone or the switch *Holiday* is on. Outdoor temperature, indoor
temperature and *Heat protection from* are then lower by that value. Example: heat protection from 25 °C and
3 K gives 22 °C while away.

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

**Slat angle from the sun** (default off): while shading AutoShuttersControl calculates from the sun
position and the slat geometry the angle that just keeps the direct sun out and lets in as much light as
possible, and adjusts the slats every minute in steps of 5 %. Settings: *Slat distance / slat width*
(default 0.9), the tilt positions for *horizontal* (100 %) and *vertical* (0 %), and on the page *Shading*
the *Window direction* (empty = middle of *Sun direction from/until*). With a high or sideways sun the slats
open further, with a low sun in front of the window they nearly close. The steps by sun elevation do not
apply then.

## Rain, wind and frost

Sensors on the page *Sensors*: *Rain sensor* (binary sensor, on = rain, or rain amount), *Wind speed* and
*Outdoor temperature*. The settings are on the page *Rain, wind and frost*. All protections have a hysteresis
and waits in both directions; an unavailable sensor keeps the last state.

- **Water protection** (on by default): when it rains and the window is tilted or open (configurable), the
  cover drives to *Water protection position* (default 0 %). With the lock-out protection at most to the
  ventilation position, unless *Water protection closes completely despite the lock-out* is on. Once per rain
  the event `autoshutterscontrol_rain_window` fires (and the extra action *Action at water protection*), e.g.
  for a notification.
  - *Back after the rain* (default *Previous position*): when it is dry again (after *Wait after the rain*) or
    the window is closed, the cover goes back to its position from before the water protection, e.g. to the
    40 % you had set by hand.
  - If something else applies by now, it goes to the new target instead: the evening or morning drive was due
    in the meantime, shading started or ended, a manual override started or ended (also by a manual drive
    during the rain) or the positions changed.
  - With *Target state* it always goes to the current target (behaviour up to 0.6.0).
- **Rain protection** (off by default, for awnings): drives to *Rain position* when it rains, back after
  *Wait after the rain* (default 15 min).
- **Wind protection** (off by default, for venetian blinds and awnings): from *Wind from* (default 50 km/h)
  to *Wind position*; ends below threshold minus hysteresis (default 20) and after the wait (default 10 min).
  *Wind protection drives to*: *Wind position* (default), *Nearest end*, *Always open* or *Always closed*.
  With the last three the cover is only fully open or fully closed in a storm, a half open cover catches the
  wind. *Nearest end* takes the end nearest to what the other functions want now (open from 50 %, else
  closed). A cover moved by hand in between goes back to an end at once.
- **Frost protection** (off by default) below *Frost below* (default 2 °C): *Soft* closes only down to
  *Frost position*, *morning* / *afternoon* blocks drives until / from noon, *No drives at all* blocks everything
  except rain, wind and force.

- **Temperature limits** (off by default): *Close above outdoor temperature* and *Close below outdoor
  temperature*. The cover closes while the limit is passed and opens again when the temperature is 1 °C back.
  A manual override and an open window (ventilation) win.
- **Winter**: the binary sensor *Winter* of the central device is on while the mean outdoor temperature of
  the last 24 hours is below *Winter below* (default 12 °C, 1 °C hysteresis, attribute `mean_24h`). Set as
  the *entity of the alternative profile* it switches e.g. a profile *Winter* by itself.

Rain and wind protection win over manual override, self defence and all schedules. *Lock-out protection
hard* also makes rain and wind protection wait until the door is closed.

On the central device the binary sensors *Rain*, *Wind* and *Frost* show the global sensors; per cover
*Rain protection*, *Water protection*, *Wind protection* and *Frost protection* show what acts now.

## Special functions

Page *Special functions*; fields with entities exist only on the cover.

- **Force functions**: *Force close / open / ventilate / shading*, one entity each (input boolean, switch,
  binary sensor). While on, the cover holds the position, above all other rules (also with Automatic off or
  pause). Off: back to the target (*Go back after a force function*).
- **Pause entity**: while on, this cover does not move automatically; off: target.
- **Party**: switch *Party* of the central device (off by default). While on, all covers taking part do not
  move automatically (protections still do); off: target.
- **Advent**: switch *Advent* of the central device (off by default). From the 1st Sunday of Advent until
  6 January (or 2 February) the evening closing waits until the button *Release deferred drives* or the action
  `autoshutterscontrol.release_deferred` releases it; the release lasts until the end of the day.
  - Period: *Advent mode from* = first Sunday of Advent (default) or *Own day* with *Own start*, e.g. `1.12.`.
    *Advent mode until* = 6 January (default), 2 February or *Own day* with *Own end*, e.g. `24.12.` or
    `15.1.`. Days as DD.MM., the period may span the new year.
  - If an own day is missing or invalid, the default applies and a repair issue appears.
- **External trigger**: any entity with up to two values and one position each, e.g. a select *Cinema* → 0 %.
  When the value ends, the cover drives to its target.
- **Wiggle**: button *Wiggle* per cover, *Wiggle all* on the central device, or the action
  `autoshutterscontrol.wiggle`: moves by *Wiggle by* (default 5 %) and back after *Wiggle wait*. Not counted as
  a manual drive.
- **Holiday**: switch *Holiday* of the central device (default off, e.g. from a calendar by an automation).
  The morning and the evening drive then shift every day by a random number of minutes up to *Holiday: shift
  the times up to* (default 30), morning and evening independently, different for every cover and the same
  after a restart. The shift comes after the earliest and latest times, so it may leave them. Holiday also
  counts as "nobody at home" for the heat limits and the glare protection.
- **Lock**: select *Lock* per cover or the action `autoshutterscontrol.set_lock` with `mode` (`hold`,
  `open`, `closed`, `none`) and optionally `duration` in minutes, e.g. *Force closed* for 120 minutes on a
  movie night. *Hold*: no automatic drives except force and protection. *Force open/closed*: fully open or
  fully closed. Water, rain, wind and frost protection win. The lock ends after the duration, with *None*, with
  a manual drive or with the button *End manual override*; then the cover goes to its target. It survives a
  restart.
- **Hardware lock**: with *Lock-out protection hard* and an entity in *Hardware lock* (switch, lock, input
  boolean) the actuator is locked while the door is open and unlocked afterwards. The switch *Hardware lock*
  of the central device (on by default) turns this off.

## Extra conditions and actions

Page *Extra conditions and actions*, with the editors of Home Assistant:

- Conditions for all drives, for opening, closing, ventilation and shading. If it is false at drive time,
  the drive is skipped; *Drive to target* catches up. Force and protections are not affected. An invalid
  condition counts as false (warning in the log).
- Actions at each drive (variables `cover`, `position`, `reason`, `trigger`), at a manual drive
  (`position`), at the end of the override and at water protection.

## Catching up after a restart or a failure

*Catch up missed drives* (page *Drive behaviour*):

- *After a failure* (default): if Home Assistant was off when a morning or evening drive was due, every
  cover drives to its target 45 seconds after the start. If the cover itself was unavailable, the missed
  drive is done as soon as it is back.
- *Always after a restart*: to the target after every start.
- *Never*.

Catching up uses all rules (override, lock-out, window …). The state (override, drives done, protections)
is kept in the storage of Home Assistant and survives every restart.

## Check, logbook and diagnostics

- **Plausibility check**: at the start and after every change AutoShuttersControl checks the effective
  settings of every cover and reports mistakes under *Settings → Repairs*, e.g. earliest time after the
  latest, 0:00 as latest closing time, swapped thresholds, rain protection without rain sensor, or entities
  that do not exist. When fixed, the issue disappears.
- **Drive check** (*Check every drive*, on by default): after the *Drive time* plus 10 seconds the cover
  must be at its position (± tolerance, at least 2 %). If it is still moving, it is checked again later. If it
  stands elsewhere, the command is sent once more; if that does not arrive either, the diagnostic sensor
  *Stuck* turns on and a repair issue appears. Both clear at the next drive that arrives. A manual drive in
  between cancels the check. Only for covers that report a position.
- **Logbook** (*Logbook entries*, on by default): an entry at the cover for every drive with its reason, for
  every drive deliberately not done (e.g. "did not drive (Evening closing): Pause") and for manual drives.
- The diagnostic sensor **Not driven because** shows why the last decision did not drive.
- **Diagnostics** (entry → three dots → *Download diagnostics*): per cover the effective settings and the
  last 50 decisions with all inputs (situation, wishes, residents, window, shading, protections).

## Overview

The overview matches the *ASC Configuration and Information Summary* of FHEM. It is available in two places:

- right in the integration: *Configure* → **Overview** (state when opened, open again to refresh), one block
  per cover so that it is readable in the narrow dialog;
- optionally as the page **AutoShuttersControl** in the sidebar (*Overview in the sidebar*, page *Drive
  behaviour*, default off), as a large table with all columns, refreshed every 10 seconds. The overview in
  the dialog links to it.

It shows:

- on top sun azimuth and elevation, forecast today, house status, active protection and all global
  switches;
- per cover: next opening and next closing, morning/evening drive by, residents up/down, shading, party
  mode, lock-out, last drive (reason, position, time), position and slats, target with reason, not driven
  because, shading state since, window, residents, and notes such as pause, simulation, manual until, quiet
  hours, hot day, rain/wind/water/frost;
- **Linked sensors and values** (as the monitored devices, NOTIFYDEV, in FHEM): every entity of the
  settings with its current value and unit (e.g. brightness sensor 23000 lx, rain, wind, temperatures,
  window contacts, residents), the setting, who uses it (global and/or covers) and when it last changed. A
  missing entity shows *missing*.

On the sidebar page a click on a cover or an entity opens its dialog.

## Import from FHEM

The names in FHEM and in Home Assistant may differ: you choose the mapping. Step by step with
the commands: [setup guide](setup.md#10-moving-from-fhem).

**Everything at once**: Options → *Import from FHEM*:

1. Paste the output of `list -r TYPE=AutoShuttersControl` and `list -r ASC=[12]` from the FHEM command line
   (or the whole `fhem.cfg`). Only `define` and `attr` lines are read.
2. Choose a Home Assistant cover for each FHEM shutter. Suggestions come from similar names.
3. Choose entities for the FHEM devices in the attributes (sensors, window contacts, residents).
4. The summary shows what is imported and what cannot be transferred (Perl code, unknown attributes).
   Covers that are already set up stay unchanged unless *Update covers that are already set up* is on.
   Submit creates the covers and saves the global settings.

The attributes of the ASC device become global settings, those of the shutters cover settings. Values all
shutters share move to the global settings; values that only repeat the default are dropped.

**One shutter**: on the cover *Reconfigure* → *Import from FHEM*. Paste the output of
`list -r <name in FHEM>`. With several shutters in the text you choose one. Then map its devices; the list shows every value
that is taken over. Values that equal what the cover inherits stay inherited. *Delete the own values of this
cover first* starts from scratch. Back in the menu, **💾 Save and close** keeps it.

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
- *Staggered drives* (global only, default 0): covers that are due at the same time start one after the
  other, the set number of seconds apart (radio, power). Force, rain, wind and water protection always drive
  at once. The FHEM import takes `ASC_shuttersDriveDelay`.
- *Quiet hours from/until* (page *Drive behaviour*, a fixed time or from an `input_datetime`/time entity,
  also across midnight): no automatic drives, except force, rain, wind, water and frost protection and self
  defense. *Ventilate in the quiet hours* (default on) still moves the cover to the ventilation position for
  an opened window. At the end of the quiet hours the cover goes to its target. Binary sensor *Quiet hours*
  per cover.
- *Simulation* (switch at the central device for all, at the cover for one): AutoShuttersControl decides and
  logs everything as usual but does not drive ("would drive to 30 % (Shading), simulation" in the logbook,
  event `autoshutterscontrol_drive` with `simulation: true`). The diagnostic sensor *Simulated drive* shows
  the last one. Drives by action (`autoshutterscontrol.drive`) still happen.

## Entities

**Central device**: switches Automatic, Weekend and holiday times, Morning drive, Evening drive,
Pause, Comfort, Shading, Self defense, Party, Advent, Hardware lock, Simulation, Holiday; sensor House status; binary sensors Rain,
Wind, Frost, Winter; diagnostics: sensors Sun azimuth, Sun elevation (calculated from the location of Home
Assistant), Forecast maximum today (global forecast sensor or daily forecast of the global weather entity),
binary sensors Sunny (weather now in the list of the shading) and Hot day (forecast from *Hot day from*);
buttons Recalculate times, All covers to target, Wiggle all, Release deferred drives.

The entities of a cover are on the device of the real cover (e.g. the Shelly or Homematic actuator), as
with the helpers of Home Assistant. A cover without a device (e.g. a template cover) gets an own device
"ASC ‹name›" below the central device.

**Per cover**: switches Automatic, Pause, Simulation and Guest present; binary sensors Day, Manual override, Self defense, Rain
protection, Water protection, Wind protection, Frost protection, Force function, Hot day, Quiet hours, Guest, Glare
protection and (diagnostic) Stuck; sensors Next
opening, Next closing, Next privacy, Last drive reason, Target, Not driven because, Window, Residents, Shading, Simulated drive; buttons Drive to target, End manual override, Wiggle and Sun has left the window;
selects Lock and Morning/Evening drive by (with *Inherit*); disabled config entities for positions and times.

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
| `autoshutterscontrol.wiggle` | Move covers a little and back (function check). |
| `autoshutterscontrol.release_deferred` | Advent: do the closing deferred today now. |
| `autoshutterscontrol.set_lock` | Lock covers (`hold`, `open`, `closed`), optionally for `duration` minutes; `none` ends it. |

All actions take `entity_id` (the controlled covers) and/or `profile` (name); empty means all.

Events: `autoshutterscontrol_drive` (every drive, with `reason` and `trigger`) and
`autoshutterscontrol_manual` (manual drive detected) and `autoshutterscontrol_rain_window` (rain with an open
window, with `window`, `position`, `driven`, `blocked_by`).

## FAQ

**Why does a cover not move?** The sensor *Not driven because* and the logbook of the cover show the reason.
The sensor *Target* shows what would apply now and, in `effective_config`, where every value comes from.

**After a manual drive the cover no longer moves automatically.** That is the manual override. It ends
after the configured time or with the button *End manual override*.

**Can I switch AutoShuttersControl off for a while?** Switch *Pause* (the target is tracked and driven to
afterwards) or *Automatic* (nothing happens, not even when turned on again), globally or per cover.

**Do I need profiles?** No. They save work when several covers share the same deviations, e.g. one facade for
shading.

**Can FHEM and Home Assistant run in parallel?** Yes, but control a cover from one side only. Otherwise each
side detects the drives of the other as manual drives.

## Translating

Each language is one file in `custom_components/autoshutterscontrol/translations/`. Field texts are
written once in `options.step.<section>`; run `python script/expand_translations.py` to copy them
into the profile and cover pages. Pull requests with new languages are welcome; see
[translating.md](translating.md).

## Thanks

AutoShuttersControl for HA rebuilds the functions of the FHEM module AutoShuttersControl. Many thanks to its author **CoolTux**:

> AutoShuttersControl for FHEM
>
> (c) 2018-2026 Copyright: Marko Oldenburg (fhemdevelopment at cooltux dot net)

From the FHEM module, special thanks goes to:

- Bernd (Cluni): this module is based on the logic of his script "Rollladensteuerung für HM/ROLLO inkl. Abschattung und Komfortfunktionen in Perl" ([FHEM forum](https://forum.fhem.de/index.php/topic,73964.0.html))
- Beta-User for many tests, many suggestions and good discussions
- pc1246 write english commandref
- FunkOdyssey commandref style
- sledge fix many typo in commandref
- many User that use with modul and report bugs
- Christoph (christoph.kaiser.in) Patch that expand RegEx for Window Events
- Julian (Loredo) expand Residents Events for new Residents functions
- Christoph (Christoph Morrison) for fix Commandref, many suggestions and good discussions
