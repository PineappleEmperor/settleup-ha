"""Shared fixtures for SettleUp tests."""
from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.settleup.const import CONF_API_KEY, CONF_EMAIL, DOMAIN
from homeassistant.const import CONF_PASSWORD

FAKE_API_KEY  = "fake_api_key"
FAKE_EMAIL    = "test@example.com"
FAKE_PASSWORD = "test_password"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    return


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain    = DOMAIN,
        data      = {
            CONF_API_KEY : FAKE_API_KEY,
            CONF_EMAIL   : FAKE_EMAIL,
            CONF_PASSWORD: FAKE_PASSWORD,
        },
        unique_id = "fake_user_id",
    )
