"""Tests for the SettleUp config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import aiohttp

from custom_components.settleup.const import (
    CONF_API_KEY,
    CONF_EMAIL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    OPT_SCAN_INTERVAL,
)
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

FAKE_API_KEY  = "fake_api_key"
FAKE_EMAIL    = "test@example.com"
FAKE_PASSWORD = "test_password"

VALID_INPUT = {
    CONF_API_KEY : FAKE_API_KEY,
    CONF_EMAIL   : FAKE_EMAIL,
    CONF_PASSWORD: FAKE_PASSWORD,
}

# The config flow instantiates SettleUpAPI internally, so we patch it there.
_PATCH_API = "custom_components.settleup.config_flow.SettleUpAPI"


def _mock_api(user_id: str = "fake_user_id", login_side_effect=None):
    """Return a patched SettleUpAPI whose login() can succeed or raise."""
    instance = AsyncMock()
    instance.user_id = user_id
    if login_side_effect:
        instance.login.side_effect = login_side_effect
    return instance


async def test_form_is_shown(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"]    == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]  == {}


async def test_successful_setup_creates_entry(hass: HomeAssistant) -> None:
    with patch(_PATCH_API, return_value=_mock_api()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )

    assert result["type"]                    == FlowResultType.CREATE_ENTRY
    assert result["title"]              == FAKE_EMAIL
    assert result["data"][CONF_EMAIL]   == FAKE_EMAIL
    assert result["data"][CONF_API_KEY] == FAKE_API_KEY


async def test_invalid_auth_shows_error(hass: HomeAssistant) -> None:
    with patch(_PATCH_API, return_value=_mock_api(login_side_effect=RuntimeError("INVALID_PASSWORD"))):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )

    assert result["type"]   == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect_shows_error(hass: HomeAssistant) -> None:
    with patch(_PATCH_API, return_value=_mock_api(login_side_effect=aiohttp.ClientError())):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )

    assert result["type"]   == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_unknown_exception_shows_error(hass: HomeAssistant) -> None:
    with patch(_PATCH_API, return_value=_mock_api(login_side_effect=Exception("boom"))):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_INPUT
        )

    assert result["type"]   == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_reauth_success_updates_entry(hass: HomeAssistant) -> None:
    with patch(_PATCH_API, return_value=_mock_api()):
        r1 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(r1["flow_id"], user_input=VALID_INPUT)
        await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    with patch(_PATCH_API, return_value=_mock_api()):
        r2 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id}
        )
        result = await hass.config_entries.flow.async_configure(
            r2["flow_id"], user_input=VALID_INPUT
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_invalid_auth_shows_error(hass: HomeAssistant) -> None:
    with patch(_PATCH_API, return_value=_mock_api()):
        r1 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(r1["flow_id"], user_input=VALID_INPUT)
        await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    with patch(_PATCH_API, return_value=_mock_api(login_side_effect=RuntimeError("INVALID_PASSWORD"))):
        r2 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id}
        )
        result = await hass.config_entries.flow.async_configure(
            r2["flow_id"], user_input=VALID_INPUT
        )

    assert result["type"]   == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_already_configured_aborts(hass: HomeAssistant) -> None:
    """single_config_entry: true means a second init is aborted immediately by HA."""
    with patch(_PATCH_API, return_value=_mock_api()):
        r1 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(r1["flow_id"], user_input=VALID_INPUT)
        await hass.async_block_till_done()

    # HA aborts the flow before it reaches async_step_user — no configure needed.
    r2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert r2["type"] == FlowResultType.ABORT


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------

async def _setup_entry(hass: HomeAssistant) -> object:
    """Helper: create a configured entry and return it."""
    with patch(_PATCH_API, return_value=_mock_api()):
        r = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(r["flow_id"], user_input=VALID_INPUT)
        await hass.async_block_till_done()
    return hass.config_entries.async_entries(DOMAIN)[0]


async def test_options_flow_shows_current_interval(hass: HomeAssistant) -> None:
    entry = await _setup_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"]    == FlowResultType.FORM
    assert result["step_id"] == "init"
    schema_keys = list(result["data_schema"].schema)
    assert OPT_SCAN_INTERVAL in schema_keys


async def test_options_flow_saves_interval(hass: HomeAssistant) -> None:
    entry  = await _setup_entry(hass)
    init   = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        init["flow_id"], user_input={OPT_SCAN_INTERVAL: 10}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[OPT_SCAN_INTERVAL] == 10


async def test_options_flow_defaults_to_five_minutes(hass: HomeAssistant) -> None:
    entry = await _setup_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    default = result["data_schema"]({})
    assert default[OPT_SCAN_INTERVAL] == DEFAULT_SCAN_INTERVAL // 60


async def test_options_flow_preserves_known_groups(hass: HomeAssistant) -> None:
    entry = await _setup_entry(hass)
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "known_groups": {"g1": {"name": "Test"}}}
    )
    init = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        init["flow_id"], user_input={OPT_SCAN_INTERVAL: 15}
    )
    assert entry.options.get("known_groups") == {"g1": {"name": "Test"}}
