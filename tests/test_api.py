"""Unit tests for the SettleUp API layer."""
from __future__ import annotations

import time

import aiohttp
import pytest

from unittest.mock import AsyncMock, MagicMock

from custom_components.settleup.api import (
    SettleUpAPI,
    SettleUpDebt,
    SettleUpGroup,
    SettleUpMember,
)

FAKE_API_KEY  = "fake_api_key"
FAKE_EMAIL    = "test@example.com"
FAKE_PASSWORD = "test_password"

MOCK_LOGIN_RESPONSE = {
    "idToken"      : "fake_id_token",
    "refreshToken" : "fake_refresh_token",
    "localId"      : "fake_user_id",
    "expiresIn"    : "3600",
}

MOCK_REFRESH_RESPONSE = {
    "id_token"      : "new_fake_id_token",
    "refresh_token" : "new_fake_refresh_token",
    "user_id"       : "fake_user_id",
    "expires_in"    : "3600",
}

MOCK_USER_GROUPS = {
    "group_abc": {"memberId": "member_alice", "order": 0},
}

MOCK_GROUP_DETAILS = {
    "name"                : "Holiday",
    "convertedToCurrency" : "GBP",
    "lastChanged"         : 1700000000,
    "minimizeDebts"       : False,
    "ownerColor"          : "#4CAF50",
}

MOCK_MEMBERS = {
    "member_alice": {"name": "Alice", "active": True, "defaultWeight": "1"},
    "member_bob"  : {"name": "Bob",   "active": True, "defaultWeight": "1"},
}

MOCK_DEBTS = [
    {"from": "member_bob", "to": "member_alice", "amount": "15.00"},
]

MOCK_TRANSACTIONS = {
    "txn_a": {
        "dateTime": 1700000100, "purpose": "Dinner", "type": "expense",
        "currencyCode": "GBP",
        "whoPaid": [{"memberId": "member_alice", "weight": "30.0"}],
        "items"  : [{"amount": "30.00", "forWhom": [{"memberId": "member_bob", "weight": "1"}]}],
    },
    "txn_b": {
        "dateTime": 1700000200, "purpose": "Taxi", "type": "expense",
        "currencyCode": "GBP",
        "whoPaid": [{"memberId": "member_bob", "weight": "10.0"}],
        "items"  : [{"amount": "10.00", "forWhom": [{"memberId": "member_alice", "weight": "1"}]}],
    },
    "txn_c": {
        "dateTime": 1700000050, "purpose": "Supplies", "type": "expense",
        "currencyCode": "GBP",
        "whoPaid": [{"memberId": "member_alice", "weight": "5.0"}],
        "items"  : [{"amount": "5.00",  "forWhom": [{"memberId": "member_bob", "weight": "1"}]}],
    },
}


def _make_mock_response(json_data: object, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status     = status
    resp.json       = AsyncMock(return_value=json_data)
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__  = AsyncMock(return_value=False)
    return resp


def make_mock_session(
    post_responses: list[object] | None = None,
    get_responses : list[object] | None = None,
) -> MagicMock:
    session = MagicMock()
    if post_responses is not None:
        session.post.side_effect = [_make_mock_response(r) for r in post_responses]
    if get_responses is not None:
        session.get.side_effect  = [_make_mock_response(r) for r in get_responses]
    return session

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _api(session, sandbox: bool = True) -> SettleUpAPI:
    return SettleUpAPI(
        api_key  = FAKE_API_KEY,
        email    = FAKE_EMAIL,
        password = FAKE_PASSWORD,
        session  = session,
        sandbox  = sandbox,
    )


def _authed_api(get_responses: list[object]) -> SettleUpAPI:
    """Return a pre-authenticated API instance with queued GET responses."""
    session = make_mock_session(get_responses=get_responses)
    api = _api(session)
    api.id_token      = "fake_id_token"
    api.refresh_token = "fake_refresh"
    api._token_expiry = time.time() + 3600
    api.user_id       = "fake_user_id"
    return api


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

async def test_login_stores_tokens() -> None:
    api = _api(make_mock_session(post_responses=[MOCK_LOGIN_RESPONSE]))
    await api.login()
    assert api.id_token      == "fake_id_token"
    assert api.refresh_token == "fake_refresh_token"
    assert api.user_id       == "fake_user_id"
    assert api._token_expiry  > time.time()


async def test_login_bad_credentials_raises() -> None:
    resp = {"error": {"message": "INVALID_PASSWORD"}}
    api  = _api(make_mock_session(post_responses=[resp]))
    with pytest.raises(RuntimeError, match="INVALID_PASSWORD"):
        await api.login()


async def test_ensure_token_calls_login_when_no_tokens() -> None:
    api = _api(make_mock_session(post_responses=[MOCK_LOGIN_RESPONSE]))
    assert api.id_token is None
    await api.ensure_token()
    assert api.id_token == "fake_id_token"


async def test_ensure_token_refreshes_expired_token() -> None:
    api = _api(make_mock_session(post_responses=[MOCK_REFRESH_RESPONSE]))
    api.refresh_token = "old_refresh"
    api.id_token      = "old_id"
    api._token_expiry = time.time() - 1          # already expired
    await api.ensure_token()
    assert api.id_token == "new_fake_id_token"


async def test_ensure_token_does_nothing_when_valid() -> None:
    session = make_mock_session()
    api = _api(session)
    api.id_token      = "valid_token"
    api.refresh_token = "valid_refresh"
    api._token_expiry = time.time() + 3600
    await api.ensure_token()
    session.post.assert_not_called()


async def test_refresh_token_failure_raises() -> None:
    api = _api(make_mock_session(post_responses=[{"error": "TOKEN_EXPIRED"}]))
    api.refresh_token = "bad_refresh"
    api.id_token      = "old"
    api._token_expiry = time.time() - 1
    with pytest.raises(RuntimeError, match="TOKEN_EXPIRED"):
        await api._refresh_id_token()


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

async def test_get_user_groups() -> None:
    result = await _authed_api([MOCK_USER_GROUPS]).get_user_groups()
    assert "group_abc"            in result
    assert result["group_abc"]["memberId"] == "member_alice"


async def test_get_user_groups_returns_empty_on_null() -> None:
    result = await _authed_api([None]).get_user_groups()
    assert result == {}


async def test_get_group_details() -> None:
    result = await _authed_api([MOCK_GROUP_DETAILS]).get_group_details("group_abc")
    assert result["name"]                == "Holiday"
    assert result["convertedToCurrency"] == "GBP"


async def test_get_group_members() -> None:
    result = await _authed_api([MOCK_MEMBERS]).get_group_members("group_abc")
    assert "member_alice" in result
    assert result["member_alice"]["name"] == "Alice"


async def test_get_group_debts() -> None:
    result = await _authed_api([MOCK_DEBTS]).get_group_debts("group_abc")
    assert len(result) == 1
    assert result[0]["from"] == "member_bob"
    assert result[0]["to"]   == "member_alice"


async def test_get_recent_transactions_sorted_newest_first() -> None:
    result = await _authed_api([MOCK_TRANSACTIONS]).get_recent_transactions("group_abc")
    assert result[0]["purpose"] == "Taxi"      # dateTime 1700000200 — newest
    assert result[1]["purpose"] == "Dinner"    # dateTime 1700000100
    assert result[2]["purpose"] == "Supplies"  # dateTime 1700000050 — oldest


async def test_get_recent_transactions_null_returns_empty() -> None:
    result = await _authed_api([None]).get_recent_transactions("group_abc")
    assert result == []


async def test_add_transaction_returns_key() -> None:
    session = make_mock_session(post_responses=[{"name": "new_firebase_key"}])
    api = _api(session)
    api.id_token      = "fake_id_token"
    api.refresh_token = "fake_refresh"
    api._token_expiry = time.time() + 3600
    key = await api.add_transaction("group_abc", {"type": "expense"})
    assert key == "new_firebase_key"


async def test_add_transaction_api_error_raises() -> None:
    session = make_mock_session(post_responses=[{"error": "PERMISSION_DENIED"}])
    api = _api(session)
    api.id_token      = "fake_id_token"
    api.refresh_token = "fake_refresh"
    api._token_expiry = time.time() + 3600
    with pytest.raises(RuntimeError, match="PERMISSION_DENIED"):
        await api.add_transaction("group_abc", {})


# ---------------------------------------------------------------------------
# Data class unit tests
# ---------------------------------------------------------------------------

def test_debt_from_api() -> None:
    debt = SettleUpDebt.from_api("g1", {"from": "m1", "to": "m2", "amount": "12.50"})
    assert debt.from_member == "m1"
    assert debt.to_member   == "m2"
    assert debt.amount      == 12.50


def test_member_from_api_defaults() -> None:
    member = SettleUpMember.from_api("g1", "m1", {"name": "Alice"})
    assert member.name           == "Alice"
    assert member.active         is True
    assert member.default_weight == "1"
    assert member.balance        == 0.0


def test_member_assign_debts_filters_correctly() -> None:
    debts = [
        SettleUpDebt("g1", "m1", "m2", 10.0),
        SettleUpDebt("g1", "m2", "m3",  5.0),
        SettleUpDebt("g1", "m3", "m4",  7.0),
    ]
    member = SettleUpMember("g1", "m2", True, "1", "Bob", 0.0)
    member.assign_debts(debts)
    assert len(member.debts) == 2
    assert all(d.from_member == "m2" or d.to_member == "m2" for d in member.debts)


def test_member_balance_owed_to() -> None:
    """Member who is owed money should have a positive balance."""
    group = _group_with_debts([
        SettleUpDebt("g1", "m2", "m1", 20.0),
        SettleUpDebt("g1", "m3", "m1", 10.0),
    ])
    assert group.member_balance("m1") == 30.0


def test_member_balance_owes() -> None:
    """Member who owes should have a negative balance."""
    group = _group_with_debts([SettleUpDebt("g1", "m1", "m2", 15.0)])
    assert group.member_balance("m1") == -15.0


def test_member_balance_net() -> None:
    group = _group_with_debts([
        SettleUpDebt("g1", "m2", "m1", 20.0),  # owed 20
        SettleUpDebt("g1", "m1", "m3",  5.0),  # owes 5
    ])
    assert group.member_balance("m1") == 15.0


def test_member_balance_zero_when_no_debts() -> None:
    assert _group_with_debts([]).member_balance("m1") == 0.0


def _group_with_debts(debts: list[SettleUpDebt]) -> SettleUpGroup:
    return SettleUpGroup(
        group_id              = "g1",
        main_member_id        = "m1",
        name                  = "Test",
        converted_to_currency = "GBP",
        invite_link           = None,
        invite_link_active    = False,
        invite_link_hash      = None,
        last_changed          = 0,
        minimize_debts        = False,
        owner_color           = "#4CAF50",
        members               = [],
        debts                 = debts,
    )

