"""0.10.1: FHEM raw definitions, overview switch, blue hour, Sunday before Advent."""

from __future__ import annotations

from datetime import date

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.autoshutterscontrol.engine import fhem
from custom_components.autoshutterscontrol.engine.special import advent_active, first_advent
from custom_components.autoshutterscontrol.engine.sun import Location, SunCalculator

from .helpers import TZ, mock_cover_services, set_cover, setup_entry, setup_hass

RAW_ASC = """defmod ASC AutoShuttersControl
attr ASC ASC_advEndDate EpiphanyDay
attr ASC ASC_advStartDate FirstAdvent
attr ASC ASC_autoShuttersControlComfort off
attr ASC ASC_autoShuttersControlEvening on
attr ASC ASC_autoShuttersControlMorning on
attr ASC ASC_rainSensor Regensensor:1.STATE rain
attr ASC ASC_tempSensor Temp_Eingang
attr ASC ASC_twilightDevice Astro
attr ASC devStateIcon { ShuttersControl_DevStateIcon($name) }
attr ASC icon fts_shutter_automatic
attr ASC room Rollladen"""

RAW_SHUTTER = """defmod Rollo_KiZi_W HMCCUDEV 123456789  sd=3.LEVEL cd=4.LEVEL
attr Rollo_KiZi_W userattr ASC_Adv:on,off ASC_Antifreeze:off,soft,hard,am,pm ASC_Closed_Pos:0,10,20,30,40,50,60,70,80,90,100 ASC_Down:time,astro,brightness,roommate ASC_ShuttersPlace:window,terrace,awning,EG_window ASC_WindowRec_subType:twostate,threestate
attr Rollo_KiZi_W ASC 2
attr Rollo_KiZi_W ASC_BlockingTime_afterManual 7200
attr Rollo_KiZi_W ASC_BlockingTime_beforeDayOpen 7200
attr Rollo_KiZi_W ASC_BlockingTime_beforeNightClose 7200
attr Rollo_KiZi_W ASC_BrightnessSensor Lux_S_JPLIO00001:brightness 200:30
attr Rollo_KiZi_W ASC_Down brightness
attr Rollo_KiZi_W ASC_DriveUpMaxDuration 20
attr Rollo_KiZi_W ASC_Drive_Delay 60
attr Rollo_KiZi_W ASC_Drive_DelayStart 5
attr Rollo_KiZi_W ASC_Mode_Down always
attr Rollo_KiZi_W ASC_Mode_Up always
attr Rollo_KiZi_W ASC_Pos_Reading pct
attr Rollo_KiZi_W ASC_PrivacyUp_Pos 16
attr Rollo_KiZi_W ASC_Shading_InOutAzimuth 15:192
attr Rollo_KiZi_W ASC_Shading_Mode always
attr Rollo_KiZi_W ASC_Shading_Pos 40
attr Rollo_KiZi_W ASC_Shading_StateChange_SunnyCloudy 15000:10000
attr Rollo_KiZi_W ASC_ShuttersPlace EG_window
attr Rollo_KiZi_W ASC_TempSensor Temp_Eingang_N
attr Rollo_KiZi_W ASC_Time_Down_Early 17:00
attr Rollo_KiZi_W ASC_Time_Down_Late 20:45
attr Rollo_KiZi_W ASC_Time_Up_Early 09:45
attr Rollo_KiZi_W ASC_Time_Up_Late 11:00
attr Rollo_KiZi_W ASC_Time_Up_WE_Holiday 10:45
attr Rollo_KiZi_W ASC_Up brightness
attr Rollo_KiZi_W ASC_Ventilate_Window_Open off
attr Rollo_KiZi_W ASC_WindowRec Fenster
attr Rollo_KiZi_W ccureadingfilter 1,2,3,4..*
attr Rollo_KiZi_W room Rollladen
attr Rollo_KiZi_W webCmd pct:open:close:stop"""


def test_raw_asc_device() -> None:
    imp = fhem.convert(RAW_ASC)
    assert imp.asc_device == "ASC"
    assert imp.global_settings == {
        "advent_end": "epiphany",
        "advent_start": "first_advent",
        "rain_sensor": fhem.Ref("Regensensor"),
        "outdoor_temperature_sensor": fhem.Ref("Temp_Eingang"),
    }
    assert imp.switches == {"comfort": False, "evening": True, "morning": True}
    # room, icon, devStateIcon are not relevant: no message
    assert imp.not_transferred == []


def test_raw_shutter() -> None:
    imp = fhem.convert(RAW_SHUTTER)
    values = imp.shutters["Rollo_KiZi_W"]
    assert values["pos_shading"] == 40
    assert values["pos_privacy_up"] == 16
    assert values["shading_azimuth_start"] == 15
    assert values["shading_azimuth_end"] == 192
    assert values["brightness_sensor"] == fhem.Ref("Lux_S_JPLIO00001")
    assert values["window_state_sensor"] == fhem.Ref("Fenster")
    assert values["up_mode"] == "brightness"
    assert "window_preset" not in values  # EG_window: an ordinary window
    # Only ASC attributes count; the ones without a counterpart are named
    assert sorted(imp.not_transferred) == [
        "Rollo_KiZi_W: ASC_BlockingTime_beforeDayOpen",
        "Rollo_KiZi_W: ASC_BlockingTime_beforeNightClose",
    ]
    # Also with the ASC device and the shutter in one text, and in the per cover import
    both = fhem.convert(RAW_ASC + "\n" + RAW_SHUTTER, loose=True)
    assert list(both.shutters) == ["Rollo_KiZi_W"]
    assert both.asc_device == "ASC"


def test_place_and_aliases() -> None:
    imp = fhem.convert(
        "defmod R1 dummy\nattr R1 ASC 1\nattr R1 ASC_ShuttersPlace terrace\n"
        "attr R1 ASC_AutoAstroModeEvening CIVIL\n"
        "defmod R2 dummy\nattr R2 ASC 1\nattr R2 ASC_ShuttersPlace awning\n"
        "defmod ASC AutoShuttersControl\nattr ASC ASC_advStartDate DeadSunday\n"
        "attr ASC ASC_advEndDate CandlemasDay\nattr ASC ASC_rainSensor Regen:rain 2:1 30\n"
    )
    assert imp.shutters["R1"] == {"window_preset": "terrace_door", "twilight_down": "civil"}
    assert imp.shutters["R2"] == {"cover_type": "awning"}
    assert imp.global_settings["advent_start"] == "dead_sunday"
    assert imp.global_settings["advent_end"] == "candlemas"
    assert imp.global_settings["rain_threshold"] == 2.0
    assert imp.global_settings["pos_rain"] == 30


async def test_import_switches(hass: HomeAssistant) -> None:
    await setup_hass(hass)
    set_cover(hass, position=100)
    mock_cover_services(hass)
    entry = await setup_entry(hass, {})
    manager = entry.runtime_data
    manager.set_switch("evening", True)
    text = "defmod ASC AutoShuttersControl\nattr ASC ASC_autoShuttersControlEvening off\n"
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "fhem_import"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"fhem_cfg": text}
    )
    while result["step_id"] != "fhem_done":
        result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["description_placeholders"]["global"] != "–"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert (
        hass.config_entries.async_get_entry(entry.entry_id).runtime_data.switches["evening"]
        is False
    )


def test_blue_hour() -> None:
    sun = SunCalculator(Location(51.35, 8.57, 450, TZ))
    day = date(2026, 12, 1)
    blue = sun.morning(day, "blue")
    assert sun.morning(day, "civil") < blue < sun.morning(day, "real")
    # Including refraction a little lower than 4°
    assert -5.2 < sun.elevation(blue) < -3.4
    assert sun.evening(day, "real") < sun.evening(day, "blue") < sun.evening(day, "civil")


def test_sunday_before_advent() -> None:
    cfg = {"advent_start": "dead_sunday", "advent_end": "epiphany"}
    first = first_advent(2026)
    assert advent_active(cfg, date.fromordinal(first.toordinal() - 7))
    assert not advent_active(cfg, date.fromordinal(first.toordinal() - 8))
    assert not advent_active(
        {**cfg, "advent_start": "first_advent"}, date.fromordinal(first.toordinal() - 1)
    )
