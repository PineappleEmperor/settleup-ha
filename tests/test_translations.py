"""Verify every translation_key used in code resolves in strings.json."""
from __future__ import annotations

import json
from pathlib import Path
import re

import custom_components.settleup as pkg

PKG = Path(pkg.__file__).parent
STRINGS = json.loads((PKG / "strings.json").read_text())
EN = json.loads((PKG / "translations" / "en.json").read_text())


def test_strings_and_en_are_identical() -> None:
    assert STRINGS == EN


def test_exception_keys_exist_in_strings() -> None:
    used = set(re.findall(r'translation_key="([^"]+)"', (PKG / "services.py").read_text()))
    declared = set(STRINGS.get("exceptions", {}))
    assert used, "expected to find exception translation_keys in services.py"
    assert used <= declared, f"missing exception strings: {used - declared}"


def test_entity_keys_exist_in_strings() -> None:
    used = set(
        re.findall(r'_attr_translation_key\s*=\s*"([^"]+)"', (PKG / "sensor.py").read_text())
    )
    declared = set(STRINGS.get("entity", {}).get("sensor", {}))
    assert used, "expected to find entity translation_keys in sensor.py"
    assert used <= declared, f"missing entity strings: {used - declared}"
