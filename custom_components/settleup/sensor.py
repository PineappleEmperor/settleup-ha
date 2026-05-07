"""Sensor platform for the Settle Up integration."""
from __future__ import annotations

from datetime import UTC, datetime
from itertools import combinations
import logging
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import SettleUpGroup, SettleUpMember
from .const import DOMAIN
from .coordinator import SettleUpCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Settle Up sensors."""
    coordinator: SettleUpCoordinator = entry.runtime_data
    known_group_ids:  set[str]                       = set()
    known_member_ids: dict[str, set[str]]             = {}
    known_pair_ids:   dict[str, set[tuple[str, str]]] = {}

    @callback
    def _async_add_new_entities() -> None:
        """Create sensors for any groups/members/pairs not yet registered."""
        new_entities: list[SensorEntity] = []

        for group in coordinator.data or []:
            gid  = group.group_id
            name = group.name
            if gid not in known_group_ids:
                known_group_ids.add(gid)
                known_member_ids[gid] = set()
                new_entities.append(SettleUpGroupSensor(coordinator, gid, name))

            for member in group.members:
                mid = member.member_id
                if mid not in known_member_ids.get(gid, set()):
                    known_member_ids.setdefault(gid, set()).add(mid)
                    new_entities.append(SettleUpMemberSensor(coordinator, gid, mid))

            # Pre-create all canonical pairs sorted by member name so sensors
            # never flip direction or go unavailable when debts are settled/reversed.
            group_pairs = known_pair_ids.setdefault(gid, set())
            sorted_members = sorted(
                group.members, key=lambda m: (m.name.casefold(), m.member_id)
            )
            for m_a, m_b in combinations(sorted_members, 2):
                pair = (m_a.member_id, m_b.member_id)
                if pair not in group_pairs:
                    group_pairs.add(pair)
                    new_entities.append(
                        SettleUpDebtSensor(coordinator, gid, m_a.member_id, m_b.member_id)
                    )

        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))
    _async_add_new_entities()

# ---------------------------------------------------------------------------

def _group_device(group_id: str, group: SettleUpGroup | None, cached_name: str = "") -> DeviceInfo:
    """Return DeviceInfo that places an entity on the correct group device."""
    friendly = (group.name if group else None) or cached_name
    return DeviceInfo(
        identifiers  = {(DOMAIN, group_id)},
        name         = f"Settle Up {friendly}",
        manufacturer = "Settle Up",
        model        = "Group",
    )

# ---------------------------------------------------------------------------

class SettleUpGroupSensor(CoordinatorEntity[SettleUpCoordinator], RestoreSensor):
    """Timestamp of the last group transaction, with debts and members in attributes."""

    _attr_has_entity_name = True
    _attr_device_class    = SensorDeviceClass.TIMESTAMP
    _attr_icon            = "mdi:receipt-text-clock"

    def __init__(self, coordinator: SettleUpCoordinator, group_id: str, cached_name: str = "") -> None:
        super().__init__(coordinator)
        self._group_id       = group_id
        self._cached_name    = cached_name
        self._attr_unique_id = f"{DOMAIN}_{group_id}_last_transaction"
        self._attr_name      = "Last Transaction"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self.coordinator.data is None:
            last = await self.async_get_last_sensor_data()
            if last is not None:
                self._attr_native_value = last.native_value
                self.async_write_ha_state()

    @property
    def _group(self) -> SettleUpGroup | None:
        return next(
            (g for g in (self.coordinator.data or []) if g.group_id == self._group_id),
            None,
        )

    @property
    def available(self) -> bool:
        return self._group is not None or self._attr_native_value is not None

    @property
    def native_value(self) -> datetime | None:
        """Return datetime of the most recent transaction, or None if none exist."""
        group = self._group
        if group is None:
            return self._attr_native_value  # type: ignore[return-value]
        if not group.recent_transactions:
            return None
        ts_ms = group.recent_transactions[0].get("dateTime", 0)
        return datetime.fromtimestamp(ts_ms / 1000, tz=UTC)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the group device."""
        return _group_device(self._group_id, self._group, self._cached_name)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        group = self._group
        if group is None:
            return {}
        member_names = {m.member_id: m.name for m in group.members}
        txn_attrs: list[dict[str, Any]] = []
        for t in group.recent_transactions:
            ts_ms   = t.get("dateTime", 0)
            paid_by = [
                member_names.get(p["memberId"], p["memberId"])
                for p in t.get("whoPaid", [])
            ]
            total = sum(float(i.get("amount", 0)) for i in t.get("items", []))
            txn_attrs.append({
                "purpose"  : t.get("purpose"),
                "type"     : t.get("type"),
                "amount"   : total,
                "currency" : t.get("currencyCode"),
                "paid_by"  : paid_by,
                "date"     : datetime.fromtimestamp(ts_ms / 1000, tz=UTC).isoformat(),
            })
        return {
            "currency"            : group.converted_to_currency,
            "main_member"         : member_names.get(group.main_member_id),
            "members"             : [
                {"name": m.name, "member_id": m.member_id, "active": m.active}
                for m in group.members
            ],
            "debts"               : [
                {
                    "from"   : member_names.get(d.from_member, d.from_member),
                    "to"     : member_names.get(d.to_member, d.to_member),
                    "amount" : d.amount,
                }
                for d in group.debts
            ],
            "recent_transactions" : txn_attrs,
        }

# ---------------------------------------------------------------------------

class SettleUpMemberSensor(CoordinatorEntity[SettleUpCoordinator], SensorEntity):
    """A specific member's net balance within a group."""

    _attr_has_entity_name = True
    _attr_device_class    = SensorDeviceClass.MONETARY
    _attr_state_class     = SensorStateClass.MEASUREMENT
    _attr_icon            = "mdi:account-cash"

    def __init__(
        self,
        coordinator: SettleUpCoordinator,
        group_id: str,
        member_id: str,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._group_id       = group_id
        self._member_id      = member_id
        self._attr_unique_id = f"{DOMAIN}_{group_id}_{member_id}_balance"

    @property
    def _group(self) -> SettleUpGroup | None:
        """Return the live group data for this sensor, or None if not found."""
        return next(
            (g for g in (self.coordinator.data or []) if g.group_id == self._group_id),
            None,
        )

    @property
    def _member(self) -> SettleUpMember | None:
        """Return this member's data from the group, or None if not found."""
        group = self._group
        if group is None:
            return None
        return next((m for m in group.members if m.member_id == self._member_id), None)

    @property
    def name(self) -> str:
        """Return member display name."""
        member = self._member
        return (member.name if member else None) or self._member_id

    @property
    def available(self) -> bool:
        """Return True if the coordinator succeeded and this member exists in the group."""
        return self.coordinator.last_update_success and self._member is not None

    @property
    def native_value(self) -> float | None:
        """Return this member's net balance (positive = owed money, negative = owes money)."""
        group = self._group
        if group is None:
            return None
        return group.member_balance(self._member_id)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the group's display currency."""
        group = self._group
        return group.converted_to_currency if group else None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the group device."""
        return _group_device(self._group_id, self._group)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        group  = self._group
        member = self._member
        if not group or not member:
            return {}
        member_names = {m.member_id: m.name for m in group.members}
        owes: list[dict[str, Any]] = []
        owed_by: list[dict[str, Any]] = []
        for debt in member.debts:
            if debt.from_member == self._member_id:
                owes.append({
                    "to"     : member_names.get(debt.to_member, debt.to_member),
                    "amount" : debt.amount,
                })
            else:
                owed_by.append({
                    "from"   : member_names.get(debt.from_member, debt.from_member),
                    "amount" : debt.amount,
                })
        return {"owes": owes, "owed_by": owed_by}

# ---------------------------------------------------------------------------

class SettleUpDebtSensor(CoordinatorEntity[SettleUpCoordinator], SensorEntity):
    """Net debt between a canonical pair of members, ordered alphabetically by name.

    Positive  → first member owes second.
    Negative  → second member owes first.
    Zero      → settled (no debt in either direction).

    The sensor never goes unavailable due to a debt direction flip; it simply
    changes sign.
    """

    _attr_has_entity_name                 = True
    _attr_state_class                     = SensorStateClass.MEASUREMENT
    _attr_icon                            = "mdi:cash-clock"
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: SettleUpCoordinator,
        group_id: str,
        first_id: str,
        second_id: str,
    ) -> None:
        """Initialise the sensor for a canonical member pair."""
        super().__init__(coordinator)
        self._group_id       = group_id
        self._first_id       = first_id
        self._second_id      = second_id
        self._attr_unique_id = f"{DOMAIN}_{group_id}_{first_id}_{second_id}_pair"

    @property
    def _group(self) -> SettleUpGroup | None:
        """Return the live group data for this sensor, or None if not found."""
        return next(
            (g for g in (self.coordinator.data or []) if g.group_id == self._group_id),
            None,
        )

    def _member_name(self, member_id: str) -> str:
        """Return a member's display name, falling back to their ID."""
        group = self._group
        if group is None:
            return member_id
        member = next((m for m in group.members if m.member_id == member_id), None)
        return member.name if member else member_id

    @property
    def name(self) -> str:
        """Return canonical pair name."""
        return f"{self._member_name(self._first_id)} / {self._member_name(self._second_id)}"

    @property
    def available(self) -> bool:
        """Return True while the group exists; direction flips do not cause unavailability."""
        return self._group is not None

    @property
    def native_value(self) -> float:
        """Return signed debt amount: positive = first owes second, negative = second owes first."""
        group = self._group
        if group is None:
            return 0.0
        for debt in group.debts:
            if debt.from_member == self._first_id and debt.to_member == self._second_id:
                return debt.amount   # first owes second → positive
            if debt.from_member == self._second_id and debt.to_member == self._first_id:
                return -debt.amount  # second owes first → negative
        return 0.0

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the group's display currency."""
        group = self._group
        return group.converted_to_currency if group else None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the group device."""
        return _group_device(self._group_id, self._group)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        value  = self.native_value
        first  = self._member_name(self._first_id)
        second = self._member_name(self._second_id)
        if value > 0:
            return {"owes": first, "to": second, "amount": value}
        if value < 0:
            return {"owes": second, "to": first, "amount": abs(value)}
        return {"settled": True}
