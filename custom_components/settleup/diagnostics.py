"""Diagnostics support for the SettleUp integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY, CONF_EMAIL

TO_REDACT = {CONF_API_KEY, CONF_EMAIL, CONF_PASSWORD, "token", "localId", "user_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: Any
) -> dict[str, Any]:
    """Return diagnostics for a config entry, with credentials redacted."""
    coordinator = entry.runtime_data
    groups = coordinator.data or []
    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "last_update_success": coordinator.last_update_success,
            "group_count": len(groups),
            "groups": [
                {
                    "group_id": g.group_id,
                    "name": g.name,
                    "currency": g.converted_to_currency,
                    "member_count": len(g.members),
                    "debt_count": len(g.debts),
                }
                for g in groups
            ],
        },
        TO_REDACT,
    )
