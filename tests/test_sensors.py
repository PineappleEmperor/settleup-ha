"""Unit tests for SettleUp sensor property methods."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from custom_components.settleup.api import SettleUpDebt, SettleUpGroup, SettleUpMember
from custom_components.settleup.sensor import (
    SettleUpDebtSensor,
    SettleUpGroupSensor,
    SettleUpMemberSensor,
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


def mock_coordinator(groups: list) -> MagicMock:
    coord = MagicMock()
    coord.data                = groups
    coord.last_update_success = True
    return coord

ALICE = "member_alice"
BOB   = "member_bob"


# ---------------------------------------------------------------------------
# SettleUpGroupSensor — timestamp state
# ---------------------------------------------------------------------------

def test_group_sensor_state_is_last_transaction_datetime() -> None:
    ts_ms  = 1700000000000
    group  = build_group(transactions=[
        {"dateTime": ts_ms, "purpose": "Lunch", "type": "expense",
         "currencyCode": "GBP", "whoPaid": [{"memberId": ALICE}],
         "items": [{"amount": "20.00", "forWhom": []}]},
    ])
    sensor   = SettleUpGroupSensor(mock_coordinator([group]), "group_test")
    expected = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
    assert sensor.native_value == expected


def test_group_sensor_state_none_when_no_transactions() -> None:
    sensor = SettleUpGroupSensor(mock_coordinator([build_group()]), "group_test")
    assert sensor.native_value is None


def test_group_sensor_state_none_when_no_data() -> None:
    coord  = mock_coordinator([])
    coord.data = None
    sensor = SettleUpGroupSensor(coord, "group_test")
    assert sensor.native_value is None


def test_group_sensor_available_with_live_data() -> None:
    sensor = SettleUpGroupSensor(mock_coordinator([build_group()]), "group_test")
    assert sensor.available is True


def test_group_sensor_unavailable_for_unknown_group() -> None:
    sensor = SettleUpGroupSensor(mock_coordinator([build_group()]), "other_group")
    assert sensor.available is False


# ---------------------------------------------------------------------------
# SettleUpGroupSensor — attributes
# ---------------------------------------------------------------------------

def test_group_sensor_currency_attribute() -> None:
    group  = build_group(currency="EUR")
    sensor = SettleUpGroupSensor(mock_coordinator([group]), "group_test")
    assert sensor.extra_state_attributes["currency"] == "EUR"


def test_group_sensor_debts_attribute_uses_names() -> None:
    group  = build_group(debts=[SettleUpDebt("group_test", BOB, ALICE, 15.0)])
    sensor = SettleUpGroupSensor(mock_coordinator([group]), "group_test")
    debts  = sensor.extra_state_attributes["debts"]
    assert len(debts)         == 1
    assert debts[0]["from"]   == "Bob"
    assert debts[0]["to"]     == "Alice"
    assert debts[0]["amount"] == 15.0


def test_group_sensor_members_attribute() -> None:
    sensor  = SettleUpGroupSensor(mock_coordinator([build_group()]), "group_test")
    members = sensor.extra_state_attributes["members"]
    names   = {m["name"] for m in members}
    assert names == {"Alice", "Bob"}


def test_group_sensor_main_member_attribute() -> None:
    group  = build_group()  # main_member_id = "member_alice"
    sensor = SettleUpGroupSensor(mock_coordinator([group]), "group_test")
    assert sensor.extra_state_attributes["main_member"] == "Alice"


def test_group_sensor_main_member_none_when_id_unmatched() -> None:
    group  = build_group()
    group.main_member_id = "unknown_id"
    sensor = SettleUpGroupSensor(mock_coordinator([group]), "group_test")
    assert sensor.extra_state_attributes["main_member"] is None


def test_group_sensor_recent_transactions_attribute() -> None:
    group  = build_group(transactions=[
        {"dateTime": 1700000000000, "purpose": "Coffee", "type": "expense",
         "currencyCode": "GBP", "whoPaid": [{"memberId": ALICE}],
         "items": [{"amount": "5.00", "forWhom": []}]},
    ])
    sensor = SettleUpGroupSensor(mock_coordinator([group]), "group_test")
    txns   = sensor.extra_state_attributes["recent_transactions"]
    assert len(txns)           == 1
    assert txns[0]["purpose"]  == "Coffee"
    assert txns[0]["amount"]   == 5.0
    assert txns[0]["currency"] == "GBP"


def test_group_sensor_paid_by_resolved_to_name() -> None:
    group  = build_group(transactions=[
        {"dateTime": 1700000000000, "purpose": "Dinner", "type": "expense",
         "currencyCode": "GBP", "whoPaid": [{"memberId": ALICE}],
         "items": [{"amount": "30.00", "forWhom": []}]},
    ])
    sensor  = SettleUpGroupSensor(mock_coordinator([group]), "group_test")
    paid_by = sensor.extra_state_attributes["recent_transactions"][0]["paid_by"]
    assert paid_by == ["Alice"]


def test_group_sensor_empty_attributes_when_no_data() -> None:
    coord  = mock_coordinator([])
    coord.data = None
    sensor = SettleUpGroupSensor(coord, "group_test")
    assert sensor.extra_state_attributes == {}


# ---------------------------------------------------------------------------
# SettleUpMemberSensor
# ---------------------------------------------------------------------------

def test_member_sensor_balance_owed() -> None:
    group  = build_group(debts=[SettleUpDebt("group_test", BOB, ALICE, 30.0)])
    sensor = SettleUpMemberSensor(mock_coordinator([group]), "group_test", ALICE)
    assert sensor.native_value == 30.0


def test_member_sensor_balance_owes() -> None:
    group  = build_group(debts=[SettleUpDebt("group_test", ALICE, BOB, 12.0)])
    sensor = SettleUpMemberSensor(mock_coordinator([group]), "group_test", ALICE)
    assert sensor.native_value == -12.0


def test_member_sensor_name_from_live_data() -> None:
    group  = build_group()
    sensor = SettleUpMemberSensor(mock_coordinator([group]), "group_test", ALICE)
    assert sensor.name == "Alice"


def test_member_sensor_name_falls_back_to_member_id() -> None:
    coord  = mock_coordinator([])
    coord.data = None
    sensor = SettleUpMemberSensor(coord, "group_test", ALICE)
    assert sensor.name == ALICE


def test_member_sensor_owes_attribute() -> None:
    group  = build_group(debts=[SettleUpDebt("group_test", BOB, ALICE, 8.0)])
    sensor = SettleUpMemberSensor(mock_coordinator([group]), "group_test", BOB)
    owes   = sensor.extra_state_attributes["owes"]
    assert len(owes)         == 1
    assert owes[0]["to"]     == "Alice"
    assert owes[0]["amount"] == 8.0


def test_member_sensor_owed_by_attribute() -> None:
    group   = build_group(debts=[SettleUpDebt("group_test", BOB, ALICE, 8.0)])
    sensor  = SettleUpMemberSensor(mock_coordinator([group]), "group_test", ALICE)
    owed_by = sensor.extra_state_attributes["owed_by"]
    assert len(owed_by)          == 1
    assert owed_by[0]["from"]    == "Bob"
    assert owed_by[0]["amount"]  == 8.0


def test_member_sensor_currency() -> None:
    group  = build_group(currency="USD")
    sensor = SettleUpMemberSensor(mock_coordinator([group]), "group_test", ALICE)
    assert sensor.native_unit_of_measurement == "USD"


def test_member_sensor_enabled_by_default_for_active_member() -> None:
    sensor = SettleUpMemberSensor(mock_coordinator([build_group()]), "group_test", ALICE)
    assert sensor.entity_registry_enabled_default is True


def test_member_sensor_disabled_by_default_for_inactive_member() -> None:
    sensor = SettleUpMemberSensor(mock_coordinator([build_group()]), "group_test", ALICE, active=False)
    assert sensor.entity_registry_enabled_default is False


def test_member_sensor_unavailable_when_member_not_in_group() -> None:
    group  = build_group()
    coord  = mock_coordinator([group])
    coord.last_update_success = True
    sensor = SettleUpMemberSensor(coord, "group_test", "nonexistent_member")
    assert sensor.available is False


# ---------------------------------------------------------------------------
# SettleUpDebtSensor — canonical pairs (Alice before Bob alphabetically)
# Positive = first (Alice) owes second (Bob); negative = second owes first.
# ---------------------------------------------------------------------------

def test_debt_sensor_positive_when_first_owes_second() -> None:
    group  = build_group(debts=[SettleUpDebt("group_test", ALICE, BOB, 42.0)])
    sensor = SettleUpDebtSensor(mock_coordinator([group]), "group_test", ALICE, BOB)
    assert sensor.native_value == 42.0


def test_debt_sensor_negative_when_second_owes_first() -> None:
    group  = build_group(debts=[SettleUpDebt("group_test", BOB, ALICE, 42.0)])
    sensor = SettleUpDebtSensor(mock_coordinator([group]), "group_test", ALICE, BOB)
    assert sensor.native_value == -42.0


def test_debt_sensor_zero_when_settled() -> None:
    group  = build_group(debts=[])
    sensor = SettleUpDebtSensor(mock_coordinator([group]), "group_test", ALICE, BOB)
    assert sensor.native_value == 0.0


def test_debt_sensor_name_uses_member_names() -> None:
    group  = build_group(debts=[SettleUpDebt("group_test", BOB, ALICE, 10.0)])
    sensor = SettleUpDebtSensor(mock_coordinator([group]), "group_test", ALICE, BOB)
    assert sensor.name == "Alice / Bob"


def test_debt_sensor_currency() -> None:
    group  = build_group(currency="EUR", debts=[SettleUpDebt("group_test", BOB, ALICE, 5.0)])
    sensor = SettleUpDebtSensor(mock_coordinator([group]), "group_test", ALICE, BOB)
    assert sensor.native_unit_of_measurement == "EUR"


def test_debt_sensor_available_when_group_exists() -> None:
    group  = build_group(debts=[])
    sensor = SettleUpDebtSensor(mock_coordinator([group]), "group_test", ALICE, BOB)
    assert sensor.available is True


def test_debt_sensor_unavailable_when_no_coordinator_data() -> None:
    coord  = mock_coordinator([])
    coord.data = None
    sensor = SettleUpDebtSensor(coord, "group_test", ALICE, BOB)
    assert sensor.available is False


def test_debt_sensor_attributes_when_first_owes_second() -> None:
    group  = build_group(debts=[SettleUpDebt("group_test", ALICE, BOB, 8.0)])
    sensor = SettleUpDebtSensor(mock_coordinator([group]), "group_test", ALICE, BOB)
    attrs  = sensor.extra_state_attributes
    assert attrs["owes"]   == "Alice"
    assert attrs["to"]     == "Bob"
    assert attrs["amount"] == 8.0


def test_debt_sensor_attributes_when_second_owes_first() -> None:
    group  = build_group(debts=[SettleUpDebt("group_test", BOB, ALICE, 8.0)])
    sensor = SettleUpDebtSensor(mock_coordinator([group]), "group_test", ALICE, BOB)
    attrs  = sensor.extra_state_attributes
    assert attrs["owes"]   == "Bob"
    assert attrs["to"]     == "Alice"
    assert attrs["amount"] == 8.0


def test_debt_sensor_attributes_when_settled() -> None:
    group  = build_group(debts=[])
    sensor = SettleUpDebtSensor(mock_coordinator([group]), "group_test", ALICE, BOB)
    assert sensor.extra_state_attributes == {"settled": True}


def test_debt_sensor_unique_id() -> None:
    sensor = SettleUpDebtSensor(mock_coordinator([build_group()]), "group_test", ALICE, BOB)
    assert sensor.unique_id == f"settleup_group_test_{ALICE}_{BOB}_pair"


def test_debt_sensor_disabled_by_default() -> None:
    sensor = SettleUpDebtSensor(mock_coordinator([build_group()]), "group_test", ALICE, BOB)
    assert sensor.entity_registry_enabled_default is False
