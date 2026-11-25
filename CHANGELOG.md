# Changelog

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
