"""
Tests for src/03_build_warehouse.sql.

Runs the real warehouse SQL against the synthetic fixture in an in-memory
DuckDB, so the assertions cover the actual shipped SQL rather than a copy.
"""

from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = Path(__file__).parent / "fixtures"
SQL_PATH = ROOT / "src" / "03_build_warehouse.sql"


@pytest.fixture(scope="module")
def con():
    """Build the warehouse from the fixture instead of data/raw."""
    sql = SQL_PATH.read_text()
    sql = sql.replace(
        "read_parquet('data/raw/region_*.parquet')",
        f"read_parquet('{(FIXTURE_DIR / 'region_*.parquet').as_posix()}')",
    )
    # The fixture has no fuel data; an empty typed stand-in keeps the joins valid.
    sql = sql.replace(
        "read_parquet('data/raw/fuel_*.parquet') f",
        "(SELECT NULL::VARCHAR AS respondent, NULL::VARCHAR AS period, "
        "NULL::VARCHAR AS fueltype, NULL::DOUBLE AS value WHERE FALSE) f",
    )
    # dim_ba ships a fixed eight-region list and stg_region_enriched inner-joins
    # to it, so the fixture's BA has to exist there or every row is dropped.
    anchor = ") AS t(ba_code, ba_name, region, interconnection, local_tz, is_home_grid);"
    assert anchor in sql, "dim_ba column list changed; update the test shim"
    sql = sql.replace(
        anchor,
        ",\n    ('TEST', 'Test Balancing Authority', 'Test', 'Eastern',"
        " 'America/New_York', FALSE)\n" + anchor,
    )

    connection = duckdb.connect(":memory:")
    connection.execute(sql)
    yield connection
    connection.close()


def test_warehouse_sql_executes(con):
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    for expected in [
        "dim_ba", "dim_fuel", "dim_date", "fact_grid_hourly",
        "fact_fuel_hourly", "analysis_stress_penalty",
        "analysis_ramp_stress_penalty",
    ]:
        assert expected in tables


def test_no_self_referential_build():
    """fact_grid_hourly must never be built by reading fact_grid_hourly."""
    sql = SQL_PATH.read_text()
    body = sql.split("CREATE OR REPLACE TABLE fact_grid_hourly AS", 1)[1]
    body = body.split("CREATE OR REPLACE TABLE", 1)[0]
    assert "FROM fact_grid_hourly\n" not in body
    assert "FROM fact_grid_hourly " not in body


def test_impossible_rows_are_excluded(con):
    """Zero demand and zero forecast hours must not reach the fact table."""
    bad = con.execute("""
        SELECT COUNT(*) FROM fact_grid_hourly
        WHERE demand_mw <= 0 OR forecast_mw <= 0
    """).fetchone()[0]
    assert bad == 0


def test_stress_hours_are_top_five_percent(con):
    total, stress = con.execute("""
        SELECT COUNT(*), SUM(CASE WHEN is_stress_hour THEN 1 ELSE 0 END)
        FROM fact_grid_hourly
    """).fetchone()
    assert total > 0
    # PERCENT_RANK >= 0.95 selects roughly the top 5% within each partition.
    assert 0.02 <= stress / total <= 0.10


def test_error_columns_are_consistent(con):
    """abs_pct_error must equal the absolute value of pct_error."""
    mismatch = con.execute("""
        SELECT COUNT(*) FROM fact_grid_hourly
        WHERE ABS(abs_pct_error - ABS(pct_error)) > 1e-9
    """).fetchone()[0]
    assert mismatch == 0


def test_balance_clean_flag_matches_threshold(con):
    mismatch = con.execute("""
        SELECT COUNT(*) FROM fact_grid_hourly
        WHERE is_balance_clean <> (ABS(imbalance_pct) <= 5)
    """).fetchone()[0]
    assert mismatch == 0
