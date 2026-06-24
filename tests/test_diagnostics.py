"""Tests for SettleUp config-entry diagnostics."""
from __future__ import annotations

from types import SimpleNamespace

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.settleup.api import SettleUpGroup, SettleUpMember
from custom_components.settleup.const import CONF_API_KEY, CONF_EMAIL, DOMAIN
from custom_components.settleup.diagnostics import async_get_config_entry_diagnostics
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

REDACTED = "**REDACTED**"


def _group() -> SettleUpGroup:
    members = [
        SettleUpMember("g1", "m_alice", True, "1", "Alice", 0.0),
        SettleUpMember("g1", "m_bob", True, "1", "Bob", 0.0),
    ]
    return SettleUpGroup(
        group_id              = "g1",
        main_member_id        = "m_alice",
        name                  = "Holiday",
        converted_to_currency = "GBP",
        invite_link           = None,
        invite_link_active    = False,
        invite_link_hash      = None,
        last_changed          = 1700000000,
        minimize_debts        = False,
        owner_color           = "#4CAF50",
        members               = members,
        debts                 = [],
        recent_transactions   = [],
    )


def _entry() -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "secret_key",
            CONF_EMAIL: "user@example.com",
            CONF_PASSWORD: "hunter2",
        },
        unique_id="fake_user_id",
    )
    entry.runtime_data = SimpleNamespace(data=[_group()], last_update_success=True)
    return entry


async def test_diagnostics_redacts_credentials(hass: HomeAssistant) -> None:
    diag = await async_get_config_entry_diagnostics(hass, _entry())
    entry_data = diag["entry"]["data"]
    assert entry_data[CONF_API_KEY] == REDACTED
    assert entry_data[CONF_EMAIL] == REDACTED
    assert entry_data[CONF_PASSWORD] == REDACTED


async def test_diagnostics_reports_group_shape(hass: HomeAssistant) -> None:
    diag = await async_get_config_entry_diagnostics(hass, _entry())
    assert diag["last_update_success"] is True
    assert diag["group_count"] == 1
    group = diag["groups"][0]
    assert group["group_id"] == "g1"
    assert group["name"] == "Holiday"
    assert group["currency"] == "GBP"
    assert group["member_count"] == 2
    assert group["debt_count"] == 0
