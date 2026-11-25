"""Engine tests of stage 5: plausibility check and FHEM import."""

from __future__ import annotations

from datetime import time

from custom_components.autoshutterscontrol.engine import fhem
from custom_components.autoshutterscontrol.engine.checks import check
from custom_components.autoshutterscontrol.engine.resolve import resolve
from custom_components.autoshutterscontrol.engine.settings import BY_KEY


def cfg(**values):
    base = resolve({})
    out = {key: base[key] for key in BY_KEY}
    out.update(values)
    return out


def codes(**values) -> list[str]:
    return [code for code, _ in check(cfg(**values))]


def test_defaults_are_plausible() -> None:
    assert codes() == []


def test_time_checks() -> None:
    assert codes(time_up_early_workday=time(9), time_up_late_workday=time(8)) == ["time_order"]
    assert codes(time_down_late_free=time(0, 0)) == ["midnight"]
    found = dict(check(cfg(time_up_early_workday=time(9), time_up_late_workday=time(8))))
    assert found["time_order"]["early"] == "09:00"


def test_threshold_checks() -> None:
    assert codes(up_mode="brightness", brightness_sensor="sensor.lux", brightness_down=900) == [
        "brightness_order"
    ]
    assert codes(shading_brightness_end=40000) == ["shading_brightness_order"]
    assert codes(shading_elevation_min=50, shading_elevation_max=40) == ["elevation_order"]
    assert codes(wind_hysteresis=60) == ["wind_hysteresis"]
    assert codes(pos_closed=100) == ["positions_equal"]


def test_advent_date_check() -> None:
    assert codes(advent_start="date") == ["advent_date"]
    assert codes(advent_end="date", advent_end_date="31.2.") == ["advent_date"]
    assert codes(advent_start="date", advent_start_date="1.12.") == []
    assert codes(advent=False, advent_start="date") == []


def test_missing_sensors() -> None:
    assert codes(up_mode="brightness") == ["missing_brightness"]
    assert codes(rain_protection=True) == ["missing_rain"]
    assert codes(rain_protection=True, rain_sensor="binary_sensor.rain") == []
    assert codes(frost_mode="soft", heat_protection_temp=28.0) == ["missing_temperature"]
    assert codes(lockout="soft") == ["missing_window"]
    assert codes(lockout="soft", window_tilted_sensor="binary_sensor.t") == []
    assert codes(down_mode="residents") == ["missing_residents"]
    assert codes(time_source="calendar") == ["missing_calendar"]
    assert codes(trigger_entity="input_select.mode", trigger_position=None) == [
        "missing_trigger_position"
    ]


FHEM_CFG = r"""
define ASC_Dev AutoShuttersControl
attr ASC_Dev ASC_rainSensor RegenSensor:state 0.5:0.2 10
attr ASC_Dev ASC_tempSensor Aussen_Temp:temperature
attr ASC_Dev ASC_brightnessDriveUpDown 800:400
attr ASC_Dev ASC_autoAstroModeMorning CIVIL
attr ASC_Dev ASC_residentsDev Bewohner
attr ASC_Dev ASC_freezeTemp 3
# comment
define Rollo_Wohnzimmer dummy
attr Rollo_Wohnzimmer ASC 2
attr Rollo_Wohnzimmer ASC_Open_Pos 0
attr Rollo_Wohnzimmer ASC_Closed_Pos 100
attr Rollo_Wohnzimmer ASC_Up astro
attr Rollo_Wohnzimmer ASC_Time_Up_Early 06:30
attr Rollo_Wohnzimmer ASC_WindowRec Fenster_WZ
attr Rollo_Wohnzimmer ASC_Shading_Direction 180
attr Rollo_Wohnzimmer ASC_Shading_Angle_Left 60
attr Rollo_Wohnzimmer ASC_Shading_MinMax_Elevation 20,90
attr Rollo_Wohnzimmer ASC_Shading_StateChange_SunnyCloudy 30000:15000
attr Rollo_Wohnzimmer ASC_LockOut soft
attr Rollo_Wohnzimmer ASC_Roommate_Device Anna,Ben
attr Rollo_Wohnzimmer userReadings test {\
  ReadingsVal("x","y",0) }
attr Rollo_Wohnzimmer ASC_Down {sunset()}
attr Rollo_Kueche ASC 1
attr Rollo_Kueche ASC_Open_Pos 0
attr Rollo_Kueche ASC_Closed_Pos 100
attr Rollo_Kueche ASC_BlockingTime_afterManual 1200
attr Rollo_Kueche ASC_Something_New 5
attr Lampe ASC_Open_Pos 50
"""


def test_read_and_convert() -> None:
    imp = fhem.convert(FHEM_CFG)
    assert imp.asc_device == "ASC_Dev"
    g = imp.global_settings
    assert g["rain_sensor"] == fhem.Ref("RegenSensor")
    assert (g["rain_threshold"], g["rain_hysteresis"], g["pos_rain"]) == (0.5, 0.2, 10)
    assert g["brightness_up"] == 800 and g["brightness_down"] == 400
    assert g["twilight_up"] == "civil"
    assert g["residents_house"] == [fhem.Ref("Bewohner")]
    assert sorted(imp.shutters) == ["Rollo_Kueche", "Rollo_Wohnzimmer"]
    wz = imp.shutters["Rollo_Wohnzimmer"]
    assert wz["time_up_early_workday"] == time(6, 30)
    assert wz["shading_azimuth_start"] == 120 and wz["shading_azimuth_end"] == 255
    assert wz["shading_elevation_min"] == 20 and wz["shading_brightness_end"] == 15000
    assert wz["residents_room"] == [fhem.Ref("Anna"), fhem.Ref("Ben")]
    assert imp.shutters["Rollo_Kueche"]["override_minutes"] == 20
    assert "Rollo_Wohnzimmer: ASC_Down (Perl)" in imp.not_transferred
    assert "Rollo_Kueche: ASC_Something_New" in imp.not_transferred
    assert imp.references() == [
        "Anna",
        "Aussen_Temp",
        "Ben",
        "Bewohner",
        "Fenster_WZ",
        "RegenSensor",
    ]


def test_suggest() -> None:
    covers = {"cover.wohnzimmer": "Wohnzimmer", "cover.kueche": "Küche", "cover.bad": "Bad"}
    assert fhem.suggest("Rollo_Wohnzimmer", covers) == "cover.wohnzimmer"
    assert fhem.suggest("Rollo_Kueche", covers) == "cover.kueche"
    assert fhem.suggest("Garage", covers) is None


def test_plan() -> None:
    imp = fhem.convert(FHEM_CFG)
    plan = fhem.plan(
        imp,
        {"Rollo_Wohnzimmer": "cover.wohnzimmer", "Rollo_Kueche": None},
        {
            "RegenSensor": "binary_sensor.rain",
            "Fenster_WZ": "sensor.fenster",
            "Anna": "person.anna",
        },
        {},
        lambda values: {key: resolve(values)[key] for key in BY_KEY},
    )
    assert plan.skipped_shutters == ["Rollo_Kueche"]
    assert plan.global_settings["rain_sensor"] == "binary_sensor.rain"
    assert "outdoor_temperature_sensor" not in plan.global_settings
    assert plan.unmapped == ["Aussen_Temp", "Ben", "Bewohner"]
    cover, name, values = plan.covers[0]
    assert (cover, name) == ("cover.wohnzimmer", "Rollo_Wohnzimmer")
    assert values["window_state_sensor"] == "sensor.fenster"
    assert values["residents_room"] == ["person.anna"]
    assert values["pos_open"] == 0 and values["pos_closed"] == 100
    assert "up_mode" not in values  # astro is the default
    assert "frost_temp" not in values


def test_plan_moves_shared_values_to_global() -> None:
    imp = fhem.convert(FHEM_CFG)
    plan = fhem.plan(
        imp,
        {"Rollo_Wohnzimmer": "cover.wohnzimmer", "Rollo_Kueche": "cover.kueche"},
        {},
        {},
        lambda values: {key: resolve(values)[key] for key in BY_KEY},
    )
    assert plan.global_settings["pos_open"] == 0
    assert plan.global_settings["pos_closed"] == 100
    for _cover, _name, values in plan.covers:
        assert "pos_open" not in values and "pos_closed" not in values


def test_morning_opening_goes_to_shading_position() -> None:
    from custom_components.autoshutterscontrol.engine.arbiter import (
        BLOCK_DIRECTION,
        Situation,
        Wish,
        decide,
    )

    c = cfg()
    wish = Wish(12, "shading", "shading", 30, "shading")
    for trigger in ("schedule_up", "recovery"):
        d = decide(c, Situation(trigger, current_position=0), [wish])
        assert d.drive and d.position == 30
    d = decide(c, Situation("shading", current_position=0), [wish])
    assert d.blocked_by == BLOCK_DIRECTION
