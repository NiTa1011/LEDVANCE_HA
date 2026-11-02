"""Shared pytest fixtures for hass-ledvance tests."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]


# ---------------------------------------------------------------------------
# Reusable Tuya schema fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def light_schema() -> list[dict]:
    """Minimal schema for a colour-temperature bulb."""
    return [
        {"id": 1, "code": "switch_led",   "type": "Boolean", "mode": "rw"},
        {"id": 2, "code": "work_mode",    "type": "Enum",    "mode": "rw",
         "property": {"range": ["white", "colour", "scene"]}},
        {"id": 3, "code": "bright_value", "type": "Integer", "mode": "rw",
         "property": {"min": 10, "max": 1000, "scale": 0, "step": 1}},
        {"id": 4, "code": "temp_value",   "type": "Integer", "mode": "rw",
         "property": {"min": 0, "max": 1000, "scale": 0, "step": 1}},
    ]


@pytest.fixture
def rgb_light_schema(light_schema) -> list[dict]:
    """Schema for a full RGB + colour-temp bulb."""
    return light_schema + [
        {"id": 5, "code": "colour_data",    "type": "Json", "mode": "rw"},
        {"id": 6, "code": "colour_data_v2", "type": "Json", "mode": "rw"},
    ]


@pytest.fixture
def socket_strip_schema() -> list[dict]:
    """Minimal schema for a 3-gang socket strip with power monitoring."""
    return [
        {"id": 1, "code": "switch_1",     "type": "Boolean", "mode": "rw"},
        {"id": 2, "code": "switch_2",     "type": "Boolean", "mode": "rw"},
        {"id": 3, "code": "switch_3",     "type": "Boolean", "mode": "rw"},
        {"id": 4, "code": "child_lock",   "type": "Boolean", "mode": "rw"},
        {"id": 5, "code": "cur_current",  "type": "Integer", "mode": "ro",
         "property": {"min": 0, "max": 30000, "scale": 3, "step": 1}},
        {"id": 6, "code": "cur_voltage",  "type": "Integer", "mode": "ro",
         "property": {"min": 0, "max": 2500,  "scale": 1, "step": 1}},
        {"id": 7, "code": "cur_power",    "type": "Integer", "mode": "ro",
         "property": {"min": 0, "max": 75000, "scale": 1, "step": 1}},
    ]


@pytest.fixture
def socket_strip_with_master_schema(socket_strip_schema) -> list[dict]:
    """Socket strip schema that includes a hardware master switch DPS."""
    return socket_strip_schema + [
        {"id": 8, "code": "master_switch", "type": "Boolean", "mode": "rw"},
    ]


@pytest.fixture
def single_switch_schema() -> list[dict]:
    """Schema for a simple single-outlet smart plug."""
    return [
        {"id": 1, "code": "switch",      "type": "Boolean", "mode": "rw"},
        {"id": 2, "code": "cur_current", "type": "Integer", "mode": "ro",
         "property": {"min": 0, "max": 30000, "scale": 3, "step": 1}},
    ]


@pytest.fixture
def lightstrip_schema() -> list[dict]:
    """Schema for a Ledvance Smart+ WiFi lightstrip."""
    return [
        {"id": 20, "code": "switch_led",   "type": "Boolean", "mode": "rw"},
        {"id": 21, "code": "work_mode",    "type": "Enum",    "mode": "rw",
         "property": {"range": ["white", "colour", "scene", "music"]}},
        {"id": 22, "code": "bright_value", "type": "Integer", "mode": "rw",
         "property": {"min": 10, "max": 1000, "scale": 0, "step": 1}},
        {"id": 23, "code": "temp_value",   "type": "Integer", "mode": "rw",
         "property": {"min": 0, "max": 1000, "scale": 0, "step": 1}},
        {"id": 24, "code": "colour_data",  "type": "Json",    "mode": "rw"},
    ]


@pytest.fixture
def thermostat_gen1_schema() -> list[dict]:
    """Schema for a Ledvance Smart+ WiFi Radiator Thermostat Gen 1."""
    return [
        {"id": 1, "code": "switch",             "type": "Boolean", "mode": "rw"},
        {"id": 2, "code": "temp_set",           "type": "Integer", "mode": "rw",
         "property": {"min": 50, "max": 350, "scale": 1, "step": 5}},
        {"id": 3, "code": "temp_current",       "type": "Integer", "mode": "ro",
         "property": {"min": 0, "max": 500, "scale": 1, "step": 1}},
        {"id": 4, "code": "mode",               "type": "Enum",    "mode": "rw",
         "property": {"range": ["auto", "manual", "holiday", "eco", "boost"]}},
        {"id": 6, "code": "battery_percentage", "type": "Integer", "mode": "ro",
         "property": {"min": 0, "max": 100, "scale": 0, "step": 1}},
        {"id": 7, "code": "child_lock",         "type": "Boolean", "mode": "rw"},
    ]


@pytest.fixture
def thermostat_gen2_schema() -> list[dict]:
    """Schema for a Ledvance Smart+ WiFi Radiator Thermostat Gen 2."""
    return [
        {"id": 1, "code": "switch",             "type": "Boolean", "mode": "rw"},
        {"id": 2, "code": "temp_set",           "type": "Integer", "mode": "rw",
         "property": {"min": 50, "max": 350, "scale": 1, "step": 5}},
        {"id": 3, "code": "temp_current",       "type": "Integer", "mode": "ro",
         "property": {"min": 0, "max": 500, "scale": 1, "step": 1}},
        {"id": 4, "code": "mode",               "type": "Enum",    "mode": "rw",
         "property": {"range": ["auto", "manual", "holiday", "eco", "boost", "frost"]}},
        {"id": 5, "code": "valve_state",        "type": "Integer", "mode": "ro",
         "property": {"min": 0, "max": 100, "scale": 0, "step": 1}},
        {"id": 6, "code": "battery_percentage", "type": "Integer", "mode": "ro",
         "property": {"min": 0, "max": 100, "scale": 0, "step": 1}},
        {"id": 7, "code": "child_lock",         "type": "Boolean", "mode": "rw"},
        {"id": 8, "code": "temp_correction",    "type": "Integer", "mode": "rw",
         "property": {"min": -9, "max": 9, "scale": 0, "step": 1}},
        {"id": 9, "code": "window_state",       "type": "Boolean", "mode": "ro"},
        {"id": 10, "code": "fault",             "type": "Bitmap",  "mode": "ro"},
    ]


# ---------------------------------------------------------------------------
# Mock API
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_api() -> MagicMock:
    """Return a pre-configured mock TuyaAPI instance."""
    api = MagicMock()
    api.get_device_list.return_value = []
    api.set_dps.return_value = None
    return api
