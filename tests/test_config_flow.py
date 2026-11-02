"""Tests for the Ledvance/Tuya config flow."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from custom_components.hass_ledvance.const import CONF_REGION, DOMAIN
from custom_components.hass_ledvance.exceptions import CannotConnect, InvalidAuthentication

VALID_INPUT = {
    CONF_EMAIL: "user@example.com",
    CONF_PASSWORD: "secret123",
    CONF_REGION: "EU",
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests in this module."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_validate(exc: Exception | None = None):
    """Patch _validate_credentials to raise exc or succeed silently."""
    if exc is None:
        return patch(
            "custom_components.hass_ledvance.config_flow._validate_credentials",
            return_value=None,
        )
    return patch(
        "custom_components.hass_ledvance.config_flow._validate_credentials",
        side_effect=exc,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestConfigFlowInitialForm:
    async def test_shows_form_on_first_visit(self, hass):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}


class TestConfigFlowSuccess:
    async def test_creates_entry_on_valid_credentials(self, hass):
        with _patch_validate():
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=VALID_INPUT
            )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == "user@example.com (EU)"
        assert result["data"] == VALID_INPUT

    async def test_entry_unique_id_is_email_plus_region(self, hass):
        with _patch_validate():
            await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=VALID_INPUT
            )

        entry = hass.config_entries.async_entries(DOMAIN)[0]
        assert entry.unique_id == "user@example.com_EU"


class TestConfigFlowErrors:
    async def test_invalid_auth_shows_error(self, hass):
        with _patch_validate(InvalidAuthentication()):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=VALID_INPUT
            )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_auth"

    async def test_cannot_connect_shows_error(self, hass):
        with _patch_validate(CannotConnect()):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=VALID_INPUT
            )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"

    async def test_unexpected_exception_shows_unknown_error(self, hass):
        with _patch_validate(RuntimeError("boom")):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=VALID_INPUT
            )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"]["base"] == "unknown"


class TestConfigFlowDuplicatePrevention:
    async def test_aborts_if_same_account_already_configured(self, hass):
        with _patch_validate():
            # First setup
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=VALID_INPUT
            )

            # Second attempt with identical credentials
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=VALID_INPUT
            )

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "already_configured"

    async def test_allows_different_region_for_same_email(self, hass):
        with _patch_validate():
            # EU entry
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=VALID_INPUT
            )

            # US entry — different unique_id
            us_input = {**VALID_INPUT, CONF_REGION: "US"}
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=us_input
            )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
