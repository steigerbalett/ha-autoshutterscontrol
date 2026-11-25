# AutoShuttersControl for HA

One integration for all covers in Home Assistant: open in the morning, close in the evening,
detect manual drives, and inherit every setting from global to profile to cover.
It rebuilds the functions of the FHEM module AutoShuttersControl (ASC) in Python and replaces
per-cover blueprint automations.

Eine Integration für alle Rollläden in Home Assistant: morgens öffnen, abends schließen,
Handfahrten erkennen und jede Einstellung von global über Profil bis zum Rollladen erben.
Sie baut die Funktionen des FHEM-Moduls AutoShuttersControl (ASC) in Python nach und ersetzt
Blueprint-Automationen je Rollladen.

- 🇬🇧 [Documentation (English)](docs/en/README.md)
- 🇩🇪 [Dokumentation (Deutsch)](docs/de/README.md)

> **Beta.** Version 0.1 is stage 1 of 5: schedule (time, sun, workday), positions, manual
> override, delays. Ventilation, shading, residents, weather protection and more follow.

License: GPL-2.0-or-later. No code from FHEM ASC or from the blueprint "Cover Control Automation"
is used; both served as a list of functions.
