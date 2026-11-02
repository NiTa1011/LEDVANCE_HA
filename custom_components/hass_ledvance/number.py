"""Number platform for Ledvance/Tuya integration.

Provides per-outlet countdown timers on socket strip devices.
Setting a countdown to 0 cancels it; any positive value (seconds)
schedules the outlet to turn off after that duration.
"""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DPS_COUNTDOWN_PREFIX, DPS_TEMP_CORRECTION
from .coordinator import CoordinatorDeviceData, LedvanceTuyaCoordinator, build_device_info
from .local_control import async_send_command
from .schema_parser import get_integer_range, get_numeric_scale

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ledvance/Tuya number entities."""
    coordinator: LedvanceTuyaCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[NumberEntity] = []

    for dev_id, dev in coordinator.data.items():
        if dev.device_type == "socket_strip":
            # Find all countdown_N DPS in the schema, ordered by outlet number
            countdown_items = sorted(
                (
                    item for item in dev.schema
                    if (item.get("code", "")).startswith(DPS_COUNTDOWN_PREFIX)
                    and item["code"][len(DPS_COUNTDOWN_PREFIX):].isdigit()
                ),
                key=lambda i: int(i["code"][len(DPS_COUNTDOWN_PREFIX):]),
            )

            for item in countdown_items:
                code = item["code"]
                outlet_num = code[len(DPS_COUNTDOWN_PREFIX):]
                entities.append(
                    LedvanceTuyaCountdown(
                        coordinator, entry, dev_id, code, f"Outlet {outlet_num} Countdown"
                    )
                )

        # Temperature calibration for thermostats
        if dev.device_type == "thermostat":
            schema_codes = {item.get("code") for item in dev.schema}
            cal_code = next(
                (c for c in (DPS_TEMP_CORRECTION, "temp_calibration", "calibration") if c in schema_codes or c in dev.dps_map),
                None,
            )
            if cal_code:
                entities.append(LedvanceTuyaTempCalibration(coordinator, entry, dev_id, cal_code))

    _LOGGER.debug("Setting up %d countdown entities", len(entities))
    async_add_entities(entities)


class LedvanceTuyaCountdown(CoordinatorEntity[LedvanceTuyaCoordinator], NumberEntity):
    """Per-outlet countdown timer (seconds) for a Ledvance/Tuya socket strip."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_step = 1.0

    def __init__(
        self,
        coordinator: LedvanceTuyaCoordinator,
        entry: ConfigEntry,
        device_id: str,
        dps_code: str,
        label: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._dps_code = dps_code
        self._attr_name = label
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_{dps_code}"

        dev = coordinator.data[device_id]
        self._attr_device_info = build_device_info(dev)
        self._dps: str | None = dev.dps_map.get(dps_code)

        lo, hi = get_integer_range(dev.schema, dps_code)
        self._attr_native_min_value = float(lo)
        self._attr_native_max_value = float(hi)

    @property
    def _device_data(self) -> CoordinatorDeviceData:
        return self.coordinator.data[self._device_id]

    @property
    def native_value(self) -> float | None:
        if self._dps is None:
            return None
        raw = self._device_data.dps.get(self._dps)
        if raw is None:
            return None
        return float(raw)

    async def async_set_native_value(self, value: float) -> None:
        if self._dps is None:
            return
        dps = {self._dps: int(value)}
        await async_send_command(
            self.hass,
            self.coordinator.api,
            self._device_data,
            dps,
        )
        self.coordinator.async_optimistic_update(self._device_id, dps)


class LedvanceTuyaTempCalibration(CoordinatorEntity[LedvanceTuyaCoordinator], NumberEntity):
    """Temperature calibration offset (°C) for a Ledvance Smart+ WiFi Radiator Thermostat."""

    _attr_has_entity_name = True
    _attr_name = "Temperature Calibration"
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:thermometer-lines"

    def __init__(
        self,
        coordinator: LedvanceTuyaCoordinator,
        entry: ConfigEntry,
        device_id: str,
        dps_code: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._dps_code = dps_code
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_{dps_code}"

        dev = coordinator.data[device_id]
        self._attr_device_info = build_device_info(dev)
        self._dps: str | None = dev.dps_map.get(dps_code)

        lo, hi = get_integer_range(dev.schema, dps_code)
        scale = get_numeric_scale(dev.schema, dps_code)
        if scale == 1.0 and (abs(lo) > 50 or abs(hi) > 50):
            scale = 10.0
        self._scale = scale
        self._attr_native_min_value = float(lo) / scale if lo != 0 else -9.0
        self._attr_native_max_value = float(hi) / scale if hi != 0 else 9.0
        self._attr_native_step = 0.5 if self._scale == 10.0 else 1.0

    @property
    def _device_data(self) -> CoordinatorDeviceData:
        return self.coordinator.data[self._device_id]

    @property
    def native_value(self) -> float | None:
        if self._dps is None:
            return None
        raw = self._device_data.dps.get(self._dps)
        if raw is None:
            return None
        try:
            return round(float(raw) / self._scale, 1)
        except (ValueError, TypeError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        if self._dps is None:
            return
        raw_val = round(value * self._scale)
        dps = {self._dps: raw_val}
        await async_send_command(
            self.hass,
            self.coordinator.api,
            self._device_data,
            dps,
        )
        self.coordinator.async_optimistic_update(self._device_id, dps)
