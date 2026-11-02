"""Light platform for Ledvance/Tuya integration."""
from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.color import (
    color_hs_to_RGB,
    color_RGB_to_hs,
)

from .const import (
    DOMAIN,
    DPS_BRIGHT_VALUE,
    DPS_BRIGHT_VALUE_V2,
    DPS_COLOUR_DATA,
    DPS_COLOUR_DATA_V2,
    DPS_SCENE_DATA,
    DPS_SCENE_DATA_V2,
    DPS_SWITCH_LED,
    DPS_TEMP_VALUE,
    DPS_WORK_MODE,
    HA_COLOUR_TEMP_MAX_KELVIN,
    HA_COLOUR_TEMP_MIN_KELVIN,
    TUYA_BRIGHTNESS_MAX,
    TUYA_BRIGHTNESS_MIN,
    TUYA_COLOUR_TEMP_MAX,
    TUYA_COLOUR_TEMP_MIN,
)
from .coordinator import CoordinatorDeviceData, LedvanceTuyaCoordinator, build_device_info
from .local_control import async_send_command
from .schema_parser import get_enum_range, get_integer_range

# work_mode values that map to HA colour modes rather than effects
_COLOUR_WORK_MODES = {"white", "colour"}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ledvance/Tuya light entities."""
    coordinator: LedvanceTuyaCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        LedvanceTuyaLight(coordinator, entry, dev_id)
        for dev_id, dev in coordinator.data.items()
        if dev.device_type == "light"
    ]
    _LOGGER.debug("Setting up %d light entities", len(entities))
    async_add_entities(entities)


class LedvanceTuyaLight(CoordinatorEntity[LedvanceTuyaCoordinator], LightEntity):
    """Representation of a Ledvance/Tuya light."""

    _attr_has_entity_name = True
    _attr_name = None  # uses device name

    def __init__(
        self,
        coordinator: LedvanceTuyaCoordinator,
        entry: ConfigEntry,
        device_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{device_id}"

        dev = self._device_data
        self._attr_device_info = build_device_info(dev)

        # Determine supported colour modes and DPS mappings from schema & dps
        codes = {item.get("code") for item in dev.schema}

        # 1. Power / switch DPS
        self._switch_dps: str | None = None
        for candidate in (DPS_SWITCH_LED, "switch", "switch_1", "led_switch", "light"):
            if candidate in dev.dps_map:
                self._switch_dps = dev.dps_map[candidate]
                break
        if self._switch_dps is None:
            if "20" in dev.dps:
                self._switch_dps = "20"
            elif "1" in dev.dps:
                self._switch_dps = "1"
            else:
                self._switch_dps = next(
                    (v for k, v in dev.dps_map.items() if "switch" in k or "led" in k or k == "light"),
                    None,
                )

        # 2. Brightness DPS
        self._bright_dps: str | None = None
        self._bright_code: str | None = None
        for candidate in (DPS_BRIGHT_VALUE, DPS_BRIGHT_VALUE_V2, "bright_value", "bright_value_v2", "brightness"):
            if candidate in dev.dps_map:
                self._bright_dps = dev.dps_map[candidate]
                self._bright_code = candidate
                break
        if self._bright_dps is None:
            for fallback_dp in ("22", "3", "2"):
                if fallback_dp in dev.dps:
                    self._bright_dps = fallback_dp
                    break

        # 3. Colour temperature DPS
        self._temp_dps: str | None = None
        self._temp_code: str | None = None
        for candidate in (DPS_TEMP_VALUE, "temp_value_v2", "colortemp_value"):
            if candidate in dev.dps_map:
                self._temp_dps = dev.dps_map[candidate]
                self._temp_code = candidate
                break
        if self._temp_dps is None:
            for fallback_dp in ("23", "4"):
                if fallback_dp in dev.dps:
                    self._temp_dps = fallback_dp
                    break

        # 4. Colour data DPS (RGB / HSV)
        self._colour_dps: str | None = None
        self._colour_code: str | None = None
        for candidate in (DPS_COLOUR_DATA, DPS_COLOUR_DATA_V2, "colour_data_hsv"):
            if candidate in dev.dps_map:
                self._colour_dps = dev.dps_map[candidate]
                self._colour_code = candidate
                break
        if self._colour_dps is None:
            for fallback_dp in ("24", "5"):
                if fallback_dp in dev.dps:
                    self._colour_dps = fallback_dp
                    break

        # 5. Mode DPS
        self._mode_dps: str | None = None
        for candidate in (DPS_WORK_MODE, "mode"):
            if candidate in dev.dps_map:
                self._mode_dps = dev.dps_map[candidate]
                break
        if self._mode_dps is None:
            for fallback_dp in ("21", "2"):
                if fallback_dp in dev.dps:
                    self._mode_dps = fallback_dp
                    break

        # Determine brightness range from schema
        if self._bright_code:
            self._bright_min, self._bright_max = get_integer_range(dev.schema, self._bright_code)
        else:
            self._bright_min, self._bright_max = (TUYA_BRIGHTNESS_MIN, TUYA_BRIGHTNESS_MAX)

        if self._temp_code:
            self._temp_min, self._temp_max = get_integer_range(dev.schema, self._temp_code)
        else:
            self._temp_min, self._temp_max = (TUYA_COLOUR_TEMP_MIN, TUYA_COLOUR_TEMP_MAX)

        # Build supported colour modes set
        supported: set[ColorMode] = set()
        if self._colour_dps:
            supported.add(ColorMode.HS)
        if self._temp_dps:
            supported.add(ColorMode.COLOR_TEMP)
        if self._bright_dps and not supported:
            supported.add(ColorMode.BRIGHTNESS)
        if not supported:
            supported.add(ColorMode.ONOFF)

        self._attr_supported_color_modes = supported
        # Default colour mode
        if ColorMode.HS in supported:
            self._attr_color_mode = ColorMode.HS
        elif ColorMode.COLOR_TEMP in supported:
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif ColorMode.BRIGHTNESS in supported:
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_color_mode = ColorMode.ONOFF

        self._attr_min_color_temp_kelvin = HA_COLOUR_TEMP_MIN_KELVIN
        self._attr_max_color_temp_kelvin = HA_COLOUR_TEMP_MAX_KELVIN

        # Scene / effect support
        self._scene_dps = dev.dps_map.get(DPS_SCENE_DATA) or dev.dps_map.get(DPS_SCENE_DATA_V2)
        work_mode_values = get_enum_range(dev.schema, DPS_WORK_MODE)
        effect_modes = [m for m in work_mode_values if m not in _COLOUR_WORK_MODES]
        if effect_modes:
            self._effect_modes: list[str] = effect_modes
            self._attr_effect_list = effect_modes
            self._attr_supported_features = LightEntityFeature.EFFECT
        else:
            self._effect_modes = []

    # ------------------------------------------------------------------

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
    def is_on(self) -> bool | None:
        if self._switch_dps is None:
            return None
        return bool(self._device_data.dps.get(self._switch_dps))

    @property
    def brightness(self) -> int | None:
        if self._bright_dps is None:
            return None
        raw = self._device_data.dps.get(self._bright_dps)
        if raw is None:
            return None
        return self._tuya_to_ha_brightness(int(raw))

    @property
    def color_temp_kelvin(self) -> int | None:
        if self._temp_dps is None:
            return None
        raw = self._device_data.dps.get(self._temp_dps)
        if raw is None:
            return None
        return self._tuya_to_ha_color_temp(int(raw))

    @property
    def hs_color(self) -> tuple[float, float] | None:
        if self._colour_dps is None:
            return None
        raw = self._device_data.dps.get(self._colour_dps)
        if not raw:
            return None
        return self._parse_colour_data(str(raw))

    @property
    def effect(self) -> str | None:
        """Return the active effect (scene/music mode), or None."""
        if not self._effect_modes or self._mode_dps is None:
            return None
        mode = self._device_data.dps.get(self._mode_dps)
        return mode if mode in self._effect_modes else None

    @property
    def color_mode(self) -> ColorMode:
        """Return current colour mode based on work_mode DPS."""
        if self._mode_dps is None:
            return self._attr_color_mode  # type: ignore[return-value]
        mode = self._device_data.dps.get(self._mode_dps)
        if mode == "colour" and ColorMode.HS in self._attr_supported_color_modes:
            return ColorMode.HS
        if mode == "white":
            if ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
                return ColorMode.COLOR_TEMP
            if ColorMode.BRIGHTNESS in self._attr_supported_color_modes:
                return ColorMode.BRIGHTNESS
        return self._attr_color_mode  # type: ignore[return-value]

    # ------------------------------------------------------------------

    async def async_turn_on(self, **kwargs: Any) -> None:
        dps_dict: dict[str, Any] = {}

        if self._switch_dps:
            dps_dict[self._switch_dps] = True

        # Handle color temperature
        if ATTR_COLOR_TEMP_KELVIN in kwargs and self._temp_dps:
            dps_dict[self._temp_dps] = self._ha_to_tuya_color_temp(kwargs[ATTR_COLOR_TEMP_KELVIN])
            if self._mode_dps:
                dps_dict[self._mode_dps] = "white"

        # Handle HS color
        elif ATTR_HS_COLOR in kwargs and self._colour_dps:
            brightness = kwargs.get(ATTR_BRIGHTNESS)
            dps_dict[self._colour_dps] = self._encode_colour_data(kwargs[ATTR_HS_COLOR], brightness)
            if self._mode_dps:
                dps_dict[self._mode_dps] = "colour"

        # Handle brightness
        if ATTR_BRIGHTNESS in kwargs and self._bright_dps:
            dps_dict[self._bright_dps] = self._ha_to_tuya_brightness(kwargs[ATTR_BRIGHTNESS])
            if self._mode_dps and ATTR_HS_COLOR not in kwargs and ATTR_COLOR_TEMP_KELVIN not in kwargs:
                current_mode = self._device_data.dps.get(self._mode_dps)
                if current_mode == "colour" and self._colour_dps:
                    current_hs = self.hs_color
                    if current_hs:
                        dps_dict[self._colour_dps] = self._encode_colour_data(current_hs, kwargs[ATTR_BRIGHTNESS])
                elif current_mode not in ("colour", "scene", "music"):
                    dps_dict[self._mode_dps] = "white"

        # Handle effects
        if ATTR_EFFECT in kwargs and self._mode_dps:
            effect = kwargs[ATTR_EFFECT]
            if effect in self._effect_modes:
                dps_dict[self._mode_dps] = effect

        await async_send_command(
            self.hass, self.coordinator.api, self._device_data, dps_dict
        )
        self.coordinator.async_optimistic_update(self._device_id, dps_dict)

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self._switch_dps is None:
            return
        dps_dict = {self._switch_dps: False}
        await async_send_command(
            self.hass,
            self.coordinator.api,
            self._device_data,
            dps_dict,
        )
        self.coordinator.async_optimistic_update(self._device_id, dps_dict)

    # ------------------------------------------------------------------
    # Value conversion helpers
    # ------------------------------------------------------------------

    def _tuya_to_ha_brightness(self, value: int) -> int:
        """Map Tuya brightness (e.g. 10-1000) to HA brightness (1-255)."""
        lo, hi = self._bright_min, self._bright_max
        clamped = max(lo, min(hi, value))
        return round((clamped - lo) / (hi - lo) * 254 + 1)

    def _ha_to_tuya_brightness(self, value: int) -> int:
        """Map HA brightness (1-255) to Tuya brightness range."""
        lo, hi = self._bright_min, self._bright_max
        return round((value - 1) / 254 * (hi - lo) + lo)

    def _tuya_to_ha_color_temp(self, value: int) -> int:
        """Map Tuya color temp (0-1000) to HA kelvin (2000-6536).

        Tuya 0 = coldest (high K), Tuya max = warmest (low K).
        """
        lo, hi = self._temp_min, self._temp_max
        ratio = (value - lo) / max(hi - lo, 1)
        # ratio 0 → max_kelvin (cold), ratio 1 → min_kelvin (warm)
        return round(
            HA_COLOUR_TEMP_MAX_KELVIN
            - ratio * (HA_COLOUR_TEMP_MAX_KELVIN - HA_COLOUR_TEMP_MIN_KELVIN)
        )

    def _ha_to_tuya_color_temp(self, kelvin: int) -> int:
        """Map HA kelvin to Tuya color temp range."""
        lo, hi = self._temp_min, self._temp_max
        ratio = (HA_COLOUR_TEMP_MAX_KELVIN - kelvin) / max(
            HA_COLOUR_TEMP_MAX_KELVIN - HA_COLOUR_TEMP_MIN_KELVIN, 1
        )
        return round(lo + ratio * (hi - lo))

    @staticmethod
    def _parse_colour_data(raw: str) -> tuple[float, float] | None:
        """Parse Tuya colour_data (JSON, HHHHSSSSVVVV, RRGGBBHHHHSSVV, or RRGGBB) to HS tuple."""
        raw = raw.strip()
        try:
            if raw.startswith("{"):
                data = json.loads(raw)
                h = float(data.get("h", 0))
                s = float(data.get("s", 0))
                scale_s = 10.0 if s > 100 else 1.0
                return (h, s / scale_s)
            if len(raw) == 14:
                # Type A: RRGGBBHHHHSSVV
                h = int(raw[6:10], 16)
                s = int(raw[10:12], 16)
                return (float(h), float(s) / 255.0 * 100.0)
            if len(raw) == 12:
                # Type B: HHHHSSSSVVVV: H in 0-360, S and V in 0-1000
                h = int(raw[0:4], 16)
                s = int(raw[4:8], 16)
                return (float(h), float(s) / 10.0)
            if len(raw) == 6:
                # RRGGBB
                r = int(raw[0:2], 16)
                g = int(raw[2:4], 16)
                b = int(raw[4:6], 16)
                return color_RGB_to_hs(r, g, b)
        except (ValueError, IndexError, json.JSONDecodeError):
            pass
        return None

    def _encode_colour_data(self, hs: tuple[float, float], brightness: int | None = None) -> str:
        """Encode HA HS to Tuya colour format (JSON, RRGGBBHHHHSSVV, or HHHHSSSSVVVV)."""
        h = int(hs[0])
        s = int(hs[1] * 10)  # 0-1000
        v = round(brightness / 255 * 1000) if brightness is not None else 1000
        v = max(10, min(1000, v))

        current_raw = str(self._device_data.dps.get(self._colour_dps) or "")
        if current_raw.startswith("{") or "h" in current_raw:
            return json.dumps({"h": h, "s": s, "v": v})
        if len(current_raw) == 14:
            rgb = color_hs_to_RGB(hs[0], hs[1])
            s_byte = int(hs[1] / 100.0 * 255)
            v_byte = int(v / 1000.0 * 255)
            return f"{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}{h:04X}{s_byte:02X}{v_byte:02X}"
        return f"{h:04X}{s:04X}{v:04X}"
