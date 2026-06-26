"""Attribute-level quality-scale checks: has-entity-name, device-class, entity-category, parallel-updates.

hassfest never instantiates the entities, so these class attributes are otherwise
only claimed by code presence. Assert them so the rules are shown, not assumed.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.settleup import sensor as sensor_module
from custom_components.settleup.api import SettleUpGroup, SettleUpMember
from custom_components.settleup.sensor import (
    SettleUpDebtSensor,
    SettleUpGroupSensor,
    SettleUpMemberSensor,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory

GROUP_ID = "group_test"
ALICE    = "member_alice"
BOB      = "member_bob"


def _coordinator() -> MagicMock:
    members = [
        SettleUpMember(GROUP_ID, ALICE, True, "1", "Alice", 0.0),
        SettleUpMember(GROUP_ID, BOB,   True, "1", "Bob",   0.0),
    ]
    group = SettleUpGroup(
        group_id              = GROUP_ID,
        main_member_id        = ALICE,
        name                  = "Test Group",
        converted_to_currency = "GBP",
        invite_link           = None,
        invite_link_active    = False,
        invite_link_hash      = None,
        last_changed          = 1700000000,
        minimize_debts        = False,
        owner_color           = "#4CAF50",
        members               = members,
        debts                 = [],
    )
    coord = MagicMock()
    coord.data                = [group]
    coord.last_update_success = True
    return coord


def _group_sensor() -> SettleUpGroupSensor:
    return SettleUpGroupSensor(_coordinator(), GROUP_ID)


def _member_sensor() -> SettleUpMemberSensor:
    return SettleUpMemberSensor(_coordinator(), GROUP_ID, ALICE)


def _debt_sensor() -> SettleUpDebtSensor:
    return SettleUpDebtSensor(_coordinator(), GROUP_ID, ALICE, BOB)


# parallel-updates (Silver) --------------------------------------------------

def test_parallel_updates_is_zero() -> None:
    assert sensor_module.PARALLEL_UPDATES == 0


# has-entity-name (Bronze) ---------------------------------------------------

def test_all_sensors_have_entity_name() -> None:
    assert _group_sensor().has_entity_name is True
    assert _member_sensor().has_entity_name is True
    assert _debt_sensor().has_entity_name is True


# entity-translations (Gold) — translation_key drives the entity name --------

def test_all_sensors_set_translation_key() -> None:
    assert _group_sensor().translation_key  == "last_transaction"
    assert _member_sensor().translation_key == "member_balance"
    assert _debt_sensor().translation_key   == "pair_debt"


# entity-device-class (Gold) -------------------------------------------------

def test_sensor_device_classes() -> None:
    assert _group_sensor().device_class  == SensorDeviceClass.TIMESTAMP
    assert _member_sensor().device_class == SensorDeviceClass.MONETARY
    assert _debt_sensor().device_class   == SensorDeviceClass.MONETARY


# state-class — monetary balances need TOTAL for long-term statistics --------
# HA permits only {TOTAL} for the MONETARY device class (DEVICE_CLASS_STATE_CLASSES);
# dropping it breaks statistics, and MEASUREMENT is rejected as "impossible" for monetary.

def test_monetary_sensors_have_total_state_class() -> None:
    assert _member_sensor().state_class == SensorStateClass.TOTAL
    assert _debt_sensor().state_class   == SensorStateClass.TOTAL


def test_timestamp_sensor_has_no_state_class() -> None:
    assert _group_sensor().state_class is None


# entity-category (Gold) — the pair-debt sensor is diagnostic ----------------

def test_debt_sensor_is_diagnostic() -> None:
    assert _debt_sensor().entity_category == EntityCategory.DIAGNOSTIC


def test_primary_sensors_have_no_entity_category() -> None:
    assert _group_sensor().entity_category  is None
    assert _member_sensor().entity_category is None
