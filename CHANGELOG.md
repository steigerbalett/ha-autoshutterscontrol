# Changelog

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
