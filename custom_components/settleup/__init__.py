"""The Settle Up integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import SettleUpCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

type SettleUpConfigEntry = ConfigEntry[SettleUpCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register integration-wide services once per process."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SettleUpConfigEntry) -> bool:
    """Set up the SettleUp integration from a config entry."""
    coordinator = SettleUpCoordinator(hass, entry)
    entry.runtime_data = coordinator

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: SettleUpConfigEntry) -> None:
    """Reload the integration when config options change."""
    _LOGGER.debug("Options changed, reloading SettleUp")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: SettleUpConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Allow deletion of a group device only when it no longer exists upstream."""
    live_group_ids = {g.group_id for g in entry.runtime_data.data or []}
    return not any(
        identifier in live_group_ids
        for domain, identifier in device_entry.identifiers
        if domain == DOMAIN
    )


async def async_unload_entry(hass: HomeAssistant, entry: SettleUpConfigEntry) -> bool:
    """Unload a SettleUp config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_shutdown()
    return unload_ok
