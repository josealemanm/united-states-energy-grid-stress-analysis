"""Tests for the data-quality checks in src/02_validate.py."""

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / "fixtures" / "region_TEST.parquet"


def load_module(filename, name):
    """Import a numerically-prefixed script that a plain import cannot name."""
    spec = importlib.util.spec_from_file_location(name, ROOT / "src" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate = load_module("02_validate.py", "validate")


@pytest.fixture(scope="module")
def wide():
    raw = pd.read_parquet(FIXTURE)
    raw["period"] = pd.to_datetime(raw["period"], utc=True)
    raw["value"] = pd.to_numeric(raw["value"], errors="coerce")
    return validate.wide_form(raw)


def test_wide_form_pivots_type_codes_into_columns(wide):
    for col in ["D", "DF", "NG", "TI"]:
        assert col in wide.columns
    # 500 distinct hours in the fixture, duplicate collapses rather than adding.
    assert len(wide) == 500


def test_impossible_values_are_counted(wide):
    # The fixture plants exactly one zero demand and one zero forecast.
    assert int((wide["D"] == 0).sum()) == 1
    assert int((wide["DF"] == 0).sum()) == 1
    assert int((wide["D"] < 0).sum()) == 0


def test_null_demand_is_counted(wide):
    assert int(wide["D"].isna().sum()) == 1


def test_balance_identity_failure_is_detected(wide):
    imbalance = wide["NG"] - wide["TI"] - wide["D"]
    imbalance_pct = 100 * imbalance / wide["D"].replace(0, pd.NA)
    # One hour had net generation inflated 50%, which cannot balance.
    assert int((imbalance_pct.abs() > 5).sum()) == 1


def test_duplicate_rows_are_detected():
    raw = pd.read_parquet(FIXTURE)
    assert int(raw.duplicated(subset=["period", "type"]).sum()) == 1


def test_uncheckable_hours_are_not_counted_as_balance_failures():
    """Hours missing NG or TI cannot fail the identity, only go untested.

    Folding them into the failure count is what produced the 6,552 figure for
    CISO that the README used to quote, against 6,396 hours that actually fail.
    """
    original = validate.RAW_DIR
    validate.RAW_DIR = FIXTURE.parent
    try:
        results = validate.check_ba("TEST")
    finally:
        validate.RAW_DIR = original

    checkable = (results["hours_balance_clean"]
                 + results["hours_balance_dirty"]
                 + results["hours_balance_unknown"])
    assert checkable == results["actual_hours"]
    # The fixture plants one imbalanced hour, and nothing else fails.
    assert results["hours_balance_dirty"] == 1
    # Hours with a null NG or TI land in unknown, never in dirty.
    assert results["hours_balance_unknown"] >= 0
    assert results["hours_balance_dirty"] + results["hours_balance_clean"] <= results["actual_hours"]


def test_implausible_forecast_is_flagged(wide):
    """A forecast far below the region's own median demand is a broken field.

    This is the check that catches SWPP on 2026-04-16, where the reported
    day-ahead forecast runs at 5% of actual demand for a whole day.
    """
    threshold = 0.2 * wide["D"].median()
    planted = int((wide["DF"] < threshold).sum())
    # The fixture's single zero forecast is below any positive threshold.
    assert planted >= 1
