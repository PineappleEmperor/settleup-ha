"""Tests for SettleUp service handlers and helper functions."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.settleup.api import SettleUpGroup, SettleUpMember
from custom_components.settleup.const import DOMAIN
from custom_components.settleup.services import (
    SERVICE_ADD_TRANSACTION,
    SERVICE_SETTLE_DEBT,
    _group_currency,
    _group_id_from_device,
    _member_id_from_entity,
    _resolve,
    _resolve_float_list,
    async_setup_services,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    template as template_helper,
)


def build_group(
    group_id    : str         = "group_test",
    main_member : str         = "member_alice",
    currency    : str         = "GBP",
    debts       : list | None = None,
    members     : list | None = None,
    transactions: list | None = None,
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

GROUP_ID = "group_test"
ALICE_ID = "member_alice"
BOB_ID   = "member_bob"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def setup(hass: HomeAssistant, mock_config_entry):
    """Coordinator, services, device, and member entities — all in one."""
    coord = MagicMock()
    coord.data = [build_group()]
    coord.api.add_transaction = AsyncMock(return_value="txn_key_123")

    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = coord
    async_setup_services(hass)

    device = dr.async_get(hass).async_get_or_create(
        config_entry_id = mock_config_entry.entry_id,
        identifiers     = {(DOMAIN, GROUP_ID)},
        name            = "SettleUp Test Group",
    )

    entity_reg = er.async_get(hass)
    alice = entity_reg.async_get_or_create(
        "sensor", DOMAIN,
        f"{DOMAIN}_{GROUP_ID}_{ALICE_ID}_balance",
        config_entry = mock_config_entry,
    )
    bob = entity_reg.async_get_or_create(
        "sensor", DOMAIN,
        f"{DOMAIN}_{GROUP_ID}_{BOB_ID}_balance",
        config_entry = mock_config_entry,
    )

    return {
        "coordinator"    : coord,
        "device_id"      : device.id,
        "alice_entity_id": alice.entity_id,
        "bob_entity_id"  : bob.entity_id,
    }


# ---------------------------------------------------------------------------
# _group_currency
# ---------------------------------------------------------------------------

def test_group_currency_returns_group_currency() -> None:
    coord = MagicMock()
    coord.data = [build_group(currency="EUR")]
    assert _group_currency(coord, GROUP_ID) == "EUR"


def test_group_currency_falls_back_when_no_data() -> None:
    coord = MagicMock()
    coord.data = None
    assert _group_currency(coord, GROUP_ID) == "GBP"


def test_group_currency_falls_back_when_group_not_found() -> None:
    coord = MagicMock()
    coord.data = [build_group(currency="EUR")]
    assert _group_currency(coord, "other_group") == "GBP"


# ---------------------------------------------------------------------------
# _resolve
# ---------------------------------------------------------------------------

async def test_resolve_returns_plain_values(hass: HomeAssistant) -> None:
    assert _resolve(hass, 42.0)    == 42.0
    assert _resolve(hass, "hello") == "hello"
    assert _resolve(hass, [1, 2])  == [1, 2]


async def test_resolve_renders_template(hass: HomeAssistant) -> None:
    tmpl = template_helper.Template("{{ 1 + 1 }}", hass)
    assert _resolve(hass, tmpl) == 2


# ---------------------------------------------------------------------------
# _resolve_float_list
# ---------------------------------------------------------------------------

async def test_resolve_float_list_plain(hass: HomeAssistant) -> None:
    assert _resolve_float_list(hass, [2.0, 1.0]) == [2.0, 1.0]


async def test_resolve_float_list_template(hass: HomeAssistant) -> None:
    tmpl = template_helper.Template("{{ [2, 1] }}", hass)
    assert _resolve_float_list(hass, tmpl) == [2.0, 1.0]


async def test_resolve_float_list_raises_on_non_list(hass: HomeAssistant) -> None:
    with pytest.raises(HomeAssistantError, match="expected_number_list"):
        _resolve_float_list(hass, "not a list")


# ---------------------------------------------------------------------------
# _group_id_from_device
# ---------------------------------------------------------------------------

async def test_group_id_from_device_resolves(hass: HomeAssistant, setup) -> None:
    assert _group_id_from_device(hass, setup["device_id"]) == GROUP_ID


async def test_group_id_from_device_raises_when_not_found(hass: HomeAssistant, setup) -> None:
    with pytest.raises(HomeAssistantError, match="device_not_found"):
        _group_id_from_device(hass, "bad_device_id")


async def test_group_id_from_device_raises_for_non_settleup_device(
    hass: HomeAssistant, setup, mock_config_entry
) -> None:
    other = dr.async_get(hass).async_get_or_create(
        config_entry_id = mock_config_entry.entry_id,
        identifiers     = {("other_domain", "some_id")},
        name            = "Other Device",
    )
    with pytest.raises(HomeAssistantError, match="not_a_group_device"):
        _group_id_from_device(hass, other.id)


# ---------------------------------------------------------------------------
# _member_id_from_entity
# ---------------------------------------------------------------------------

async def test_member_id_from_entity_resolves_alice(hass: HomeAssistant, setup) -> None:
    member_id = _member_id_from_entity(hass, setup["alice_entity_id"], GROUP_ID)
    assert member_id == ALICE_ID


async def test_member_id_from_entity_resolves_bob(hass: HomeAssistant, setup) -> None:
    member_id = _member_id_from_entity(hass, setup["bob_entity_id"], GROUP_ID)
    assert member_id == BOB_ID


async def test_member_id_from_entity_raises_when_unknown(hass: HomeAssistant, setup) -> None:
    with pytest.raises(HomeAssistantError, match="unknown_entity"):
        _member_id_from_entity(hass, "sensor.nonexistent", GROUP_ID)


async def test_member_id_from_entity_raises_for_wrong_group(hass: HomeAssistant, setup) -> None:
    with pytest.raises(HomeAssistantError, match="not_a_member_sensor"):
        _member_id_from_entity(hass, setup["alice_entity_id"], "other_group")


# ---------------------------------------------------------------------------
# handle_add_transaction — split modes
# ---------------------------------------------------------------------------

async def test_add_transaction_equal_split(hass: HomeAssistant, setup) -> None:
    await hass.services.async_call(
        DOMAIN, SERVICE_ADD_TRANSACTION,
        {
            "group"      : setup["device_id"],
            "purpose"    : "Dinner",
            "amount"     : 30.0,
            "paid_by"    : setup["alice_entity_id"],
            "for_members": [setup["alice_entity_id"], setup["bob_entity_id"]],
        },
        blocking=True,
    )
    coord = setup["coordinator"]
    coord.api.add_transaction.assert_awaited_once()
    group_id, txn = coord.api.add_transaction.call_args.args
    assert group_id                          == GROUP_ID
    assert txn["type"]                       == "expense"
    assert txn["purpose"]                    == "Dinner"
    assert txn["whoPaid"][0]["memberId"]     == ALICE_ID
    assert len(txn["items"])                 == 1
    assert len(txn["items"][0]["forWhom"])   == 2


async def test_add_transaction_weighted_split(hass: HomeAssistant, setup) -> None:
    await hass.services.async_call(
        DOMAIN, SERVICE_ADD_TRANSACTION,
        {
            "group"      : setup["device_id"],
            "purpose"    : "Dinner",
            "amount"     : 30.0,
            "paid_by"    : setup["alice_entity_id"],
            "for_members": [setup["alice_entity_id"], setup["bob_entity_id"]],
            "weights"    : [2.0, 1.0],
        },
        blocking=True,
    )
    _, txn    = setup["coordinator"].api.add_transaction.call_args.args
    for_whom  = txn["items"][0]["forWhom"]
    assert len(for_whom)          == 2
    assert for_whom[0]["weight"]  == "2.0"
    assert for_whom[1]["weight"]  == "1.0"


async def test_add_transaction_exact_amounts(hass: HomeAssistant, setup) -> None:
    await hass.services.async_call(
        DOMAIN, SERVICE_ADD_TRANSACTION,
        {
            "group"          : setup["device_id"],
            "purpose"        : "Dinner",
            "amount"         : 30.0,
            "paid_by"        : setup["alice_entity_id"],
            "for_members"    : [setup["alice_entity_id"], setup["bob_entity_id"]],
            "member_amounts" : [20.0, 10.0],
        },
        blocking=True,
    )
    _, txn = setup["coordinator"].api.add_transaction.call_args.args
    assert len(txn["items"])          == 2
    assert txn["items"][0]["amount"]  == "20.0"
    assert txn["items"][1]["amount"]  == "10.0"
    assert txn["items"][0]["forWhom"][0]["memberId"] == ALICE_ID
    assert txn["items"][1]["forWhom"][0]["memberId"] == BOB_ID


async def test_add_transaction_single_member_equal_weight(hass: HomeAssistant, setup) -> None:
    await hass.services.async_call(
        DOMAIN, SERVICE_ADD_TRANSACTION,
        {
            "group"      : setup["device_id"],
            "purpose"    : "Solo",
            "amount"     : 10.0,
            "paid_by"    : setup["alice_entity_id"],
            "for_members": [setup["alice_entity_id"]],
        },
        blocking=True,
    )
    _, txn   = setup["coordinator"].api.add_transaction.call_args.args
    for_whom = txn["items"][0]["forWhom"]
    assert for_whom[0]["weight"] == "1"


# ---------------------------------------------------------------------------
# handle_add_transaction — currency
# ---------------------------------------------------------------------------

async def test_add_transaction_uses_group_currency_by_default(hass: HomeAssistant, setup) -> None:
    await hass.services.async_call(
        DOMAIN, SERVICE_ADD_TRANSACTION,
        {
            "group"      : setup["device_id"],
            "purpose"    : "Coffee",
            "amount"     : 5.0,
            "paid_by"    : setup["alice_entity_id"],
            "for_members": [setup["alice_entity_id"]],
        },
        blocking=True,
    )
    _, txn = setup["coordinator"].api.add_transaction.call_args.args
    assert txn["currencyCode"] == "GBP"


async def test_add_transaction_explicit_currency_overrides(hass: HomeAssistant, setup) -> None:
    await hass.services.async_call(
        DOMAIN, SERVICE_ADD_TRANSACTION,
        {
            "group"         : setup["device_id"],
            "purpose"       : "Coffee",
            "amount"        : 5.0,
            "paid_by"       : setup["alice_entity_id"],
            "for_members"   : [setup["alice_entity_id"]],
            "currency_code" : "EUR",
        },
        blocking=True,
    )
    _, txn = setup["coordinator"].api.add_transaction.call_args.args
    assert txn["currencyCode"] == "EUR"


# ---------------------------------------------------------------------------
# handle_add_transaction — error cases
# ---------------------------------------------------------------------------

async def test_add_transaction_both_weights_and_amounts_raises(hass: HomeAssistant, setup) -> None:
    with pytest.raises(HomeAssistantError, match="weights_and_amounts"):
        await hass.services.async_call(
            DOMAIN, SERVICE_ADD_TRANSACTION,
            {
                "group"          : setup["device_id"],
                "purpose"        : "Dinner",
                "amount"         : 30.0,
                "paid_by"        : setup["alice_entity_id"],
                "for_members"    : [setup["alice_entity_id"], setup["bob_entity_id"]],
                "weights"        : [2.0, 1.0],
                "member_amounts" : [20.0, 10.0],
            },
            blocking=True,
        )


async def test_add_transaction_weights_length_mismatch_raises(hass: HomeAssistant, setup) -> None:
    with pytest.raises(HomeAssistantError, match="length_mismatch"):
        await hass.services.async_call(
            DOMAIN, SERVICE_ADD_TRANSACTION,
            {
                "group"      : setup["device_id"],
                "purpose"    : "Dinner",
                "amount"     : 30.0,
                "paid_by"    : setup["alice_entity_id"],
                "for_members": [setup["alice_entity_id"], setup["bob_entity_id"]],
                "weights"    : [2.0],
            },
            blocking=True,
        )


async def test_add_transaction_member_amounts_length_mismatch_raises(hass: HomeAssistant, setup) -> None:
    with pytest.raises(HomeAssistantError, match="length_mismatch"):
        await hass.services.async_call(
            DOMAIN, SERVICE_ADD_TRANSACTION,
            {
                "group"          : setup["device_id"],
                "purpose"        : "Dinner",
                "amount"         : 30.0,
                "paid_by"        : setup["alice_entity_id"],
                "for_members"    : [setup["alice_entity_id"], setup["bob_entity_id"]],
                "member_amounts" : [20.0],
            },
            blocking=True,
        )


async def test_add_transaction_api_error_raises(hass: HomeAssistant, setup) -> None:
    setup["coordinator"].api.add_transaction.side_effect = RuntimeError("Firebase error")
    with pytest.raises(HomeAssistantError, match="api_error"):
        await hass.services.async_call(
            DOMAIN, SERVICE_ADD_TRANSACTION,
            {
                "group"      : setup["device_id"],
                "purpose"    : "Dinner",
                "amount"     : 30.0,
                "paid_by"    : setup["alice_entity_id"],
                "for_members": [setup["alice_entity_id"]],
            },
            blocking=True,
        )


# ---------------------------------------------------------------------------
# handle_settle_debt
# ---------------------------------------------------------------------------

async def test_settle_debt_posts_transfer(hass: HomeAssistant, setup) -> None:
    await hass.services.async_call(
        DOMAIN, SERVICE_SETTLE_DEBT,
        {
            "group"       : setup["device_id"],
            "from_member" : setup["bob_entity_id"],
            "to_member"   : setup["alice_entity_id"],
            "amount"      : 15.0,
        },
        blocking=True,
    )
    coord = setup["coordinator"]
    coord.api.add_transaction.assert_awaited_once()
    group_id, txn = coord.api.add_transaction.call_args.args
    assert group_id                                       == GROUP_ID
    assert txn["type"]                                    == "transfer"
    assert txn["whoPaid"][0]["memberId"]                  == BOB_ID
    assert txn["items"][0]["forWhom"][0]["memberId"]      == ALICE_ID
    assert txn["items"][0]["amount"]                      == "15.0"


async def test_settle_debt_uses_group_currency_by_default(hass: HomeAssistant, setup) -> None:
    await hass.services.async_call(
        DOMAIN, SERVICE_SETTLE_DEBT,
        {
            "group"       : setup["device_id"],
            "from_member" : setup["bob_entity_id"],
            "to_member"   : setup["alice_entity_id"],
            "amount"      : 15.0,
        },
        blocking=True,
    )
    _, txn = setup["coordinator"].api.add_transaction.call_args.args
    assert txn["currencyCode"] == "GBP"


async def test_settle_debt_explicit_currency(hass: HomeAssistant, setup) -> None:
    await hass.services.async_call(
        DOMAIN, SERVICE_SETTLE_DEBT,
        {
            "group"         : setup["device_id"],
            "from_member"   : setup["bob_entity_id"],
            "to_member"     : setup["alice_entity_id"],
            "amount"        : 15.0,
            "currency_code" : "USD",
        },
        blocking=True,
    )
    _, txn = setup["coordinator"].api.add_transaction.call_args.args
    assert txn["currencyCode"] == "USD"


async def test_settle_debt_api_error_raises(hass: HomeAssistant, setup) -> None:
    setup["coordinator"].api.add_transaction.side_effect = RuntimeError("Firebase error")
    with pytest.raises(HomeAssistantError, match="api_error"):
        await hass.services.async_call(
            DOMAIN, SERVICE_SETTLE_DEBT,
            {
                "group"       : setup["device_id"],
                "from_member" : setup["bob_entity_id"],
                "to_member"   : setup["alice_entity_id"],
                "amount"      : 15.0,
            },
            blocking=True,
        )
