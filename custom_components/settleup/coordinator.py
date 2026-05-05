"""DataUpdateCoordinator for the SettleUp integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SettleUpAPI, SettleUpGroup
from .const import CONF_API_KEY, CONF_EMAIL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

OPT_KNOWN_GROUPS = "known_groups"


class SettleUpCoordinator(DataUpdateCoordinator[list[SettleUpGroup]]):
    """Coordinator that fetches all groups."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise with config entry credentials."""
        self.api = SettleUpAPI(
            api_key  = entry.data[CONF_API_KEY],
            email    = entry.data[CONF_EMAIL],
            password = entry.data[CONF_PASSWORD],
            session  = async_get_clientsession(hass),
            sandbox  = entry.data.get("sandbox", False),
        )
        super().__init__(
            hass,
            _LOGGER,
            name            = f"{DOMAIN} ({entry.unique_id})",
            update_method   = self._async_update_data,
            update_interval = timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry    = entry,
        )

    async def _async_update_data(self) -> list[SettleUpGroup]:
        """Fetch the latest data from SettleUp."""
        try:
            raw_groups = await self.api.get_user_groups()
            groups: list[SettleUpGroup] = []
            for group_id, group_info in raw_groups.items():
                member_id = group_info.get("memberId", "")
                group = await SettleUpGroup.from_api(self.api, group_id, member_id)
                groups.append(group)
        except RuntimeError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error communicating with SettleUp: {err}") from err

        self._persist_known_entities(groups)
        return groups

    def _persist_known_entities(self, groups: list[SettleUpGroup]) -> None:
        """Cache data for startup."""
        assert self.config_entry is not None
        known: dict[str, dict] = {
            g.group_id: {
                "name"     : g.name,
                "currency" : g.converted_to_currency,
                "members"  : {m.member_id: m.name for m in g.members},
            }
            for g in groups
        }
        if known != self.config_entry.options.get(OPT_KNOWN_GROUPS):
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                options={**self.config_entry.options, OPT_KNOWN_GROUPS: known},
            )
