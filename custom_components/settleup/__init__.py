"""The SettleUp integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import SettleUpCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

type SettleUpConfigEntry = ConfigEntry[SettleUpCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SettleUpConfigEntry) -> bool:
    """Set up the SettleUp integration."""
    _LOGGER.info("Setting up SettleUp integration")

    try:
        coordinator = SettleUpCoordinator(hass, entry)
        _LOGGER.debug("SettleUpCoordinator initialised")

        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _LOGGER.debug("Platforms forwarded: %s", PLATFORMS)

        await coordinator.async_refresh()
        _LOGGER.debug(
            "Initial refresh complete (success=%s)",
            coordinator.last_update_success
        )

        async_setup_services(hass)
        _LOGGER.debug("Services registered")

        entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    except Exception:
        _LOGGER.exception("Unexpected error setting up SettleUp")
        raise

    _LOGGER.info("SettleUp setup complete")
    return True


async def _async_update_listener(hass: HomeAssistant, entry: SettleUpConfigEntry) -> None:
    """Reload the integration when config options change."""
    _LOGGER.debug("Options changed, reloading SettleUp")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SettleUpConfigEntry) -> bool:
    """Unload a SettleUp config entry."""
    _LOGGER.info("Unloading SettleUp integration for entry_id=%s", entry.entry_id)

    for service in hass.services.async_services_for_domain(DOMAIN):
        hass.services.async_remove(DOMAIN, service)
    _LOGGER.debug("Services removed")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    _LOGGER.debug("Platform unload result: %s", unload_ok)

    return unload_ok
