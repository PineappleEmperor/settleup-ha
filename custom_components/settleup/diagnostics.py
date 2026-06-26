"""Diagnostics support for the SettleUp integration."""
from __future__ import annotations

from typing import Any, cast

# async_redact_data is generically typed in HA and resolves partially-unknown here.
from homeassistant.components.diagnostics import (
    async_redact_data,  # pyright: ignore[reportUnknownVariableType]
)
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY, CONF_EMAIL
from .coordinator import SettleUpConfigEntry

TO_REDACT = {CONF_API_KEY, CONF_EMAIL, CONF_PASSWORD, "token", "localId", "user_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SettleUpConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry, with credentials redacted."""
    coordinator = entry.runtime_data
    groups = coordinator.data or []
    payload: dict[str, Any] = {
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
    }
    # async_redact_data is generically typed in HA; the to_redact set widens the
    # result to a partially-unknown dict, so cast back to the declared shape.
    return cast("dict[str, Any]", async_redact_data(payload, TO_REDACT))
