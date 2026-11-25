"""Table tests of stage 3: residents, self defense, shading, slats."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.autoshutterscontrol.engine.arbiter import (
    BLOCK_DIRECTION,
    BLOCK_NO_WISH,
    BLOCK_NOT_SHADED,
    REASON_HEAT,
    REASON_SELF_DEFENSE,
    REASON_SHADING,
    REASON_SLEEP,
    TRIGGER_APPLY_TARGET,
    TRIGGER_SCHEDULE_UP,
    TRIGGER_SHADING,
    TRIGGER_SHADING_END,
    TRIGGER_WINDOW,
    Situation,
    build_wishes,
    decide,
)
from custom_components.autoshutterscontrol.engine.residents import (
    Source,
    combine,
    map_source,
    parse_map,
    presence_allows,
    self_defense_due,
    status,
)
from custom_components.autoshutterscontrol.engine.resolve import resolve
from custom_components.autoshutterscontrol.engine.shading import (
    IN,
    IN_RESERVED,
    OUT,
    OUT_RESERVED,
    Configured,
    Inputs,
    average,
    combine as shading_combine,
    conditions,
    heat_active,
    in_azimuth,
    in_time_window,
    step,
    sun_left,
)
from custom_components.autoshutterscontrol.engine.sun import Location, SunCalculator
from custom_components.autoshutterscontrol.engine.tilt import parse_steps, shading_tilt, tilt_for

TZ = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 6, 20, 13, 0, tzinfo=TZ)


def cfg(**values):
    from custom_components.autoshutterscontrol.engine.settings import BY_KEY, to_storage

    return resolve({k: to_storage(BY_KEY[k], v) for k, v in values.items()})


# --- residents ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("entity", "state", "expected"),
    [
        ("person.a", "home", "home"),
        ("person.a", "not_home", "absent"),
        ("person.a", "work", "absent"),
        ("device_tracker.p", "home", "home"),
        ("zone.home", "0", "absent"),
        ("zone.home", "2", "home"),
        ("binary_sensor.bed", "on", "asleep"),
        ("binary_sensor.bed", "off", "awoken"),
        ("input_boolean.sleep", "on", "asleep"),
        ("alarm_control_panel.a", "armed_away", "gone"),
        ("alarm_control_panel.a", "armed_night", "asleep"),
        ("alarm_control_panel.a", "disarmed", "home"),
        ("input_select.mode", "gotosleep", "gotosleep"),
        ("sensor.x", "whatever", None),
    ],
)
def test_map_source(entity, state, expected) -> None:
    assert map_source(Source(entity, state), {}, NOW, 0) == expected


def test_gone_after_hours_and_own_map() -> None:
    old = Source("person.a", "not_home", NOW - timedelta(hours=30))
    assert map_source(old, {}, NOW, 24) == "gone"
    assert map_source(old, {}, NOW, 0) == "absent"
    own = parse_map("Schlafen:asleep, Urlaub : gone; junk, x:invalid")
    assert own == {"schlafen": "asleep", "urlaub": "gone"}
    assert map_source(Source("input_select.m", "Urlaub"), own, NOW, 0) == "gone"


def test_combine_priority() -> None:
    assert combine(["home", "asleep", "absent"]) == "asleep"
    assert combine(["absent", "gone"]) == "absent"
    assert combine(["awoken", "home"]) == "awoken"
    assert combine([None]) is None
    sources = [Source("person.a", "not_home"), Source("person.b", "home")]
    assert status(sources, {}, NOW, 0) == "home"


@pytest.mark.parametrize(
    ("mode", "house", "expected"),
    [
        ("always", "absent", True),
        ("home", "home", True),
        ("home", "asleep", True),
        ("home", "absent", False),
        ("absent", "gone", True),
        ("absent", "home", False),
        ("off", "home", False),
        ("home", None, True),
        ("off", None, False),
    ],
)
def test_presence_allows(mode, house, expected) -> None:
    assert presence_allows(mode, house) is expected


def test_self_defense_due() -> None:
    gone = cfg(self_defense_mode="gone")
    absent = cfg(self_defense_mode="absent", self_defense_delay=5)
    assert self_defense_due(gone, "gone", None, NOW)
    assert not self_defense_due(gone, "absent", NOW - timedelta(hours=1), NOW)
    assert self_defense_due(absent, "gone", None, NOW)
    assert not self_defense_due(absent, "absent", NOW - timedelta(minutes=4), NOW)
    assert self_defense_due(absent, "absent", NOW - timedelta(minutes=5), NOW)
    assert not self_defense_due(cfg(self_defense_mode="off"), "gone", None, NOW)


# --- shading conditions --------------------------------------------------------


def test_in_azimuth() -> None:
    assert in_azimuth(180, 105, 255)
    assert not in_azimuth(90, 105, 255)
    # Across north
    assert in_azimuth(350, 300, 30)
    assert in_azimuth(10, 300, 30)
    assert not in_azimuth(180, 300, 30)


SUNNY = Inputs(azimuth=180, elevation=40, brightness=50000, temp_out=25)
ALL = Configured(brightness=True, temp_out=True)


def test_conditions_and_hysteresis() -> None:
    c = cfg()
    start = conditions(c, SUNNY, ALL, active=False)
    assert start["azimuth"] and start["elevation"] and start["brightness"] and start["temp_out"]
    assert start["temp_in"] is None  # no sensor
    assert shading_combine(c, start)
    # 25000 lx: not enough to start, but enough to stay (end below 20000)
    cloudy = Inputs(azimuth=180, elevation=40, brightness=25000, temp_out=25)
    assert not shading_combine(c, conditions(c, cloudy, ALL, active=False))
    assert shading_combine(c, conditions(c, cloudy, ALL, active=True))
    # Temperature hysteresis 1 K: 17.5 °C keeps shading, 16.9 ends it
    cool = Inputs(azimuth=180, elevation=40, brightness=50000, temp_out=17.5)
    assert not shading_combine(c, conditions(c, cool, ALL, active=False))
    assert shading_combine(c, conditions(c, cool, ALL, active=True))
    cold = Inputs(azimuth=180, elevation=40, brightness=50000, temp_out=16.9)
    assert not shading_combine(c, conditions(c, cold, ALL, active=True))


def test_unavailable_sensor_starts_nothing_but_keeps_shading() -> None:
    c = cfg()
    missing = Inputs(azimuth=180, elevation=40, brightness=None, temp_out=25)
    assert not shading_combine(c, conditions(c, missing, ALL, active=False))
    assert shading_combine(c, conditions(c, missing, ALL, active=True))


def test_unconfigured_conditions_are_ignored() -> None:
    c = cfg()
    only_sun = Inputs(azimuth=180, elevation=40)
    assert shading_combine(c, conditions(c, only_sun, Configured(), active=False))


def test_any_list() -> None:
    c = cfg(shading_must=["azimuth", "elevation"], shading_any=["brightness", "temp_in"])
    configured = Configured(brightness=True, temp_in=True)
    c2 = cfg(
        shading_must=["azimuth", "elevation"],
        shading_any=["brightness", "temp_in"],
        shading_temp_in_min=24,
    )
    warm_inside = Inputs(azimuth=180, elevation=40, brightness=1000, temp_in=26)
    assert shading_combine(c2, conditions(c2, warm_inside, configured, active=False))
    dark_cool = Inputs(azimuth=180, elevation=40, brightness=1000, temp_in=20)
    assert not shading_combine(c2, conditions(c2, dark_cool, configured, active=False))
    # temp_in without threshold is ignored, brightness alone decides
    assert not shading_combine(c, conditions(c, dark_cool, configured, active=False))


def test_weather_forecast_sensor() -> None:
    c = cfg(shading_forecast_min=22)
    conf = Configured(forecast=True, weather=True, sensor=True)
    good = Inputs(azimuth=180, elevation=40, forecast=24, weather="sunny", sensor=True)
    assert shading_combine(c, conditions(c, good, conf, active=False))
    for bad in (
        Inputs(azimuth=180, elevation=40, forecast=20, weather="sunny", sensor=True),
        Inputs(azimuth=180, elevation=40, forecast=24, weather="rainy", sensor=True),
        Inputs(azimuth=180, elevation=40, forecast=24, weather="sunny", sensor=False),
    ):
        assert not shading_combine(c, conditions(c, bad, conf, active=False))


def test_sun_left() -> None:
    c = cfg()
    assert sun_left(conditions(c, Inputs(azimuth=270, elevation=40), Configured(), True))
    assert sun_left(conditions(c, Inputs(azimuth=180, elevation=10), Configured(), True))
    assert not sun_left(conditions(c, Inputs(azimuth=180, elevation=40), Configured(), True))


def test_time_window() -> None:
    assert in_time_window(cfg(), time(3, 0))
    c = cfg(shading_time_start=time(10, 0), shading_time_end=time(17, 0))
    assert in_time_window(c, time(12, 0))
    assert not in_time_window(c, time(9, 59))


# --- state machine ---------------------------------------------------------------


def run(c, state, since, minutes, **kw):
    return step(c, state, since, NOW + timedelta(minutes=minutes), **kw)


def test_state_machine_with_delays() -> None:
    c = cfg(shading_delay_start=10, shading_delay_end=20)
    ok = {"start_ok": True, "still_ok": True, "left": False}
    state, since = run(c, OUT, None, 0, **ok)
    assert (state, since) == (IN_RESERVED, NOW)
    assert run(c, state, since, 9, **ok)[0] == IN_RESERVED
    state, since = run(c, state, since, 10, **ok)
    assert state == IN
    # Clouds: still ok with hysteresis
    assert run(c, state, since, 30, start_ok=False, still_ok=True, left=False)[0] == IN
    state, since = run(c, state, since, 40, start_ok=False, still_ok=False, left=False)
    assert state == OUT_RESERVED
    # Sun back within the end delay
    assert run(c, state, since, 50, **ok)[0] == IN
    assert run(c, state, since, 59, start_ok=False, still_ok=False, left=False)[0] == OUT_RESERVED
    assert run(c, state, since, 60, start_ok=False, still_ok=False, left=False)[0] == OUT


def test_state_machine_reserved_drops_back_and_sun_leaves() -> None:
    c = cfg(shading_delay_start=10, shading_delay_end=20)
    assert run(c, IN_RESERVED, NOW, 5, start_ok=False, still_ok=False, left=False)[0] == OUT
    # Sun leaves the area: end at once
    assert run(c, IN, NOW, 5, start_ok=False, still_ok=False, left=True)[0] == OUT
    c2 = cfg(shading_end_sun_leaves=False)
    assert run(c2, IN, NOW, 5, start_ok=False, still_ok=False, left=True)[0] == OUT_RESERVED
    # Not allowed (night, switch off, mode)
    assert run(c, IN, NOW, 1, start_ok=True, still_ok=True, left=False, allowed=False)[0] == OUT


def test_state_machine_without_delays() -> None:
    c = cfg(shading_delay_start=0, shading_delay_end=0)
    assert run(c, OUT, None, 0, start_ok=True, still_ok=True, left=False)[0] == IN
    assert run(c, IN, NOW, 1, start_ok=False, still_ok=False, left=False)[0] == OUT


def test_heat_and_average() -> None:
    c = cfg(heat_protection_temp=28)
    assert not heat_active(cfg(), 40, False)
    assert heat_active(c, 29, False)
    assert not heat_active(c, 27, False)
    assert heat_active(c, 20, True)
    samples = [(NOW - timedelta(minutes=m), v) for m, v in ((20, 0), (5, 100), (1, 200))]
    assert average(samples, NOW, 10) == 150
    assert average(samples, NOW, 0) == 200
    assert average([], NOW, 10) is None


# --- slats -------------------------------------------------------------------------


def test_tilt() -> None:
    assert parse_steps("50:30, 20:70; 35:50, bad, 60:x, 70:120, 80:0") == [
        (20.0, 70),
        (35.0, 50),
        (50.0, 30),
        (70.0, 100),
    ]
    c = cfg(tilt_shading=80, tilt_shading_steps="20:70, 35:50, 50:30", tilt_closed=0)
    assert shading_tilt(c, 10) == 80
    assert shading_tilt(c, 36) == 50
    assert shading_tilt(c, 60) == 30
    assert tilt_for(c, REASON_SHADING, 40) == 50
    assert tilt_for(c, REASON_HEAT, 10) == 80
    assert tilt_for(c, "night_close") == 0
    assert tilt_for(c, REASON_SLEEP) == 0  # falls back to closed
    assert tilt_for(c, "day_open") is None
    assert tilt_for(c, "service") is None
    assert tilt_for(c, None, named="closed") == 0


# --- arbiter ---------------------------------------------------------------------


def target(c, **kw):
    trigger = kw.pop("trigger", TRIGGER_APPLY_TARGET)
    current = kw.pop("current", None)
    sit = Situation(trigger=trigger, current_position=current, lockout=kw.pop("lockout", False))
    wishes = build_wishes(c, trigger=trigger, current=current, **kw)
    return decide(c, sit, wishes)


def test_sleep_closes_and_blocks_open_and_ventilate() -> None:
    c = cfg(pos_sleep=10)
    d = target(c, is_day=True, sleeping=True, current=100)
    assert (d.drive, d.position, d.reason) == (True, 10, REASON_SLEEP)
    # Window tilted while asleep: no ventilation
    d = target(c, is_day=False, sleeping=True, window=(50, "ventilate"), current=10)
    assert d.reason == REASON_SLEEP
    c2 = cfg(sleep_allow_ventilate=True)
    d = target(c2, is_day=False, sleeping=True, window=(50, "ventilate"), current=0)
    assert d.reason == "ventilate"
    # sleep_close off: the morning drive waits
    c3 = cfg(sleep_close=False)
    d = target(c3, is_day=True, sleeping=True, trigger=TRIGGER_SCHEDULE_UP, current=0)
    assert d.blocked_by == BLOCK_NO_WISH
    d = target(cfg(sleep_close=False, sleep_allow_open=True), is_day=True, sleeping=True, current=0)
    assert d.reason == "day_open"


def test_self_defense_wins_over_lockout_and_window() -> None:
    c = cfg(lockout="soft")
    d = target(
        c, is_day=True, self_defense=True, window=(50, "ventilate"), current=100, lockout=True
    )
    assert (d.drive, d.position, d.reason) == (True, 0, REASON_SELF_DEFENSE)


def test_shading_wish_rules() -> None:
    c = cfg()
    d = target(c, is_day=True, shaded=True, current=100, trigger=TRIGGER_SHADING)
    assert (d.drive, d.position, d.reason) == (True, 30, REASON_SHADING)
    # Not at night
    d = target(c, is_day=False, shaded=True, current=0)
    assert d.reason == "night_close"
    # Only down: a lower cover stays
    d = target(c, is_day=True, shaded=True, current=10, trigger=TRIGGER_SHADING)
    assert d.blocked_by == BLOCK_DIRECTION
    # Alternative position
    d = target(cfg(pos_shading_alt=15), is_day=True, shaded=True, shading_alt=True, current=100)
    assert d.position == 15
    # Heat protection
    d = target(c, is_day=True, heat=True, current=100)
    assert d.reason == REASON_HEAT
    # Shading trigger never starts another drive
    d = target(c, is_day=True, shaded=False, current=0, trigger=TRIGGER_SHADING)
    assert d.blocked_by == BLOCK_NO_WISH
    # Window beats shading (ventilation is higher than the shading position)
    d = target(c, is_day=True, shaded=True, window=(50, "ventilate"), current=100)
    assert d.reason == "ventilate"


def test_shading_end() -> None:
    c = cfg()
    d = target(c, is_day=True, current=30, trigger=TRIGGER_SHADING_END)
    assert (d.drive, d.position) == (True, 100)
    d = target(c, is_day=True, current=60, trigger=TRIGGER_SHADING_END)
    assert d.blocked_by == BLOCK_NOT_SHADED
    d = target(cfg(shading_end_open=False), is_day=True, current=30, trigger=TRIGGER_SHADING_END)
    assert d.blocked_by == BLOCK_NO_WISH


def test_window_trigger_does_not_start_shading() -> None:
    c = cfg()
    d = target(
        c, is_day=True, shaded=True, window=(50, "ventilate"), current=60, trigger=TRIGGER_WINDOW
    )
    assert d.source == "window"


def test_azimuth_from_sun() -> None:
    sun = SunCalculator(Location(51.35, 8.57, 450, TZ))
    noon = sun.azimuth(datetime(2026, 6, 20, 13, 30, tzinfo=TZ))
    assert 170 < noon < 190
    assert sun.azimuth(datetime(2026, 6, 20, 8, 0, tzinfo=TZ)) < 120
