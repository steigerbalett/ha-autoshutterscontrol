# Changelog

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
