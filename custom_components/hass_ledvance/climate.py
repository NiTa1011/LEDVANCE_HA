"""Climate platform for Ledvance/Tuya smart radiator thermostats (Gen 1 & Gen 2)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
    PRECISION_HALVES,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    DPS_TEMP_CURRENT,
    DPS_TEMP_SET,
    DPS_VALVE_STATE,
)
from .coordinator import (
    CoordinatorDeviceData,
    LedvanceTuyaCoordinator,
    build_device_info,
)
from .local_control import async_send_command
from .schema_parser import get_enum_range, get_integer_range, get_numeric_scale

_LOGGER = logging.getLogger(__name__)

# Preset mappings between Tuya mode enum values and HA presets
_TUYA_TO_HA_PRESETS: dict[str, str] = {
    "holiday": PRESET_AWAY,
    "vacation": PRESET_AWAY,
    "away": PRESET_AWAY,
    "eco": PRESET_ECO,
    "energy_saving": PRESET_ECO,
    "boost": PRESET_BOOST,
    "comfort": PRESET_COMFORT,
    "frost": "anti_freeze",
    "antifrost": "anti_freeze",
    "anti_freeze": "anti_freeze",
}

_HA_TO_TUYA_PRESETS: dict[str, str] = {
    PRESET_AWAY: "holiday",
    PRESET_ECO: "eco",
    PRESET_BOOST: "boost",
    PRESET_COMFORT: "comfort",
    "anti_freeze": "frost",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ledvance/Tuya climate entities."""
    coordinator: LedvanceTuyaCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ClimateEntity] = [
        LedvanceTuyaThermostat(coordinator, entry, dev_id)
        for dev_id, dev in coordinator.data.items()
        if dev.device_type == "thermostat"
    ]
    _LOGGER.debug("Setting up %d climate entities", len(entities))
    async_add_entities(entities)


class LedvanceTuyaThermostat(CoordinatorEntity, ClimateEntity):
    """Representation of a Ledvance Smart+ WiFi Radiator Thermostat (Gen 1 & Gen 2)."""

    _attr_has_entity_name = True
    _attr_name = None  # uses device name
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_HALVES
    _attr_target_temperature_step = 0.5

    def __init__(
        self,
        coordinator: LedvanceTuyaCoordinator,
        entry: ConfigEntry,
        device_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{device_id}_climate"

        dev = self._device_data
        self._attr_device_info = build_device_info(dev)

        # 1. Target temperature DPS
        self._temp_set_dps: str | None = None
        self._temp_set_code: str | None = None
        for candidate in (DPS_TEMP_SET, "target_temperature", "temperature_set", "temp_set_f"):
            if candidate in dev.dps_map:
                self._temp_set_dps = dev.dps_map[candidate]
                self._temp_set_code = candidate
                break
        if self._temp_set_dps is None:
            for fallback_dp in ("2", "16"):
                if fallback_dp in dev.dps:
                    self._temp_set_dps = fallback_dp
                    break

        # 2. Current temperature DPS
        self._temp_current_dps: str | None = None
        self._temp_current_code: str | None = None
        for candidate in (
            DPS_TEMP_CURRENT,
            "room_temperature",
            "va_temperature",
            "current_temperature",
            "temp_current_f",
        ):
            if candidate in dev.dps_map:
                self._temp_current_dps = dev.dps_map[candidate]
                self._temp_current_code = candidate
                break
        if self._temp_current_dps is None:
            for fallback_dp in ("3", "24"):
                if fallback_dp in dev.dps:
                    self._temp_current_dps = fallback_dp
                    break

        # 3. Mode / Work Mode DPS
        self._mode_dps: str | None = None
        self._mode_code: str | None = None
        for candidate in ("mode", "work_mode"):
            if candidate in dev.dps_map:
                self._mode_dps = dev.dps_map[candidate]
                self._mode_code = candidate
                break
        if self._mode_dps is None and "4" in dev.dps:
            self._mode_dps = "4"

        # 4. Switch / Power DPS
        self._switch_dps: str | None = None
        for candidate in ("switch", "switch_1", "heating_switch", "switch_power"):
            if candidate in dev.dps_map:
                self._switch_dps = dev.dps_map[candidate]
                break
        if self._switch_dps is None and "1" in dev.dps:
            self._switch_dps = "1"

        # 5. Valve state DPS
        self._valve_dps: str | None = None
        for candidate in (DPS_VALVE_STATE, "valve", "valve_position"):
            if candidate in dev.dps_map:
                self._valve_dps = dev.dps_map[candidate]
                break
        if self._valve_dps is None and "5" in dev.dps:
            self._valve_dps = "5"

        # Determine temperature scale & limits from schema
        lo, hi = get_integer_range(dev.schema, self._temp_set_code or "temp_set")
        scale_set = get_numeric_scale(dev.schema, self._temp_set_code or "temp_set")
        # Tuya TRVs frequently use scale 10 (e.g. 50-350 for 5.0-35.0 C)
        if scale_set == 1.0 and hi > 100:
            scale_set = 10.0
        self._scale_set = scale_set
        self._attr_min_temp = float(lo) / scale_set if lo > 0 else 5.0
        self._attr_max_temp = float(hi) / scale_set if hi > 0 else 35.0

        scale_curr = get_numeric_scale(dev.schema, self._temp_current_code or "temp_current")
        if scale_curr == 1.0 and scale_set == 10.0:
            scale_curr = 10.0
        self._scale_curr = scale_curr

        # Determine supported HVAC modes & preset modes
        self._available_modes: list[str] = (
            get_enum_range(dev.schema, self._mode_code) if self._mode_code else []
        )
        if not self._available_modes and self._mode_dps:
            # Standard Tuya TRV modes fallback
            self._available_modes = ["auto", "manual", "holiday", "eco", "boost", "off"]

        hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
        if "auto" in self._available_modes:
            hvac_modes.append(HVACMode.AUTO)
        self._attr_hvac_modes = hvac_modes

        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

        # Map available presets
        preset_modes: list[str] = [PRESET_NONE]
        for tuya_m in self._available_modes:
            ha_p = _TUYA_TO_HA_PRESETS.get(tuya_m)
            if ha_p and ha_p not in preset_modes:
                preset_modes.append(ha_p)

        if len(preset_modes) > 1:
            features |= ClimateEntityFeature.PRESET_MODE
            self._attr_preset_modes = preset_modes
        else:
            self._attr_preset_modes = []

        self._attr_supported_features = features

    @property
    def _device_data(self) -> CoordinatorDeviceData:
        return self.coordinator.data[self._device_id]

    @property
    def available(self) -> bool:
        return (
            super().available
            and self._device_id in self.coordinator.data
            and self._device_data.is_online
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature from sensor."""
        if self._temp_current_dps is None:
            return None
        raw = self._device_data.dps.get(self._temp_current_dps)
        if raw is None:
            return None
        try:
            return round(float(raw) / self._scale_curr, 1)
        except (ValueError, TypeError):
            return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self._temp_set_dps is None:
            return None
        raw = self._device_data.dps.get(self._temp_set_dps)
        if raw is None:
            return None
        try:
            return round(float(raw) / self._scale_set, 1)
        except (ValueError, TypeError):
            return None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation mode."""
        # 1. Switch power state check
        if self._switch_dps is not None:
            power_on = bool(self._device_data.dps.get(self._switch_dps))
            if not power_on:
                return HVACMode.OFF

        # 2. Tuya mode check
        if self._mode_dps is not None:
            mode_val = str(self._device_data.dps.get(self._mode_dps) or "").lower()
            if mode_val == "off":
                return HVACMode.OFF
            if mode_val == "auto":
                return HVACMode.AUTO

        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return current HVAC action (heating, idle, off)."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF

        # If valve opening state is available
        if self._valve_dps is not None:
            raw_valve = self._device_data.dps.get(self._valve_dps)
            if raw_valve is not None:
                try:
                    return HVACAction.HEATING if int(raw_valve) > 0 else HVACAction.IDLE
                except (ValueError, TypeError):
                    pass

        # Fallback to temperature comparison
        cur = self.current_temperature
        tgt = self.target_temperature
        if cur is not None and tgt is not None:
            return HVACAction.HEATING if cur < tgt else HVACAction.IDLE

        return HVACAction.HEATING

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if not self._attr_preset_modes or self._mode_dps is None:
            return None
        mode_val = str(self._device_data.dps.get(self._mode_dps) or "").lower()
        return _TUYA_TO_HA_PRESETS.get(mode_val, PRESET_NONE)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if self._temp_set_dps is None or ATTR_TEMPERATURE not in kwargs:
            return

        target_temp = float(kwargs[ATTR_TEMPERATURE])
        clamped_temp = max(self._attr_min_temp, min(self._attr_max_temp, target_temp))
        raw_val = round(clamped_temp * self._scale_set)

        dps: dict[str, Any] = {self._temp_set_dps: raw_val}

        # If device switch is currently OFF, turn it ON when setting target temp
        if self._switch_dps and not self._device_data.dps.get(self._switch_dps):
            dps[self._switch_dps] = True

        await async_send_command(self.hass, self.coordinator.api, self._device_data, dps)
        self.coordinator.async_optimistic_update(self._device_id, dps)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        dps: dict[str, Any] = {}

        if hvac_mode == HVACMode.OFF:
            if self._switch_dps:
                dps[self._switch_dps] = False
            elif self._mode_dps and "off" in self._available_modes:
                dps[self._mode_dps] = "off"

        elif hvac_mode == HVACMode.AUTO:
            if self._switch_dps:
                dps[self._switch_dps] = True
            if self._mode_dps:
                for auto_candidate in ("auto", "schedule"):
                    if auto_candidate in self._available_modes:
                        dps[self._mode_dps] = auto_candidate
                        break

        elif hvac_mode == HVACMode.HEAT:
            if self._switch_dps:
                dps[self._switch_dps] = True
            if self._mode_dps:
                for manual_candidate in ("manual", "heat", "normal"):
                    if manual_candidate in self._available_modes:
                        dps[self._mode_dps] = manual_candidate
                        break

        if dps:
            await async_send_command(self.hass, self.coordinator.api, self._device_data, dps)
            self.coordinator.async_optimistic_update(self._device_id, dps)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if not self._mode_dps:
            return

        dps: dict[str, Any] = {}
        if preset_mode == PRESET_NONE:
            # Revert to standard manual or auto
            for mode_candidate in ("manual", "heat", "auto"):
                if mode_candidate in self._available_modes:
                    dps[self._mode_dps] = mode_candidate
                    break
        else:
            tuya_mode = _HA_TO_TUYA_PRESETS.get(preset_mode)
            if tuya_mode and tuya_mode in self._available_modes:
                dps[self._mode_dps] = tuya_mode
            elif tuya_mode:
                # Find partial match
                for m in self._available_modes:
                    if tuya_mode in m:
                        dps[self._mode_dps] = m
                        break

        if dps:
            # Ensure device power is ON when selecting a preset
            if self._switch_dps and not self._device_data.dps.get(self._switch_dps):
                dps[self._switch_dps] = True
            await async_send_command(self.hass, self.coordinator.api, self._device_data, dps)
            self.coordinator.async_optimistic_update(self._device_id, dps)

    async def async_turn_on(self) -> None:
        """Turn the thermostat on."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn the thermostat off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
