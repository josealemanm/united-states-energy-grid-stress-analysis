"""
04_export_for_bi.py
Executes the warehouse SQL and exports star schema tables as parquet
for downstream BI tools to consume.

Run:  python src/04_export_for_bi.py
"""

import sys
from pathlib import Path
import duckdb
import pandas as pd

DB_PATH = Path("data/interim/grid.duckdb")
OUT_DIR = Path("data/processed")
OUT_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def main():
    con = duckdb.connect(str(DB_PATH))

    sql = Path("src/03_build_warehouse.sql").read_text()
    print("Building warehouse...")
    con.execute(sql)

    TABLES = [
        "dim_ba",
        "dim_fuel",
        "dim_date",
        "fact_grid_hourly",
        "fact_fuel_hourly",
        "analysis_stress_penalty",
        "analysis_ramp_stress_penalty",
    ]

    # --csv also writes CSV copies. Power BI reads parquet natively, but older
    # builds occasionally refuse it, and CSV is the escape hatch that always works.
    also_csv = "--csv" in sys.argv

    for t in TABLES:
        # Relational API rather than a formatted COPY statement: a table name is an
        # identifier, so it cannot be bound as a query parameter, and building the
        # SQL by hand is the thing worth avoiding.
        rel = con.table(t)
        n = rel.count("*").fetchone()[0]
        rel.write_parquet((OUT_DIR / f"{t}.parquet").as_posix())
        if also_csv:
            rel.write_csv((OUT_DIR / f"{t}.csv").as_posix())
        print(f"  {t:28s} {n:>10,} rows{'  (+csv)' if also_csv else ''}")

    print("\n" + "=" * 70)
    print("HEADLINE RESULT: forecast error, stress hours vs normal hours")
    print("=" * 70)
    result = con.execute("""
        SELECT ba_code, region, mape_normal, mape_stress,
               stress_penalty_pp, stress_multiple
        FROM analysis_stress_penalty
        ORDER BY stress_penalty_pp DESC
    """).df()
    print(result.to_string(index=False))

    con.close()
    print(f"\nParquet written to {OUT_DIR}/")


if __name__ == "__main__":
    main()
