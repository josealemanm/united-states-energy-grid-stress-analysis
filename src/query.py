"""
query.py
Run whatever SQL is in scratch/scratch.sql against the built warehouse and print
the result. Edit scratch/scratch.sql, save it, then run:  python src/query.py
"""

from pathlib import Path
import duckdb
import pandas as pd

pd.set_option("display.max_rows", 100)
pd.set_option("display.width", 200)

DB_PATH = Path("data/interim/grid.duckdb")
SQL_PATH = Path("scratch/scratch.sql")

if not DB_PATH.exists():
    raise SystemExit(
        "No warehouse at data/interim/grid.duckdb. Run 04_export_for_bi.py first."
    )

if not SQL_PATH.exists() or not SQL_PATH.read_text().strip():
    SQL_PATH.parent.mkdir(parents=True, exist_ok=True)
    SQL_PATH.write_text("SELECT 'put your query here and re-run' AS message;\n")
    print("Created scratch/scratch.sql. Put a query in it and run again.")
    raise SystemExit(0)

# read_only=True means a scratch query can never damage the warehouse.
con = duckdb.connect(str(DB_PATH), read_only=True)
result = con.execute(SQL_PATH.read_text().strip()).df()
con.close()

print(result.to_string(index=False))
