"""Tests for the SettleUp DataUpdateCoordinator."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.settleup.api import (
    SettleUpAuthError,
    SettleUpGroup,
    SettleUpMember,
)
from custom_components.settleup.coordinator import OPT_KNOWN_GROUPS, SettleUpCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

MOCK_USER_GROUPS = {
    "group_abc": {"memberId": "member_alice", "order": 0},
}


def build_group(
    group_id    : str             = "group_test",
    main_member : str             = "member_alice",
    currency    : str             = "GBP",
    debts       : list | None     = None,
    members     : list | None     = None,
    transactions: list | None     = None,
) -> SettleUpGroup:
    if members is None:
        members = [
            SettleUpMember(group_id, "member_alice", True, "1", "Alice", 0.0),
            SettleUpMember(group_id, "member_bob",   True, "1", "Bob",   0.0),
        ]
    debts = debts or []
    for m in members:
        m.assign_debts(debts)
    return SettleUpGroup(
        group_id              = group_id,
        main_member_id        = main_member,
        name                  = "Test Group",
        converted_to_currency = currency,
        invite_link           = None,
        invite_link_active    = False,
        invite_link_hash      = None,
        last_changed          = 1700000000,
        minimize_debts        = False,
        owner_color           = "#4CAF50",
        members               = members,
        debts                 = debts,
        recent_transactions   = transactions or [],
    )

_PATCH_API   = "custom_components.settleup.coordinator.SettleUpAPI"
_PATCH_GROUP = "custom_components.settleup.coordinator.SettleUpGroup"


def _make_coordinator(hass: HomeAssistant, entry: MockConfigEntry) -> SettleUpCoordinator:
    with patch(_PATCH_API):
        return SettleUpCoordinator(hass, entry)


# ---------------------------------------------------------------------------
# Successful update
# ---------------------------------------------------------------------------

async def test_update_returns_groups(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    mock_config_entry.add_to_hass(hass)
    coord = _make_coordinator(hass, mock_config_entry)

    group = build_group()
    coord.api.get_user_groups = AsyncMock(return_value=MOCK_USER_GROUPS)

    with patch(_PATCH_GROUP + ".from_api", new=AsyncMock(return_value=group)):
        await coord.async_refresh()

    assert coord.last_update_success is True
    assert len(coord.data) == 1
    assert coord.data[0].name == "Test Group"


async def test_update_persists_known_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """After a successful update, group/member metadata is cached in entry.options."""
    mock_config_entry.add_to_hass(hass)
    coord = _make_coordinator(hass, mock_config_entry)

    group = build_group()
    coord.api.get_user_groups = AsyncMock(return_value=MOCK_USER_GROUPS)

    with patch(_PATCH_GROUP + ".from_api", new=AsyncMock(return_value=group)):
        await coord.async_refresh()

    known = mock_config_entry.options.get(OPT_KNOWN_GROUPS, {})
    assert "group_test" in known
    assert known["group_test"]["name"]                 == "Test Group"
    assert known["group_test"]["currency"]             == "GBP"
    assert "member_alice" in known["group_test"]["members"]
    assert "member_bob"   in known["group_test"]["members"]


async def test_persist_skipped_when_unchanged(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """_persist_known_entities should not call async_update_entry if nothing changed."""
    mock_config_entry.add_to_hass(hass)
    coord = _make_coordinator(hass, mock_config_entry)

    group = build_group()
    coord.api.get_user_groups = AsyncMock(return_value=MOCK_USER_GROUPS)

    with patch(_PATCH_GROUP + ".from_api", new=AsyncMock(return_value=group)):
        await coord.async_refresh()  # first refresh — writes options
        first_options = dict(mock_config_entry.options)

        await coord.async_refresh()  # second refresh — same data, no write needed
        second_options = dict(mock_config_entry.options)

    assert first_options == second_options


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

async def test_runtime_error_raises_update_failed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    mock_config_entry.add_to_hass(hass)
    coord = _make_coordinator(hass, mock_config_entry)
    coord.api.get_user_groups = AsyncMock(side_effect=RuntimeError("auth failed"))

    await coord.async_refresh()

    assert coord.last_update_success is False


async def test_unexpected_exception_raises_update_failed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    mock_config_entry.add_to_hass(hass)
    coord = _make_coordinator(hass, mock_config_entry)
    coord.api.get_user_groups = AsyncMock(side_effect=ConnectionError("network down"))

    await coord.async_refresh()

    assert coord.last_update_success is False


async def test_auth_error_raises_config_entry_auth_failed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """SettleUpAuthError must surface as ConfigEntryAuthFailed so HA starts reauth.

    Asserting our contract (the raised exception) rather than HA's internal
    async_start_reauth call keeps the test stable across HA versions.
    """
    mock_config_entry.add_to_hass(hass)
    coord = _make_coordinator(hass, mock_config_entry)
    coord.api.get_user_groups = AsyncMock(side_effect=SettleUpAuthError("token revoked"))

    with pytest.raises(ConfigEntryAuthFailed):
        await coord._async_update_data()

    await coord.async_refresh()
    assert coord.last_update_success is False


async def test_empty_groups_returns_empty_list(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    mock_config_entry.add_to_hass(hass)
    coord = _make_coordinator(hass, mock_config_entry)
    coord.api.get_user_groups = AsyncMock(return_value={})

    await coord.async_refresh()

    assert coord.last_update_success is True
    assert coord.data == []
