"""SettleUp API client and data classes."""
from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Self

import aiohttp

from .const import FIREBASE_AUTH_URL, FIREBASE_REFRESH_URL, LIVE_DB, SANDBOX_DB


@dataclass
class SettleUpDebt:
    """A single debt between two members within a SettleUp group."""

    group_id    : str
    from_member : str
    to_member   : str
    amount      : float

    @classmethod
    def from_api(cls, group_id: str, data: dict[str, Any]) -> Self:
        """Create a SettleUpDebt from raw API debt data."""
        return cls(
            group_id    = group_id,
            from_member = data["from"],
            to_member   = data["to"],
            amount      = float(data["amount"]),
        )


@dataclass
class SettleUpMember:
    """A member within a particular SettleUp group."""

    group_id       : str
    member_id      : str
    active         : bool
    default_weight : str
    name           : str
    balance        : float
    debts          : list[SettleUpDebt] = field(default_factory=list)

    @classmethod
    def from_api(cls, group_id: str, member_id: str, data: dict[str, Any]) -> Self:
        """Create a SettleUpMember from raw API member data."""
        return cls(
            group_id       = group_id,
            member_id      = member_id,
            active         = data.get("active", True),
            default_weight = data.get("defaultWeight", "1"),
            name           = data.get("name", ""),
            balance        = 0.0,
        )

    def assign_debts(self, debts: list[SettleUpDebt]) -> None:
        """Filter the group debt list down to debts involving this member."""
        self.debts = [d for d in debts if self.member_id in (d.from_member, d.to_member)]


@dataclass
class SettleUpGroup:
    """Details of a SettleUp group, including its members and debts."""

    group_id              : str
    main_member_id        : str
    name                  : str
    converted_to_currency : str
    invite_link           : str | None
    invite_link_active    : bool
    invite_link_hash      : str | None
    last_changed          : int
    minimize_debts        : bool
    owner_color           : str
    members               : list[SettleUpMember]
    debts                 : list[SettleUpDebt]
    recent_transactions   : list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    async def from_api(
        cls, api: SettleUpAPI, group_id: str, main_member_id: str
    ) -> SettleUpGroup:
        """Fetch group details, members, debts, and recent transactions."""
        data = await api.get_group_details(group_id)
        group = cls(
            group_id              = group_id,
            main_member_id        = main_member_id,
            name                  = data.get("name", "Unnamed Group"),
            converted_to_currency = data.get("convertedToCurrency", "GBP"),
            invite_link           = data.get("inviteLink"),
            invite_link_active    = data.get("inviteLinkActive", False),
            invite_link_hash      = data.get("inviteLinkHash"),
            last_changed          = data.get("lastChanged", 0),
            minimize_debts        = data.get("minimizeDebts", False),
            owner_color           = data.get("ownerColor", "#4CAF50"),
            members               = [],
            debts                 = [],
        )
        await group.populate(api)
        return group

    async def populate(self, api: SettleUpAPI) -> None:
        """Fetch and assign members, debts, and recent transactions for this group."""
        raw_members  = await api.get_group_members(self.group_id)
        self.members = [
            SettleUpMember.from_api(self.group_id, mid, mdata)
            for mid, mdata in (raw_members or {}).items()
        ]
        raw_debts   = await api.get_group_debts(self.group_id)
        self.debts  = [
            SettleUpDebt.from_api(self.group_id, d) for d in (raw_debts or [])
        ]
        for member in self.members:
            member.assign_debts(self.debts)
        self.recent_transactions = await api.get_recent_transactions(self.group_id)

    def member_balance(self, member_id: str) -> float:
        """Return a member's net balance (positive = others owe them)."""
        balance = 0.0
        for debt in self.debts:
            if debt.to_member == member_id:
                balance += debt.amount
            elif debt.from_member == member_id:
                balance -= debt.amount
        return round(balance, 2)


class SettleUpAPI:
    """Client for SettleUp API."""

    def __init__(
        self,
        api_key: str,
        email: str,
        password: str,
        session: aiohttp.ClientSession,
        sandbox: bool = False,
    ) -> None:
        """Initialise the API client with user credentials."""
        self._api_key      = api_key
        self._email        = email
        self._password     = password
        self._session      = session
        self._db_url: str  = SANDBOX_DB if sandbox else LIVE_DB
        self.id_token      : str | None = None
        self.refresh_token : str | None = None
        self.user_id       : str | None = None
        self._token_expiry : float      = 0

    async def login(self) -> None:
        """Sign in with email/password and store the tokens."""
        url     = f"{FIREBASE_AUTH_URL}{self._api_key}"
        payload = {
            "email"             : self._email,
            "password"          : self._password,
            "returnSecureToken" : True,
        }
        token_header = {
            'Content-Type': 'application/json; charset=UTF-8',
            'X-Android-Package': 'com.settleup.android',
            'X-Android-Cert': '3a8174548074662d5e5c8e310086f6f9479b1836',
        }
        async with self._session.post(url, json=payload, headers=token_header) as resp:
            data: dict[str, Any] = await resp.json()
        if resp.status != 200 or "error" in data:
            error_msg = data.get("error", {}).get("message", "Unknown Error")
            raise RuntimeError(f"Firebase Error {resp.status}: {error_msg}")
        self.id_token      = data["idToken"]
        self.refresh_token = data["refreshToken"]
        self.user_id       = data["localId"]
        self._token_expiry = time.time() + int(data["expiresIn"]) - 30

    async def ensure_token(self) -> None:
        """Ensure a valid id_token is available."""
        if not self.refresh_token:
            await self.login()
        elif not self.id_token or time.time() >= self._token_expiry:
            await self._refresh_id_token()

    async def _refresh_id_token(self) -> None:
        url     = FIREBASE_REFRESH_URL.format(api_key=self._api_key)
        payload = {"grant_type": "refresh_token", "refresh_token": self.refresh_token}
        async with self._session.post(url, data=payload) as resp:
            data: dict[str, Any] = await resp.json()
        if "error" in data:
            raise RuntimeError(f"SettleUp token refresh failed: {data['error']}")
        self.id_token      = data["id_token"]
        self.refresh_token = data["refresh_token"]
        self.user_id       = data["user_id"]
        self._token_expiry = time.time() + int(data["expires_in"]) - 30

    async def _get(self, path: str) -> Any:
        await self.ensure_token()
        assert self.id_token is not None
        url = f"{self._db_url}/{path}.json"
        async with self._session.get(url, params={"auth": self.id_token}) as resp:
            return await resp.json()

    async def _post(self, path: str, payload: dict[str, Any]) -> Any:
        await self.ensure_token()
        assert self.id_token is not None
        url = f"{self._db_url}/{path}.json"
        async with self._session.post(url, params={"auth": self.id_token}, json=payload) as resp:
            return await resp.json()

    async def get_user_groups(self) -> dict[str, dict[str, Any]]:
        """Return the groups the authenticated user belongs to, keyed by group_id."""
        await self.ensure_token()
        result: dict[str, dict[str, Any]] = await self._get(f"userGroups/{self.user_id}") or {}
        return result

    async def get_group_details(self, group_id: str) -> dict[str, Any]:
        """Return top-level details for a group."""
        result: dict[str, Any] = await self._get(f"groups/{group_id}") or {}
        return result

    async def get_group_members(self, group_id: str) -> dict[str, dict[str, Any]]:
        """Return all members of a group, keyed by member_id."""
        result: dict[str, dict[str, Any]] = await self._get(f"members/{group_id}") or {}
        return result

    async def get_group_debts(self, group_id: str) -> list[dict[str, Any]]:
        """Return the current debts list for a group."""
        result: list[dict[str, Any]] = await self._get(f"debts/{group_id}") or []
        return result

    async def get_recent_transactions(
        self, group_id: str, limit: int = 3
    ) -> list[dict[str, Any]]:
        """Return the most recent transactions for a group, newest first."""
        await self.ensure_token()
        assert self.id_token is not None
        url = f"{self._db_url}/transactions/{group_id}.json"
        params = {
            "auth"        : self.id_token,
            "orderBy"     : '"$key"',
            "limitToLast" : str(limit),
        }
        async with self._session.get(url, params=params) as resp:
            data: dict[str, Any] = await resp.json() or {}
        return sorted(data.values(), key=lambda t: t.get("dateTime", 0), reverse=True)

    async def add_transaction(self, group_id: str, transaction: dict[str, Any]) -> str:
        """Add a transaction to the group."""
        result: dict[str, Any] = await self._post(f"transactions/{group_id}", transaction)
        if "error" in result:
            raise RuntimeError(f"SettleUp add_transaction failed: {result['error']}")
        return str(result["name"])
