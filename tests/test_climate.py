"""Tests for custom_components.hass_ledvance.climate."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TEMPERATURE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
)

from custom_components.hass_ledvance.climate import (
    LedvanceTuyaThermostat,
    async_setup_entry,
)
from custom_components.hass_ledvance.const import DOMAIN
from custom_components.hass_ledvance.coordinator import CoordinatorDeviceData


def _build_thermostat_data(
    schema: list[dict],
    dps: dict,
    product_id: str = "trv_pid",
    is_online: bool = True,
    device_id: str = "trv001",
) -> CoordinatorDeviceData:
    dps_map = {item["code"]: str(item["id"]) for item in schema if "code" in item and "id" in item}
    return CoordinatorDeviceData(
        device_id=device_id,
        gateway_id=device_id,
        name="Living Room Radiator",
        product_id=product_id,
        device_type="thermostat",
        schema=schema,
        dps_map=dps_map,
        dps=dps,
        local_key="0123456789abcdef",
        mac="aa:bb:cc:dd:ee:ff",
        is_online=is_online,
        lan_ip="192.168.1.100",
        version="3.3",
    )


class TestThermostatGen1:
    """Tests for Gen 1 Radiator Thermostat."""

    def test_temperature_properties(self, thermostat_gen1_schema):
        # 210 = 21.0 C, 205 = 20.5 C
        dev = _build_thermostat_data(
            thermostat_gen1_schema,
            dps={"1": True, "2": 210, "3": 205, "4": "manual", "6": 85, "7": False},
        )
        coordinator = MagicMock()
        coordinator.data = {dev.device_id: dev}
        entry = MagicMock()
        entry.entry_id = "test_entry"

        trv = LedvanceTuyaThermostat(coordinator, entry, dev.device_id)

        assert trv.current_temperature == 20.5
        assert trv.target_temperature == 21.0
        assert trv.min_temp == 5.0
        assert trv.max_temp == 35.0
        assert trv.hvac_mode == HVACMode.HEAT
        assert trv.hvac_action == HVACAction.HEATING
        assert trv.available is True

    def test_hvac_mode_off_when_switch_false(self, thermostat_gen1_schema):
        dev = _build_thermostat_data(
            thermostat_gen1_schema,
            dps={"1": False, "2": 200, "3": 200, "4": "manual"},
        )
        coordinator = MagicMock()
        coordinator.data = {dev.device_id: dev}
        entry = MagicMock()
        entry.entry_id = "test_entry"

        trv = LedvanceTuyaThermostat(coordinator, entry, dev.device_id)

        assert trv.hvac_mode == HVACMode.OFF
        assert trv.hvac_action == HVACAction.OFF

    def test_hvac_mode_auto(self, thermostat_gen1_schema):
        dev = _build_thermostat_data(
            thermostat_gen1_schema,
            dps={"1": True, "2": 200, "3": 200, "4": "auto"},
        )
        coordinator = MagicMock()
        coordinator.data = {dev.device_id: dev}
        entry = MagicMock()
        entry.entry_id = "test_entry"

        trv = LedvanceTuyaThermostat(coordinator, entry, dev.device_id)

        assert trv.hvac_mode == HVACMode.AUTO

    def test_preset_modes(self, thermostat_gen1_schema):
        dev = _build_thermostat_data(
            thermostat_gen1_schema,
            dps={"1": True, "2": 200, "3": 200, "4": "eco"},
        )
        coordinator = MagicMock()
        coordinator.data = {dev.device_id: dev}
        entry = MagicMock()
        entry.entry_id = "test_entry"

        trv = LedvanceTuyaThermostat(coordinator, entry, dev.device_id)

        assert trv.preset_mode == PRESET_ECO
        assert PRESET_ECO in trv.preset_modes
        assert PRESET_BOOST in trv.preset_modes
        assert PRESET_AWAY in trv.preset_modes

    async def test_set_temperature(self, hass, mock_api, thermostat_gen1_schema):
        dev = _build_thermostat_data(
            thermostat_gen1_schema,
            dps={"1": True, "2": 200, "3": 190, "4": "manual"},
        )
        coordinator = MagicMock()
        coordinator.data = {dev.device_id: dev}
        coordinator.api = mock_api
        entry = MagicMock()
        entry.entry_id = "test_entry"

        trv = LedvanceTuyaThermostat(coordinator, entry, dev.device_id)
        trv.hass = hass

        with patch("custom_components.hass_ledvance.climate.async_send_command", new=AsyncMock(return_value=True)) as mock_send:
            await trv.async_set_temperature(**{ATTR_TEMPERATURE: 22.5})
            mock_send.assert_called_once_with(hass, mock_api, dev, {"2": 225})
            coordinator.async_optimistic_update.assert_called_once_with(dev.device_id, {"2": 225})

    async def test_set_hvac_mode(self, hass, mock_api, thermostat_gen1_schema):
        dev = _build_thermostat_data(
            thermostat_gen1_schema,
            dps={"1": True, "2": 200, "3": 190, "4": "manual"},
        )
        coordinator = MagicMock()
        coordinator.data = {dev.device_id: dev}
        coordinator.api = mock_api
        entry = MagicMock()
        entry.entry_id = "test_entry"

        trv = LedvanceTuyaThermostat(coordinator, entry, dev.device_id)
        trv.hass = hass

        with patch("custom_components.hass_ledvance.climate.async_send_command", new=AsyncMock(return_value=True)) as mock_send:
            await trv.async_set_hvac_mode(HVACMode.OFF)
            mock_send.assert_called_once_with(hass, mock_api, dev, {"1": False})

        with patch("custom_components.hass_ledvance.climate.async_send_command", new=AsyncMock(return_value=True)) as mock_send:
            await trv.async_set_hvac_mode(HVACMode.AUTO)
            mock_send.assert_called_once_with(hass, mock_api, dev, {"1": True, "4": "auto"})


class TestThermostatGen2:
    """Tests for Gen 2 Radiator Thermostat."""

    def test_gen2_properties_with_valve(self, thermostat_gen2_schema):
        dev = _build_thermostat_data(
            thermostat_gen2_schema,
            dps={
                "1": True,
                "2": 210,
                "3": 215,
                "4": "manual",
                "5": 40,   # valve 40% open
                "6": 90,   # battery 90%
                "7": False,
                "8": 0,    # calibration
                "9": False,# window closed
                "10": 0,   # no fault
            },
        )
        coordinator = MagicMock()
        coordinator.data = {dev.device_id: dev}
        entry = MagicMock()
        entry.entry_id = "test_entry"

        trv = LedvanceTuyaThermostat(coordinator, entry, dev.device_id)

        assert trv.current_temperature == 21.5
        assert trv.target_temperature == 21.0
        # Even though cur > tgt, valve is 40% open so action is HEATING
        assert trv.hvac_action == HVACAction.HEATING

    def test_gen2_idle_when_valve_zero(self, thermostat_gen2_schema):
        dev = _build_thermostat_data(
            thermostat_gen2_schema,
            dps={
                "1": True,
                "2": 210,
                "3": 215,
                "4": "manual",
                "5": 0,    # valve 0% closed
            },
        )
        coordinator = MagicMock()
        coordinator.data = {dev.device_id: dev}
        entry = MagicMock()
        entry.entry_id = "test_entry"

        trv = LedvanceTuyaThermostat(coordinator, entry, dev.device_id)

        assert trv.hvac_action == HVACAction.IDLE

    async def test_gen2_async_setup_entry(self, hass, thermostat_gen2_schema):
        dev = _build_thermostat_data(
            thermostat_gen2_schema,
            dps={"1": True, "2": 200, "3": 200, "4": "manual"},
        )
        coordinator = MagicMock()
        coordinator.data = {dev.device_id: dev}
        hass.data = {DOMAIN: {"test_entry": coordinator}}
        entry = MagicMock()
        entry.entry_id = "test_entry"

        entities_added = []
        def async_add_entities(entities):
            entities_added.extend(entities)

        await async_setup_entry(hass, entry, async_add_entities)
        assert len(entities_added) == 1
        assert isinstance(entities_added[0], LedvanceTuyaThermostat)
