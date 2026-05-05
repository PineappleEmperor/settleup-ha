"""Config flow for the SettleUp integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SettleUpAPI
from .const import CONF_API_KEY, CONF_EMAIL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY):  str,
        vol.Required(CONF_EMAIL):    str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class SettleUpConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SettleUp."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api = SettleUpAPI(
                api_key  = user_input[CONF_API_KEY],
                email    = user_input[CONF_EMAIL],
                password = user_input[CONF_PASSWORD],
                session  = async_get_clientsession(self.hass),
            )
            try:
                await api.login()
            except RuntimeError as err:
                _LOGGER.warning("SettleUp login failed: %s", err)
                errors["base"] = "invalid_auth"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during SettleUp setup")
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id(api.user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title = user_input[CONF_EMAIL],
                    data  = user_input,
                )

        return self.async_show_form(
            step_id     = "user",
            data_schema = STEP_USER_SCHEMA,
            errors      = errors,
        )
