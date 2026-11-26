# Setup step by step

This guide takes you from installing to the first cover that opens by itself in the morning and closes in
the evening. The first steps take about 15 minutes. Everything else can be switched on later, one by one. All
settings are described in full in the [documentation](README.md).

**Contents**

1. [Before you start](#1-before-you-start)
2. [Install](#2-install)
3. [Add the integration](#3-add-the-integration)
4. [Check the global settings](#4-check-the-global-settings)
5. [Add covers](#5-add-covers)
6. [Test first: simulation](#6-test-first-simulation)
7. [Profiles for groups of covers](#7-profiles-for-groups-of-covers)
8. [Adjust one cover](#8-adjust-one-cover)
9. [Recipes for typical rooms](#9-recipes-for-typical-rooms)
10. [Moving from FHEM](#10-moving-from-fhem)
11. [The overview](#11-the-overview)
12. [When something does not work](#12-when-something-does-not-work)

## How it works in one sentence

Every setting exists on three levels: **global** (for the whole house), in a **profile** (for a group, e.g.
"South side") and on the **cover**. The cover always takes the nearest value that is set: cover → profile →
global → default. So you set most things once globally and enter on the cover only what is different there.
An empty field means "inherit", and the line `↳` below the field shows what is inherited.

## 1. Before you start

All you need is a cover in Home Assistant that knows its position (a `cover` entity with a position of
0–100 %). Everything else is optional and can be added later:

| What | For | Without |
|---|---|---|
| **Workday** integration | other times on weekends and holidays | Monday to Friday are workdays |
| **Brightness sensor** (lx) | opening and closing by brightness, shading | the position of the sun is used |
| **Window contacts** | ventilation, lock-out protection at the patio door | no window functions |
| **Persons** or a sleep mode | open only when someone is awake | drives by time and sun |
| **Outdoor temperature**, weather | shading when it is hot, frost protection | shading by sun and brightness only |
| Rain and wind sensor | rain and wind protection | no weather protection |

Tip: add the Workday integration twice, once for today and once with a day offset of 1 for tomorrow. Then
AutoShuttersControl knows in the evening whether you sleep in tomorrow.

## 2. Install

1. Open *Settings → Marketplace* (Home Assistant 2026.11 and newer, before that it is called HACS).
2. The three dots at the top right → *Custom repositories*.
3. Enter `https://github.com/steigerbalett/ha-autoshutterscontrol`, type *Integration*.
4. Versions 0.x are pre-releases: switch on *Show beta versions* for the repository.
5. Install *AutoShuttersControl for HA* and restart Home Assistant.

The button in the [README](../../README.md#english) is quicker.

## 3. Add the integration

1. *Settings → Devices & services → Add integration* → **AutoShuttersControl for HA**.
2. A form with the **sensors for the whole house** appears. Choose what you have. Leaving fields empty is
   fine:
   - *Workday sensor (today)* and *(tomorrow)*: the Workday binary sensors.
   - *Brightness sensor*: an outdoor sensor in lx.
   - *Outdoor temperature*, *Weather*, *Rain sensor*, *Wind speed*: for shading and weather protection.
3. *Submit*. Now there is the entry **AutoShuttersControl** with a central device. It holds the switches for
   the whole house, e.g. *Automatic*, *Pause*, *Shading*, *Holiday* and *Simulation*.

There is always only **one** entry for the whole house. Covers and profiles belong to it.

## 4. Check the global settings

Click **Configure** on the entry. You see a menu of pages. Two are enough to start with:

**Schedule**

- *Morning drive by* and *Evening drive by*: the default is **Sun**. The cover opens at sunrise
  and closes at sunset, but never before the *earliest* and never after the *latest* time.
- Default on workdays: open between 05:00 and 08:30, close between 16:00 and 22:00. Days off have their own
  times.
- Prefer fixed times? Set the mode to **Time**. Then the cover drives at the earliest time.
- With a brightness sensor: mode **Brightness**, plus the thresholds *Open from* and *Close below* on the page
  *Brightness and sun elevation*.

**Positions**

- *Open position* (default 100 %) and *Closed position* (default 0 %). Many covers like to leave a small gap
  when closed, e.g. 10 %.

Important: changes on the pages are only kept when you click **💾 Save and close** in the menu at the end. If
you close the dialog with the X before that, they are lost.

## 5. Add covers

1. Click **Add covers** on the entry.
2. Choose one or several covers at once. You do not need a profile yet.
3. *Submit*. Each cover gets its own entities, e.g. *Next opening*, *Next closing*, *Target*, the
   switches *Automatic* and *Pause* and the button *Drive to target*.

If the cover has its own device in Home Assistant, these entities appear right on that device.

From now on the cover drives by the global schedule.

## 6. Test first: simulation

Do you want to see what would happen first, without anything moving?

1. Switch on **Simulation** on the central device (or on the cover for just that one).
2. AutoShuttersControl decides as usual but does not drive. The logbook then says e.g. "would drive to 0 %
   (evening), simulation", and the sensor *Simulated drive* shows the last decision.
3. When everything fits, switch the simulation off again.

You can always see the current plan on the sensors *Next opening* and *Next closing*.

## 7. Profiles for groups of covers

A profile is worth it as soon as several covers share the same difference, e.g. all windows facing south with
shading, or all bedrooms opening later.

1. Click **Add profile** on the entry and enter a name, e.g. "South side".
2. Open the pages in the menu and enter only what is different for this group. Empty fields inherit from
   global.
3. **💾 Save and close**.
4. On the cover (three dots → *Reconfigure*) → *Name and profile* → choose the profile "South side" and save.

## 8. Adjust one cover

On the cover, click the three dots → **Reconfigure**. You see the same menu as globally. Enter only what is
different for this one cover, then click **💾 Save and close**.

Fields that exist only on the cover:

- Page *Window contacts*: *Contact "open"*, *Contact "tilted"* or a *window sensor with three states*.
- Page *Residents and self defense*: *Sources of the room status* (e.g. the persons sleeping here) and *Guests in this room*.
- Page *Shading*: *Horizon of the window*, *Window sill above the floor* and *Window height*.
- Menu item *Import from FHEM*: the settings of one FHEM shutter, see
  [Moving from FHEM](#10-moving-from-fhem).

*Back to the inherited value* clears fields again.

## 9. Recipes for typical rooms

### Bedroom: open only when everybody is awake

1. Globally on the page *Residents and self defense*: *Sources of the house status* = your persons.
2. On the bedroom cover, page *Residents and self defense*: *Sources of the room status* = e.g. an input boolean "Sleep mode"
   or a bed sensor (on = asleep).
3. Page *Schedule*: *Morning drive by* = **Residents (when awake)**. The cover opens as soon as the
   sleep mode turns off, but at the latest time at the latest.

### South side: shading in sun and heat

1. Add the profile "South side" and assign it to the covers.
2. In the profile, page *Shading*: *Shading* = **Always**. Adjust *Sun direction from/to* to the facade, e.g.
   135° to 225° for south.
3. Globally there are sensible thresholds already: from 35000 lx and from 18 °C outside. Without a brightness
   sensor only the sun position and the temperature count.
4. Page *Positions*: *Shading position*, e.g. 30 %.

On the cover the button **Sun has left the window** helps: press it when the sun disappears behind the
neighbour's house. Then AutoShuttersControl knows where the horizon of this window is.

### Patio door: do not lock anyone out

1. On the cover, page *Window contacts*: enter the door contact.
2. *Lock-out protection* = **Soft**: while the door is open, the cover does not go down. The drive is caught
   up as soon as the door is closed. **Hard** also makes rain and wind protection wait.

### Winter: other times as soon as it is cold

1. Add the profile "Winter", e.g. with earlier closing.
2. On the cover, *Name and profile*: *Alternative profile* = "Winter" and *Entity for the alternative
   profile* = the binary sensor **Winter** of the central device. It turns on when the 24 hour mean of the
   outdoor temperature is below 12 °C.
3. Instead of the sensor a fixed period works too, e.g. *from* `1.11.` *to* `31.3.`.

### Holiday: look lived in

Switch on **Holiday** on the central device. The morning and evening drives then shift every day by up to
30 random minutes, differently for each cover.

### School holidays: open later during the holidays

Two ways, depending on what you already have:

1. **Workday sensor in a profile**: add a template binary sensor that is off during the holidays, e.g. from a
   holiday calendar: `{{ is_state('binary_sensor.workday_sensor', 'on') and is_state('calendar.school_holidays', 'off') }}`.
   Add a profile "Children's rooms" and enter it there on the page *Sensors* as *Workday sensor (today)*. Then
   these covers use the times of days off during the holidays, all others do not.
2. **Alternative profile with a calendar**: add a profile "Holidays" with later earliest and latest opening.
   On the cover, *Name and profile*: *Alternative profile* = "Holidays", *Entity for the alternative profile* =
   the calendar with the holidays (e.g. `calendar.school_holidays`, it is on while an event runs). For fixed
   holidays the period *from*/*to* works as well.

### Smoke detector: everything up in an emergency

1. *Configure* → *Special functions*: *Emergency input* = your smoke detectors (binary sensors).
2. When one turns on, all covers open (*Emergency position*, default 100 %) and awnings retract, even with
   automatic off or pause.
3. Afterwards press **Reset emergency** on the central device. Only then the covers drive normally again.

## 10. Moving from FHEM

Your settings from ASC in FHEM can be taken over. The names in FHEM and in Home Assistant may differ, because
you choose the mapping yourself. Only settings are taken over, that is the `attr` lines. Perl code and a few
FHEM-only attributes cannot be transferred. They are listed at the end.

### Everything at once

1. In FHEM, enter in the command line at the top:
   - `list -r TYPE=AutoShuttersControl` (the ASC device with the global settings)
   - `list -r ASC=[12]` (all shutters with the attribute ASC 1 or 2)
2. Select and copy the output of both commands. The whole `fhem.cfg` works as well.
3. In Home Assistant: AutoShuttersControl → **Configure** → **Import from FHEM** → paste the text.
4. Map each FHEM shutter to a cover in Home Assistant. Suggestions come from similar names. Empty means "do not
   take over".
5. Map the FHEM devices (sensors, window contacts, residents) to entities.
6. The summary shows what happens. If covers are already set up, you can choose whether they are updated with
   the FHEM values. *Submit* creates the other covers and saves the global settings.

Values that all shutters share go to the global settings. Values that only repeat the default are dropped. So
the cover keeps only what is really different.

### One single shutter

This is how you take over the settings of one FHEM shutter for a cover that already exists in Home Assistant:

1. In FHEM: `list -r` followed by the name of the shutter in FHEM, e.g. `list -r EG_Wohnzimmer_Rollo`. Copy the
   whole output.
2. In Home Assistant, on the cover click the three dots → *Reconfigure* → **Import from FHEM** → paste the
   text.
3. If the text contains several shutters, choose the right one.
4. Map the devices (e.g. the window contact).
5. The list shows every setting that is taken over. Optionally *Delete the own values of this cover first*.
6. *Submit* and then **💾 Save and close**.

Tip: do not let FHEM and Home Assistant both control the same cover. Otherwise each side takes the drives of
the other for a manual drive. Set the attribute `ASC` of the shutter to 0 in FHEM as soon as it runs in Home
Assistant.

## 11. The overview

**Configure** → **Overview** shows all covers with position, target, next drives, last drive, shading and
window, and below that all linked sensors with their current value. A ❗ marks an entity that does not exist.

The Home Assistant dialog is narrow. The page in the sidebar has more room: *Configure* → *Drive behaviour* →
switch on **Overview in the sidebar** and save. Then the sidebar has the item *AutoShuttersControl* with a
large table that refreshes every 10 seconds.

The same page has the tab **Edit covers**. It lists all covers in a table. You can add, duplicate and remove
covers and change several at once: tick them, *Edit selected*, change only the fields that should apply to all,
and save.

For dashboards there is the card **AutoShuttersControl**: *Edit dashboard* → *Add card* → *Custom*. It shows
every cover with position, target and reason, the next drives and buttons. Reload the page once after
installing so that the card appears in the list.

## 12. When something does not work

**The cover does not drive.** Look at the sensor *Not driven because* of the cover. It shows the reason, e.g.
"window open", "manual override" or "pause". The logbook of the cover shows every decision.

**It no longer drives after a manual drive.** That is intended: after a drive by hand the automation pauses
(default 20 minutes). The button *End manual override* lifts that at once.

**The times are wrong.** Check the mode and the earliest and latest times on the page *Schedule*. The button
*Recalculate times* on the central device recalculates at once.

**The diagnostic sensor *Stuck* is on.** The cover did not reach its position after a drive. If it does not
report its position reliably, switch off *Check every drive* for this cover on the page *Drive behaviour*.

**Where does a value come from?** The sensor *Target* shows every effective value in the attribute
`effective_config` and whether it comes from the cover, the profile, global or the default.

**I want to stop everything for a moment.** Switch *Pause* (afterwards the cover drives to its target state)
or *Automatic* off (nothing happens at all), globally or per cover.

More questions are answered in the [documentation](README.md#faq).
