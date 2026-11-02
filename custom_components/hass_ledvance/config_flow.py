"""Config flow for Ledvance/Tuya integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .api import TuyaAPI
from .const import CONF_REGION, DEFAULT_REGION, DOMAIN, REGIONS
from .exceptions import CannotConnect, InvalidAuthentication

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_REGION, default=DEFAULT_REGION): vol.In(list(REGIONS)),
    }
)


async def _validate_credentials(
    hass: HomeAssistant, data: dict[str, Any]
) -> None:
    """Raise on auth or connectivity failure."""
    region_cfg = REGIONS[data[CONF_REGION]]
    api = TuyaAPI(
        email=data[CONF_EMAIL],
        password=data[CONF_PASSWORD],
        endpoint=region_cfg["endpoint"],
        country_code=region_cfg["country_code"],
    )
    await hass.async_add_executor_job(api.login)


class LedvanceTuyaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Ledvance/Tuya config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await _validate_credentials(self.hass, user_input)
            except InvalidAuthentication:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during config flow")
                errors["base"] = "unknown"
            else:
                # Prevent duplicate entries for same account
                await self.async_set_unique_id(
                    f"{user_input[CONF_EMAIL]}_{user_input[CONF_REGION]}"
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"{user_input[CONF_EMAIL]} ({user_input[CONF_REGION]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
