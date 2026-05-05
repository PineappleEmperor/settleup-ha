"""Base entity class for the SettleUp integration."""
from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SettleUpCoordinator


class SettleUpEntity(CoordinatorEntity[SettleUpCoordinator]):
    """Base class providing coordinator typing for all SettleUp entities."""

    _attr_has_entity_name = True
