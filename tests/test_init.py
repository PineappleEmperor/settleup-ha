"""Tests for SettleUp setup and unload of a config entry."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.settleup import async_remove_config_entry_device
from custom_components.settleup.api import SettleUpGroup, SettleUpMember
from custom_components.settleup.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

SERVICE_ADD_TRANSACTION = "add_transaction"
SERVICE_SETTLE_DEBT = "settle_debt"

MOCK_USER_GROUPS = {"group_abc": {"memberId": "member_alice", "order": 0}}


def build_group(
    group_id: str = "group_test",
    name: str = "Test Group",
    members: list[tuple[str, str]] | None = None,
) -> SettleUpGroup:
    """Return a minimal group for setup tests; members are (member_id, display_name)."""
    members = members or [("member_alice", "Alice"), ("member_bob", "Bob")]
    member_objs = [
        SettleUpMember(group_id, mid, True, "1", mname, 0.0) for mid, mname in members
    ]
    return SettleUpGroup(
        group_id              = group_id,
        main_member_id        = member_objs[0].member_id,
        name                  = name,
        converted_to_currency = "GBP",
        invite_link           = None,
        invite_link_active    = False,
        invite_link_hash      = None,
        last_changed          = 1700000000,
        minimize_debts        = False,
        owner_color           = "#4CAF50",
        members               = member_objs,
        debts                 = [],
        recent_transactions   = [],
    )

_PATCH_API = "custom_components.settleup.coordinator.SettleUpAPI"
_PATCH_FROM_API = "custom_components.settleup.coordinator.SettleUpGroup.from_api"


@pytest.fixture
def mock_api() -> MagicMock:
    """Return a mock SettleUpAPI whose group fetch succeeds."""
    api = MagicMock()
    api.get_user_groups = AsyncMock(return_value=MOCK_USER_GROUPS)
    return api


async def _setup(hass: HomeAssistant, entry: MockConfigEntry, api: MagicMock) -> bool:
    """Run a real config-entry setup with only the API transport mocked."""
    entry.add_to_hass(hass)
    with (
        patch(_PATCH_API, return_value=api),
        patch(_PATCH_FROM_API, AsyncMock(return_value=build_group())),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return result


async def test_setup_entry_loaded(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """A real setup reaches LOADED, populates runtime_data and creates entities."""
    assert await _setup(hass, mock_config_entry, mock_api)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None
    mock_api.get_user_groups.assert_awaited()

    assert hass.states.async_all("sensor")


async def test_setup_registers_services(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Services are registered during component setup."""
    await _setup(hass, mock_config_entry, mock_api)

    assert hass.services.has_service(DOMAIN, SERVICE_ADD_TRANSACTION)
    assert hass.services.has_service(DOMAIN, SERVICE_SETTLE_DEBT)


async def test_setup_retries_when_first_refresh_fails(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """A failing first refresh leaves the entry in SETUP_RETRY, not LOADED."""
    mock_api.get_user_groups = AsyncMock(side_effect=RuntimeError("Firebase down"))
    mock_config_entry.add_to_hass(hass)
    with patch(_PATCH_API, return_value=mock_api):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Unloading a loaded entry succeeds and reaches NOT_LOADED."""
    await _setup(hass, mock_config_entry, mock_api)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_dynamic_devices_adds_entities_for_new_group(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """A group that appears on a later refresh spawns new entities (dynamic-devices)."""
    await _setup(hass, mock_config_entry, mock_api)
    before = len(hass.states.async_all("sensor"))

    coordinator = mock_config_entry.runtime_data
    coordinator.data = [
        build_group(),
        build_group("group_two", "Second", [("member_carol", "Carol"), ("member_dave", "Dave")]),
    ]
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) > before
    assert hass.states.get("sensor.settle_up_second_last_transaction") is not None


async def test_remove_device_blocked_while_group_live(hass: HomeAssistant) -> None:
    """A device whose group still exists upstream cannot be deleted."""
    entry = SimpleNamespace(runtime_data=SimpleNamespace(data=[build_group()]))
    device = SimpleNamespace(identifiers={(DOMAIN, "group_test")})
    assert await async_remove_config_entry_device(hass, entry, device) is False


async def test_remove_device_allowed_when_group_stale(hass: HomeAssistant) -> None:
    """A device whose group no longer exists upstream can be deleted."""
    entry = SimpleNamespace(runtime_data=SimpleNamespace(data=[build_group()]))
    device = SimpleNamespace(identifiers={(DOMAIN, "gone_group")})
    assert await async_remove_config_entry_device(hass, entry, device) is True
