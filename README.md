# AutoShuttersControl for HA

[![Marketplace / HACS Custom](https://img.shields.io/badge/Marketplace%20%7C%20HACS-Custom-41BDF5.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=steigerbalett&repository=ha-autoshutterscontrol&category=integration)
[![Home Assistant 2026.10+](https://img.shields.io/badge/Home%20Assistant-2026.10%2B-41BDF5?logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
[![Release](https://img.shields.io/github/v/release/steigerbalett/ha-autoshutterscontrol?include_prereleases&sort=semver)](https://github.com/steigerbalett/ha-autoshutterscontrol/releases)
[![Downloads](https://img.shields.io/github/downloads/steigerbalett/ha-autoshutterscontrol/total?label=downloads)](https://github.com/steigerbalett/ha-autoshutterscontrol/releases)
[![Downloads of the latest release](https://img.shields.io/github/downloads-pre/steigerbalett/ha-autoshutterscontrol/latest/total?label=downloads%20latest)](https://github.com/steigerbalett/ha-autoshutterscontrol/releases)
[![Tests](https://github.com/steigerbalett/ha-autoshutterscontrol/actions/workflows/tests.yml/badge.svg)](https://github.com/steigerbalett/ha-autoshutterscontrol/actions/workflows/tests.yml)
[![Validate](https://github.com/steigerbalett/ha-autoshutterscontrol/actions/workflows/validate.yml/badge.svg)](https://github.com/steigerbalett/ha-autoshutterscontrol/actions/workflows/validate.yml)
[![License GPL-2.0-or-later](https://img.shields.io/github/license/steigerbalett/ha-autoshutterscontrol)](LICENSE)

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

> **Pre-release.** Version 0.7 contains all five stages of the concept and switching profiles by an entity: schedule (time, sun, brightness,
> sun elevation, calendar, residents, workday), window contacts, residents and self defense, shading,
> slats, privacy, rain/wind/frost, force functions, party, advent, trigger, wiggle, extra conditions and
> actions, catching up after a restart, plausibility check, logbook, diagnostics and import from FHEM.

## Installation

### Marketplace (Home Assistant 2026.11 and newer) / Marketplace (ab Home Assistant 2026.11)

Since Home Assistant 2026.11, HACS is part of Home Assistant as the
[Marketplace](https://www.home-assistant.io/integrations/marketplace/). Until AutoShuttersControl for HA is in
its community catalog, add it as a custom repository. The button does that for you:

Seit Home Assistant 2026.11 ist HACS als Marketplace fest in Home Assistant enthalten. Bis AutoShuttersControl
for HA in dessen Community-Katalog steht, wird es als benutzerdefiniertes Repository hinzugefügt. Der Button
erledigt das:

[![Open your Home Assistant instance and open this repository in the Marketplace / HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=steigerbalett&repository=ha-autoshutterscontrol&category=integration)

1. Open *Settings → Marketplace* as an administrator, or press the button above. /
   Als Administrator *Einstellungen → Marketplace* öffnen oder den Button oben drücken.
2. Without the button: menu (three dots) → *Custom repositories* → `https://github.com/steigerbalett/ha-autoshutterscontrol`, type
   *Integration*. / Ohne Button: Menü (drei Punkte) → *Benutzerdefinierte Repositories* →
   `https://github.com/steigerbalett/ha-autoshutterscontrol`, Typ *Integration*.
3. Versions 0.x are pre-releases: switch on *Show beta versions* for the repository. / Versionen 0.x sind
   Pre-Releases: beim Repository *Beta-Versionen anzeigen* einschalten.
4. Install *AutoShuttersControl for HA* and restart Home Assistant. / Installieren und Home Assistant neu
   starten.
5. *Settings → Devices & services → Add integration → AutoShuttersControl for HA*.

### HACS (Home Assistant 2026.10)

The same steps in HACS. / Die gleichen Schritte in HACS.

### Manual / Von Hand

Download `autoshutterscontrol.zip` from the [releases](https://github.com/steigerbalett/ha-autoshutterscontrol/releases), unpack it into
`config/custom_components/autoshutterscontrol` and restart Home Assistant. / `autoshutterscontrol.zip` aus den
Releases laden, nach `config/custom_components/autoshutterscontrol` entpacken und Home Assistant neu starten.

License: GPL-2.0-or-later. No code from FHEM ASC or from the blueprint "Cover Control Automation"
is used; both served as a list of functions.
