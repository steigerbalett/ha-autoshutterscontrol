# Changelog

## 0.7.1

- Water protection: when it is dry again or the window is closed, the cover goes back to its position from
  before the water protection, unless another target applies by now (other drive, shading, manual
  override). New setting *Back after the rain* (previous position / target state, default previous
  position). New drive reason "After the rain".
- Workflow "Release draft": after every push to main a draft release for the version in manifest.json, with
  the CHANGELOG section as notes. Versions 0.x and betas are marked as pre-release.

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
