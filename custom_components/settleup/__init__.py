"""The SettleUp integration."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .coordinator import ExampleCoordinator
from .services import ExampleServicesSetup

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR
]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

type MyConfigEntry = ConfigEntry[RuntimeData]

@dataclass
class RuntimeData:
    """Class to hold your data."""

    coordinator: DataUpdateCoordinator
    cancel_update_listener: Callable


async def async_setup_entry(hass: HomeAssistant, config_entry: MyConfigEntry) -> bool:
    """Set up the SettleUp integration."""
    _LOGGER.info("Setting up the SettleUp integration")

    # Check if the entry is already set up
    if DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]:
        raise ValueError(
            f"Config entry {config_entry.title} ({config_entry.entry_id}) for {DOMAIN} has already been setup!"
        )

    # ----------------------------------------------------------------------------
    # Initialise the coordinator that manages data updates from your api.
    # This is defined in coordinator.py
    # ----------------------------------------------------------------------------
    coordinator = ExampleCoordinator(hass, config_entry)

    # ----------------------------------------------------------------------------
    # Perform an initial data load from api.
    # async_config_entry_first_refresh() is special in that it does not log errors
    # if it fails.
    # ----------------------------------------------------------------------------
    await coordinator.async_config_entry_first_refresh()

    # ----------------------------------------------------------------------------
    # Test to see if api initialised correctly, else raise ConfigNotReady to make
    # HA retry setup.
    # Change this to match how your api will know if connected or successful
    # update.
    # ----------------------------------------------------------------------------
    if not coordinator.data:
        raise ConfigEntryNotReady

    # ----------------------------------------------------------------------------
    # Initialise a listener for config flow options changes.
    # This will be removed automatically if the integraiton is unloaded.
    # See config_flow for defining an options setting that shows up as configure
    # on the integration.
    # If you do not want any config flow options, no need to have listener.
    # ----------------------------------------------------------------------------
    cancel_update_listener = config_entry.async_on_unload(
        config_entry.add_update_listener(_async_update_listener)
    )

    # ----------------------------------------------------------------------------
    # Add the coordinator and update listener to your config entry to make
    # accessible throughout your integration
    # ----------------------------------------------------------------------------
    config_entry.runtime_data = RuntimeData(coordinator, cancel_update_listener)

    # ----------------------------------------------------------------------------
    # Setup platforms (based on the list of entity types in PLATFORMS defined above)
    # This calls the async_setup method in each of your entity type files.
    # ----------------------------------------------------------------------------
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # ----------------------------------------------------------------------------
    # Setup global services
    # This can be done here but included in a seperate file for ease of reading.
    # See also light.py for entity services examples
    # ----------------------------------------------------------------------------
    ExampleServicesSetup(hass, config_entry)

    # Store integration data in hass.data
    hass.data[DOMAIN] = {}

    return True

async def _async_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle config options update.

    Reload the integration when the options change.
    Called from our listener created above.
    """
    await hass.config_entries.async_reload(config_entry.entry_id)

async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Delete device if selected from UI.

    Adding this function shows the delete device option in the UI.
    Remove this function if you do not want that option.
    You may need to do some checks here before allowing devices to be removed.
    """
    return True

async def async_unload_entry(hass: HomeAssistant, config_entry: MyConfigEntry) -> bool:
    """Unload a config entry.

    This is called when you remove your integration or shutdown HA.
    If you have created any custom services, they need to be removed here too.
    """

    # Unload services
    for service in hass.services.async_services_for_domain(DOMAIN):
        hass.services.async_remove(DOMAIN, service)

    # Unload platforms and return result
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)