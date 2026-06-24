"""Unit tests for the manifest version gate decision logic."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "manifest_gate", Path(__file__).parents[1] / "scripts" / "manifest_gate.py"
)
assert _SPEC and _SPEC.loader
manifest_gate = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(manifest_gate)
evaluate = manifest_gate.evaluate
label_bump = manifest_gate.label_bump


def ok(*args, **kwargs) -> bool:
    return evaluate(*args, **kwargs)[0]


def test_unchanged_vs_last_release_fails() -> None:
    assert not ok("1.1.0", "1.1.0", "1.1.0", ["fix"])


def test_feature_minor_bump_passes() -> None:
    assert ok("1.1.0", "1.1.0", "1.2.0", ["feature"])


def test_feature_only_patch_bump_under_bumps() -> None:
    assert not ok("1.1.0", "1.1.0", "1.1.1", ["feature"])


def test_chore_rides_in_cycle_minor_version() -> None:
    # The shipped bug: a chore PR at 1.2.0 while last release is 1.1.0 and main is
    # already 1.2.0 (a feature merged this cycle). Must PASS — it rides the cycle.
    assert ok("1.1.0", "1.2.0", "1.2.0", ["chore"])


def test_chore_overbump_beyond_cycle_fails() -> None:
    assert not ok("1.1.0", "1.2.0", "2.0.0", ["chore"])


def test_fix_patch_when_main_at_release() -> None:
    assert ok("1.1.0", "1.1.0", "1.1.1", ["fix"])


def test_breaking_major_bump_passes() -> None:
    assert ok("1.1.0", "1.2.0", "2.0.0", ["xfeat"])


def test_breaking_under_bump_fails() -> None:
    assert not ok("1.1.0", "1.2.0", "1.3.0", ["xfeat"])


def test_prerelease_only_needs_to_differ() -> None:
    assert ok("1.1.0", "1.1.0", "2.0.0rc1", ["feature"])
    assert not ok("2.0.0rc1", "2.0.0rc1", "2.0.0rc1", ["feature"])


def test_dependabot_exempt() -> None:
    assert ok("1.1.0", "1.1.0", "1.1.0", [], dependabot=True)


def test_no_managed_label_passes_when_changed() -> None:
    assert ok("1.1.0", "1.1.0", "1.1.5", [])


def test_no_release_yet_uses_zero_base() -> None:
    assert ok("", "", "0.1.0", ["feature"])


def test_label_bump_breaking_precedes_feature() -> None:
    assert label_bump(["xfeature"]) == "major"
    assert label_bump(["feature"]) == "minor"
    assert label_bump(["chore"]) == "patch"
    assert label_bump(["docs-only"]) is None
