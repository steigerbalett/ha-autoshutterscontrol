"""Engine tests of stage 4: protection, advent, trigger, wiggle."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest

from custom_components.autoshutterscontrol.engine import period, protection as p, special

NOW = datetime(2026, 11, 25, 12, 0)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("on", True), ("off", False), ("0.4", 0.4), ("unknown", None), (None, None), ("dry", False)],
)
def test_as_value(raw, expected) -> None:
    assert p.as_value(raw) == expected


def test_above_with_hysteresis() -> None:
    assert p.above(0.5, 0.0, 0.0, False) is True
    assert p.above(0.0, 0.0, 0.0, False) is False
    assert p.above(True, 5.0, 0.0, False) is True
    assert p.above(None, 0.0, 0.0, True) is None
    assert p.above(1.5, 2.0, 1.0, True) is True
    assert p.above(1.5, 2.0, 1.0, False) is False


def test_wind_and_frost_thresholds() -> None:
    assert p.at_least(50, 50, 20, False) is True
    assert p.at_least(35, 50, 20, True) is True
    assert p.at_least(29, 50, 20, True) is False
    assert p.at_least(True, 50, 20, False) is None
    assert p.below(2.0, 2.0, 1.0, False) is True
    assert p.below(2.5, 2.0, 1.0, True) is True
    assert p.below(3.5, 2.0, 1.0, True) is False


def test_step_waits_both_ways() -> None:
    state = p.Protection()
    state = p.step(state, True, NOW, 2, 15)
    assert state == p.Protection(False, NOW)
    state = p.step(state, True, NOW + timedelta(minutes=2), 2, 15)
    assert state == p.Protection(True, None)
    state = p.step(state, None, NOW + timedelta(minutes=3), 2, 15)
    assert state.active
    state = p.step(state, False, NOW + timedelta(minutes=4), 2, 15)
    assert state.active and state.pending_since is not None
    # Rain again: the end wait starts over
    state = p.step(state, True, NOW + timedelta(minutes=10), 2, 15)
    assert state == p.Protection(True, None)
    assert p.step(p.Protection(), True, NOW, 0, 0).active


@pytest.mark.parametrize(
    ("mode", "clock", "expected"),
    [
        ("off", time(8), (False, False)),
        ("hard", time(18), (True, False)),
        ("am", time(8), (True, False)),
        ("am", time(13), (False, False)),
        ("pm", time(8), (False, False)),
        ("pm", time(18), (True, False)),
        ("soft", time(18), (False, True)),
    ],
)
def test_frost_effect(mode, clock, expected) -> None:
    cfg = {"frost_mode": mode, "pos_frost": 20}
    assert p.frost_effect(cfg, True, clock) == expected
    assert p.frost_effect(cfg, False, clock) == (False, False)


def test_frost_soft_needs_position() -> None:
    assert p.frost_effect({"frost_mode": "soft", "pos_frost": None}, True, time(8)) == (
        False,
        False,
    )


@pytest.mark.parametrize(
    ("year", "expected"),
    [(2026, date(2026, 11, 29)), (2022, date(2022, 11, 27)), (2023, date(2023, 12, 3))],
)
def test_first_advent(year, expected) -> None:
    assert special.first_advent(year) == expected
    assert special.first_advent(year).weekday() == 6


def test_advent_active() -> None:
    cfg = {"advent_end": "epiphany"}
    assert not special.advent_active(cfg, date(2026, 11, 28))
    assert special.advent_active(cfg, date(2026, 11, 29))
    assert special.advent_active(cfg, date(2027, 1, 6))
    assert not special.advent_active(cfg, date(2027, 1, 7))
    assert special.advent_active({"advent_end": "candlemas"}, date(2027, 2, 2))


def test_trigger_position() -> None:
    cfg = {
        "trigger_entity": "input_select.mode",
        "trigger_value": "Kino",
        "trigger_position": 0,
        "trigger_value2": "lesen",
        "trigger_position2": 50,
    }
    assert special.trigger_position(cfg, "kino") == 0
    assert special.trigger_position(cfg, "Lesen") == 50
    assert special.trigger_position(cfg, "aus") is None
    assert special.trigger_position({**cfg, "trigger_entity": None}, "kino") is None


def test_wiggle_target() -> None:
    cfg = {"wiggle_value": 5}
    assert special.wiggle_target(cfg, 80) == 75
    assert special.wiggle_target(cfg, 3) == 8


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.11.", (11, 1)),
        ("01.11", (11, 1)),
        ("31-03", (3, 31)),
        ("29.2.", (2, 29)),
        ("31.2.", None),
        ("1.13.", None),
        ("x", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_day(text, expected) -> None:
    assert period.parse_day(text) == expected


def test_in_period() -> None:
    assert period.in_period(date(2026, 12, 31), (11, 1), (3, 31))
    assert period.in_period(date(2027, 1, 1), (11, 1), (3, 31))
    assert not period.in_period(date(2027, 4, 1), (11, 1), (3, 31))
    assert period.in_period(date(2026, 6, 1), (5, 1), (9, 30))
    assert not period.in_period(date(2026, 10, 1), (5, 1), (9, 30))


def test_advent_own_days() -> None:
    cfg = {
        "advent_start": "date",
        "advent_start_date": "1.12.",
        "advent_end": "date",
        "advent_end_date": "15.1.",
    }
    assert not special.advent_active(cfg, date(2026, 11, 30))
    assert special.advent_active(cfg, date(2026, 12, 1))
    assert special.advent_active(cfg, date(2027, 1, 15))
    assert not special.advent_active(cfg, date(2027, 1, 16))
    # First Sunday of Advent until Christmas Eve
    cfg = {"advent_start": "first_advent", "advent_end": "date", "advent_end_date": "24.12."}
    assert not special.advent_active(cfg, date(2026, 11, 28))
    assert special.advent_active(cfg, date(2026, 11, 29))
    assert not special.advent_active(cfg, date(2026, 12, 25))
    assert not special.advent_active(cfg, date(2027, 1, 2))
    # Invalid own day: the default applies
    cfg = {"advent_start": "date", "advent_start_date": "xx", "advent_end": "date"}
    assert special.advent_active(cfg, date(2026, 11, 29))
    assert special.advent_active(cfg, date(2027, 1, 6))
    assert not special.advent_active(cfg, date(2027, 1, 7))
