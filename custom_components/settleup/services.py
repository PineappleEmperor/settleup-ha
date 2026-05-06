"""Services for the Settle Up integration."""
from __future__ import annotations

import logging
import time
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)

from .const import DOMAIN
from .coordinator import SettleUpCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_ADD_TRANSACTION = "add_transaction"
SERVICE_SETTLE_DEBT     = "settle_debt"

ADD_TRANSACTION_SCHEMA = vol.Schema(
    {
        vol.Required("group"):                           cv.string,
        vol.Required("purpose"):                         cv.string,
        vol.Required("amount"):                          vol.Coerce(float),
        vol.Optional("currency_code"):                   vol.All(cv.string, vol.Length(min=3, max=3)),
        vol.Required("paid_by"):                         cv.entity_id,
        vol.Required("for_members"):                     vol.All(cv.ensure_list, [cv.entity_id]),
        vol.Optional("weights"):                         vol.All(cv.ensure_list, [vol.Coerce(float)]),
        vol.Optional("member_amounts"):                  vol.All(cv.ensure_list, [vol.Coerce(float)]),
        vol.Optional("category", default="general"):     cv.string,
    }
)

SETTLE_DEBT_SCHEMA = vol.Schema(
    {
        vol.Required("group"):                           cv.string,
        vol.Required("from_member"):                     cv.entity_id,
        vol.Required("to_member"):                       cv.entity_id,
        vol.Required("amount"):                          vol.Coerce(float),
        vol.Optional("currency_code"):                   vol.All(cv.string, vol.Length(min=3, max=3)),
    }
)

# ---------------------------------------------------------------------------

def _get_coordinator(hass: HomeAssistant) -> SettleUpCoordinator:
    for entry in hass.config_entries.async_entries(DOMAIN):
        return entry.runtime_data
    raise HomeAssistantError("No Settle Up integration loaded")


def _group_id_from_device(hass: HomeAssistant, device_id: str) -> str:
    """Resolve an HA device ID → Firebase group_id via device identifiers."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise HomeAssistantError(f"Device {device_id!r} not found")
    for domain, identifier in device.identifiers:
        if domain == DOMAIN:
            return identifier
    raise HomeAssistantError(f"Device {device_id!r} is not a Settle Up group")


def _member_id_from_entity(hass: HomeAssistant, entity_id: str, group_id: str) -> str:
    """Resolve a member sensor entity_id → Firebase member_id."""
    registry = er.async_get(hass)
    entry    = registry.async_get(entity_id)
    if not entry or not entry.unique_id:
        raise HomeAssistantError(f"Unknown entity: {entity_id}")
    uid    = entry.unique_id
    prefix = f"{DOMAIN}_{group_id}_"
    suffix = "_balance"
    if uid.startswith(prefix) and uid.endswith(suffix):
        return uid[len(prefix):-len(suffix)]
    raise HomeAssistantError(f"{entity_id} is not a Settle Up member sensor for group {group_id}")


def _group_currency(coordinator: SettleUpCoordinator, group_id: str) -> str:
    """Return the group's configured currency, falling back to GBP."""
    if coordinator.data:
        for group in coordinator.data:
            if group.group_id == group_id:
                return group.converted_to_currency
    return "GBP"

# ---------------------------------------------------------------------------

def async_setup_services(hass: HomeAssistant) -> None:
    """Register Settle Up services."""

    async def handle_add_transaction(call: ServiceCall) -> None:
        """Add an expense transaction to a Settle Up group."""
        coordinator    = _get_coordinator(hass)
        group_id       = _group_id_from_device(hass, call.data["group"])
        paid_by_id     = _member_id_from_entity(hass, call.data["paid_by"], group_id)
        for_ids        = [
            _member_id_from_entity(hass, eid, group_id)
            for eid in call.data["for_members"]
        ]
        amount         = call.data["amount"]
        weights        = call.data.get("weights")
        member_amounts = call.data.get("member_amounts")
        currency       = call.data.get("currency_code") or _group_currency(coordinator, group_id)

        if weights and member_amounts:
            raise HomeAssistantError("Specify either weights or member_amounts, not both")

        if weights:
            if len(weights) != len(for_ids):
                raise HomeAssistantError(
                    f"weights has {len(weights)} values but for_members has {len(for_ids)}"
                )
            items: list[dict[str, Any]] = [
                {
                    "amount"  : str(amount),
                    "forWhom" : [
                        {"memberId": mid, "weight": str(w)}
                        for mid, w in zip(for_ids, weights, strict=True)
                    ],
                }
            ]

        elif member_amounts:
            if len(member_amounts) != len(for_ids):
                raise HomeAssistantError(
                    f"member_amounts has {len(member_amounts)} values but for_members has {len(for_ids)}"
                )
            items = [
                {"amount": str(a), "forWhom": [{"memberId": mid, "weight": "1"}]}
                for mid, a in zip(for_ids, member_amounts, strict=True)
            ]

        else:
            n      = len(for_ids)
            weight = str(round(1 / n, 6)) if n > 1 else "1"
            items  = [
                {
                    "amount"  : str(amount),
                    "forWhom" : [{"memberId": mid, "weight": weight} for mid in for_ids],
                }
            ]

        transaction: dict[str, Any] = {
            "type"              : "expense",
            "purpose"           : call.data["purpose"],
            "category"          : call.data["category"],
            "currencyCode"      : currency,
            "dateTime"          : int(time.time() * 1000),
            "fixedExchangeRate" : False,
            "whoPaid"           : [{"memberId": paid_by_id, "weight": str(amount)}],
            "items"             : items,
        }
        try:
            key = await coordinator.api.add_transaction(group_id, transaction)
            _LOGGER.debug("Added transaction %s to group %s", key, group_id)
        except RuntimeError as err:
            raise HomeAssistantError(str(err)) from err

    async def handle_settle_debt(call: ServiceCall) -> None:
        """Record a debt settlement between two members of a Settle Up group."""
        coordinator = _get_coordinator(hass)
        group_id    = _group_id_from_device(hass, call.data["group"])
        from_member = _member_id_from_entity(hass, call.data["from_member"], group_id)
        to_member   = _member_id_from_entity(hass, call.data["to_member"], group_id)
        amount      = call.data["amount"]
        currency    = call.data.get("currency_code") or _group_currency(coordinator, group_id)

        transaction: dict[str, Any] = {
            "type"              : "transfer",
            "purpose"           : "Settlement",
            "category"          : "general",
            "currencyCode"      : currency,
            "dateTime"          : int(time.time() * 1000),
            "fixedExchangeRate" : False,
            "whoPaid"           : [{"memberId": from_member, "weight": str(amount)}],
            "items"             : [
                {
                    "amount"  : str(amount),
                    "forWhom" : [{"memberId": to_member, "weight": "1"}],
                }
            ],
        }
        try:
            key = await coordinator.api.add_transaction(group_id, transaction)
            _LOGGER.debug("Recorded settlement %s in group %s", key, group_id)
        except RuntimeError as err:
            raise HomeAssistantError(str(err)) from err

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_TRANSACTION, handle_add_transaction, schema=ADD_TRANSACTION_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SETTLE_DEBT, handle_settle_debt, schema=SETTLE_DEBT_SCHEMA
    )
