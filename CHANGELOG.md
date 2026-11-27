# Changelog

## 0.10.1

- Import from FHEM also reads the *Raw definition* of devices (`defmod` and `attr` lines), globally and on the
  cover. Only the ASC attributes count; `room`, `icon`, `userattr`, `webCmd` and the like are skipped without a
  message.
- Import of more ASC attributes: `ASC_autoShuttersControlMorning`/`Evening`/`Comfort` (switches of the
  central device), `ASC_advStartDate`, `ASC_advEndDate`, `ASC_PrivacyUp_Pos`, `ASC_Shading_InOutAzimuth`,
  `ASC_ShuttersPlace` (terrace → preset *Patio door*, awning → type *Awning*), the spelling
  `ASC_AutoAstroMode…` of newer ASC versions and `ASC_rainSensor` with a text instead of a threshold. The list of
  a single shutter shows options in the language of Home Assistant.
- *Advent mode from*: new option *Sunday before Advent* (Totensonntag).
- Sun event *Blue hour* (sun 4° below the horizon).
- The switch *Overview in the sidebar* moved from *Drive behaviour* to the page *Overview*; its first line shows
  whether the page is on.

## 0.10.0

- Sidebar page, tab *Edit covers*: all covers as a table; edit one or several at once (only the changed fields
  are saved for every selected cover), with the inherited value and its source next to every field; add,
  duplicate and remove covers. The values stay in the subentries. Only administrators can change anything.
- Dashboard cards, loaded automatically: `custom:autoshutterscontrol-card` (all or selected covers as grid,
  list or compact) and `custom:autoshutterscontrol-cover-card` (one cover). Animated window with position and
  target, target with reason, not driven because, next drives, buttons open, stop, close, drive to target and
  automatic (ends a manual override). Asks before closing while the lock-out protection is active. Card editor.
- Groups: cover entity *All covers* and one per profile on the central device. Commands go to every member as a
  manual drive; the lock-out protection of every member holds. Awnings are not part of groups.
- *Minimum gap between commands* (global, default off): all commands to covers go through one queue.
- *Manual drive to a known position keeps the automatic* (default off).
- Emergency: *Emergency input* (e.g. smoke detectors) drives all covers to the *Emergency position* (default
  100 %) and retracts awnings, before everything else. Latched until the button *Reset emergency* (default on).
  Binary sensor *Emergency*.
- A window contact that is unavailable or unknown counts as not closed (lock-out protection holds) and raises a
  repair issue after 2 minutes.
- Window presets *Patio door*, *Vent window* and *Protection only* (profile and cover); own fields win.
- *Close in the evening as soon as on* (e.g. the light) with *Close by entity not before*; night position as a
  second stage from a time or an entity.
- Sun event *Golden hour* (sun 6°).
- *Do not close in summer* with *Summer from/until*; *Advent position*: in Advent the closing goes to this
  position instead of waiting.
- Awnings: *Type* = *Awning* extends for shading by day and retracts otherwise, at night and with wind, rain
  and frost.
- Docs: recipes for school holidays and smoke detectors in the setup guide.
- Sidebar overview: the switch *Holiday* shows its name.

## 0.9.1

- Setup guide step by step in German and English (`docs/de/einrichtung.md`, `docs/en/setup.md`), with recipes
  for typical rooms and the move from FHEM. Linked from the README.
- Import of one shutter from FHEM: on the cover *Reconfigure* → *Import from FHEM*, paste the output of
  `list -r <name>`. The names may differ; with several shutters in the text you choose one. Values equal to
  the inherited ones stay inherited; optionally the own values of the cover are deleted first.
- Import of everything from FHEM: the help names the commands `list -r TYPE=AutoShuttersControl` and
  `list -r ASC=[12]`; new option *Update covers that are already set up*.
- The menu item *Save* is now *💾 Save and close* with a hint below it, in the global menu, in profiles and in
  covers.
- The overview in the dialog shows one block per cover instead of a wide table, so it is readable in the
  narrow dialog, and links to the overview in the sidebar.

## 0.9.0

- Drive check (*Check every drive*, default on): after the drive time the cover must be at its position;
  otherwise the command is sent once more, and if that does not arrive either the diagnostic binary sensor
  *Stuck* turns on and a repair issue appears. Both clear at the next drive that arrives.
- Horizon per window: the button *Sun has left the window* stores the direction and elevation of the sun as a
  point of the horizon (field *Horizon of the window*, editable). Below the horizon the sun does not count as
  on the window (shading, glare, hot day).
- Shading by the depth of the sun: with window sill, window height and *Sun may reach into the room* the cover
  goes down only as far as needed, never below the shading position.
- Glare protection (default off): own position for bright sun on the window, whatever the temperature, only
  by day and not while nobody is at home. Binary sensor *Glare protection*, drive reason "Glare protection".
- Temperature limits: close above or below an outdoor temperature (1 °C hysteresis). Binary sensor *Winter*
  (24 hour mean of the outdoor temperature below *Winter below*, default 12 °C), usable as the entity of the
  alternative profile.
- *Nobody at home: heat limits lower by* (default 0 = off).
- Switch *Holiday*: the morning and the evening drive shift every day by random minutes (*Holiday: shift the
  times up to*, default 30), the same after a restart.
- Lock: select *Lock* per cover and action `autoshutterscontrol.set_lock` (hold, force open, force closed,
  optionally with a duration). Ends with a manual drive or *End manual override*.
- Wind protection drives to: wind position (as before), nearest end, always open or always closed. A cover
  moved by hand in between goes back to an end.

## 0.8.0

- Devices: the entities of a cover are now shown on the device of the real cover (as the helpers of Home
  Assistant do). The own device "ASC ‹name›" is only kept for covers without a device and is removed
  otherwise; entity ids stay the same.

- Overview as the ASC Configuration and Information Summary in FHEM, right in the integration (*Configure*
  → *Overview*) and optionally as the page **AutoShuttersControl** in the sidebar: all covers with next opening/closing, modes, party mode, lock-out, last drive, position, target,
  not driven because and shading info, plus global switches, sun, forecast and house status.
- Linked sensors and values (as the monitored devices in FHEM): every entity of the settings with its value
  and unit, the setting, who uses it and when it changed; missing entities are marked.
- New global setting *Overview in the sidebar* (default off). Websocket command
  `autoshutterscontrol/summary` with the same data.
- Guests per cover: *Guests in this room* (person, device tracker, switch, input boolean) or the switch
  *Guest present*. While a guest is present the cover does not open in the morning; it is caught up when
  the guest is gone. Binary sensor *Guest*. Setting *If a guest is present*: no morning drive (default), no
  morning and evening drive, or only manual drives (force and protection still drive).

## 0.7.3

- Simulation: switch at the central device (all covers) and per cover. Everything is decided and logged,
  nothing is driven; logbook "would drive to …", event `autoshutterscontrol_drive` with `simulation: true`,
  diagnostic sensor *Simulated drive*.
- Staggered drives (global): covers due at the same time start the set seconds apart; not for force, rain,
  wind and water protection. FHEM `ASC_shuttersDriveDelay` is imported.
- Slat angle from the sun: while shading the slats follow the sun (profile angle and slat distance/width),
  in steps of 5 %. New settings slat distance/width, tilt horizontal/vertical, window direction.
- Quiet hours (fixed or from an `input_datetime`/time entity, across midnight): no automatic drives except
  force and protection; ventilation optional (default on); at the end the cover goes to its target. New
  block "Quiet hours", binary sensor per cover, repair issue for only start or only end.
- Hot day (optional, default off): with a hot (and sunny) forecast the morning drive goes straight to the
  shading position while the sun will still shine on the window today; nothing moves at night so the rooms
  can cool down. Ends when the sun has passed the window or the normal shading ends. New drive reason
  "Hot day", binary sensor per cover.
- Morning/evening time from an entity (mode *Entity*): `input_datetime`, time entity or timestamp sensor
  (e.g. next alarm of the phone), with offset, kept between earliest and latest time. Repair issue for a
  missing entity.
- Diagnostic entities at the central device: sun azimuth, sun elevation, forecast maximum today, sunny,
  hot day.

## 0.7.2

- Advent: own period. *Advent mode from* first Sunday of Advent or an own day, *Advent mode until* 6 January,
  2 February or an own day (DD.MM., across the new year). Repair issue for a missing or invalid own day.
- Alternative profile: period of the year (*from*/*until* as DD.MM., e.g. 1.11. to 31.3. for winter),
  checked at midnight, in addition to the entity (either is enough).
- Repository: the HACS action now runs all checks (brand icon from `brand/`), weekly as well; the release
  draft waits until Tests and Validate succeeded; Dependabot once a month; new tests for the requirements of
  HACS/Marketplace default and hassfest (manifest, hacs.json, brand icons, translations, services).
- README and documentation: thanks to CoolTux, author of FHEM AutoShuttersControl, and to everyone thanked in
  the FHEM module. README split into an English part on top and a German part below. Internal notes
  (stage overview, pre-release note in the README) removed.

## 0.7.1

- Water protection: when it is dry again or the window is closed, the cover goes back to its position from
  before the water protection, unless another target applies by now (other drive, shading, manual
  override). New setting *Back after the rain* (previous position / target state, default previous
  position). New drive reason "After the rain".
- Workflow "Release draft": after every push to main a draft release for the version in manifest.json, with
  the CHANGELOG section as notes. Versions 0.x and betas are marked as pre-release. The draft gets
  `autoshutterscontrol.zip`, which HACS/the Marketplace installs.
- README: badges and installation via the Marketplace.
- New icon: a shutter from the OpenAutomation icon set of FHEM with the FHEM logo as a badge, black with a
  white variant for the dark theme (CC BY-SA 3.0 DE, see NOTICE.md).

## 0.6.0b1

- Alternative profile per cover while an entity shows a value (e.g. summer/winter, CCA `instance_active`,
  concept 6.7). Switching drives to the new target in any direction; the last state counts while the entity
  is unavailable. The sensor Target shows the active profile.

## 0.5.0b1

Stage 5 of the concept.

- Catching up: after a restart (Home Assistant was off when a morning/evening drive was due) or when the
  cover is available again, the target is driven to; mode never / after a failure (default) / always.
- Plausibility check of the effective settings of every cover as repair issues (time order, 0:00 as latest
  closing time, swapped thresholds, empty sun elevation range, wind hysteresis, equal positions, functions
  without their sensor, entities that do not exist).
- Logbook entries at the cover for drives, deliberately skipped drives and manual drives, in the language of
  Home Assistant (can be switched off). New diagnostic sensor "Not driven because".
- Diagnostics: the last 50 decisions per cover now contain all inputs.
- Import from FHEM in the options: paste fhem.cfg, map shutters to covers and FHEM devices to entities
  (suggestions by name), summary with what cannot be transferred.
- Brand icon in `brand/`, docs: catching up, check/logbook/diagnostics, FHEM import, FAQ, translating.

## 0.4.0b1

Stage 4 of the concept.

- Rain, wind and frost with thresholds, hysteresis and waits in both directions; unavailable sensors keep
  the last state. Water protection (on by default): rain with a tilted/open window drives to the water
  protection position, limited to the ventilation position by the lock-out protection unless allowed;
  event `autoshutterscontrol_rain_window` once per rain. Rain and wind protection (off by default) drive to
  their positions and win over manual override, self defense and schedules. Frost modes soft (frost
  position), morning, afternoon, hard.
- Lock-out protection hard: rain and wind protection wait too; optional hardware lock entity (switch, lock,
  input boolean) locked while the door is open, global switch Hardware lock.
- Force close/open/ventilate/shading per cover (above everything, back to target when off), pause entity,
  party (global switch, participation per cover), advent (evening closing deferred from the 1st Sunday of
  Advent until 6 January or 2 February, release by button or action), external trigger with two values,
  wiggle (button, action).
- Extra conditions (all drives, open, close, ventilate, shading) and actions (each drive, manual drive,
  end of override, water protection) with the Home Assistant editors.
- New entities: switches Party, Advent, Hardware lock; binary sensors Rain, Wind, Frost; buttons Wiggle all,
  Release deferred drives; per cover binary sensors Rain/Water/Wind/Frost protection and Force function,
  button Wiggle. New actions `wiggle` and `release_deferred`.
- Direction rules and extra conditions do not apply to force and protections.

## 0.3.0b1

Stage 3 of the concept.

- Residents: house status (global, profile or cover) and room status (per cover) from persons, device
  trackers, zones, bed/sleep sensors, alarm panels, sensors and selects, with own value mapping, "gone" after
  hours away and last known state while unavailable. Sleep closes to the sleep position, waking up opens;
  morning drive, ventilation and shading wait while asleep unless allowed. Morning/evening drive always,
  only when someone / nobody is at home, or never. New mode "Residents" for the morning/evening drive.
- Self defense (global switch, off by default): covers with an open or tilted window (optionally all) close
  when the residents are gone, or absent after a delay; wins over lock-out protection and manual override.
- Shading: sun direction, sun elevation, brightness (with average), outdoor/indoor temperature, forecast
  temperature (sensor or weather daily forecast), weather condition, own binary sensor; Must and Or lists;
  hysteresis for brightness and temperatures; ASC state machine with start/end waits, end at once when the
  sun leaves; time window, presence mode, alternative position, only downwards, back to target only from the
  shading position; heat protection until the evening.
- Slats: tilt position per drive, up to 4 shading steps by sun elevation, order (after wait, at standstill,
  slats first), time limit, close first, tolerance, own slat entity.
- New entities: switches Shading and Self defense, sensor House status; per cover sensors Residents and
  Shading, binary sensor Self defense, select Shading, number Shading position.

## 0.2.0b1

Stage 2 of the concept.

- Morning/evening modes brightness, sun elevation, and brightness + sun elevation (OR/AND): drive as soon
  as the condition holds for the minimum duration between earliest and latest time; the latest time is
  the deadline. Elevation threshold fixed, from a sensor, or sensor + offset.
- Calendar as source of the earliest/latest times (event titles for opening and closing).
- Window contacts per cover (open, tilted, three-state sensor): ventilation, full ventilation with the
  global switch Comfort, back to target or previous position, delays, lock-out protection (drive is done
  when the door is closed). New sensor Window.
- Privacy before the evening and/or morning drive, and in the evening by brightness. New sensor Next
  privacy.

## 0.1.0b1

First beta, stage 1 of the concept.

- One main entry, profiles and covers as subentries; every setting inherits cover → profile → global → default.
- Schedule: time or sun (real, civil, nautical, astronomical twilight, own elevation) with offset,
  earliest/latest times for workdays and days off, workday sensors for today and tomorrow, evening by
  tomorrow's day type.
- Arbiter with priorities (prepared for all later functions), direction rules, tolerance.
- Manual override detected by context, ends after a duration, at a time, at the next scheduled drive or by
  hand; blocked drive kinds selectable; manual drive can count as the scheduled drive.
- Fixed and random delay.
- State survives restarts.
- Entities, actions, events, diagnostics, repair issue for a missing cover.
- English and German.
