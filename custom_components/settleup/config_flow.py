"""Config flow for the SettleUp integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SettleUpAPI
from .const import (
    CONF_API_KEY,
    CONF_EMAIL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    OPT_SCAN_INTERVAL,
)

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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: object) -> OptionsFlow:
        """Return the options flow handler."""
        return SettleUpOptionsFlow()

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

    async def _async_validate(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Validate credentials, returning a (possibly empty) errors dict."""
        errors: dict[str, str] = {}
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
            _LOGGER.exception("Unexpected exception validating SettleUp credentials")
            errors["base"] = "unknown"
        return errors

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Begin reauth flow when credentials are rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow the user to update connection settings."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            errors = await self._async_validate(user_input)
            if not errors:
                return self.async_update_reload_and_abort(
                    reconfigure_entry, data=user_input
                )

        return self.async_show_form(
            step_id     = "reconfigure",
            data_schema = self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, reconfigure_entry.data
            ),
            errors      = errors,
        )

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show form to update credentials after auth failure."""
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
                _LOGGER.warning("SettleUp reauth failed: %s", err)
                errors["base"] = "invalid_auth"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during SettleUp reauth")
                errors["base"] = "unknown"

            if not errors:
                reauth_entry = self._get_reauth_entry()
                self.hass.config_entries.async_update_entry(reauth_entry, data=user_input)
                await self.hass.config_entries.async_reload(reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id     = "reauth_confirm",
            data_schema = STEP_USER_SCHEMA,
            errors      = errors,
        )


class SettleUpOptionsFlow(OptionsFlow):
    """Options flow to configure the polling interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options form."""
        if user_input is not None:
            return self.async_create_entry(data={
                **self.config_entry.options,
                OPT_SCAN_INTERVAL: user_input[OPT_SCAN_INTERVAL],
            })

        current = self.config_entry.options.get(
            OPT_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL // 60
        )
        return self.async_show_form(
            step_id     = "init",
            data_schema = vol.Schema({
                vol.Required(OPT_SCAN_INTERVAL, default=current): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
            }),
        )
