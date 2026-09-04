"""
Regenerate tests/fixtures/region_TEST.parquet.

Synthetic, deterministic, and deliberately dirty: it carries a duplicate hour,
a null, a zero demand, a zero forecast and a balance-identity failure so the
validator and warehouse have something to actually catch.

Run:  python tests/make_fixture.py
"""

from pathlib import Path
import numpy as np
import pandas as pd

OUT = Path(__file__).parent / "fixtures" / "region_TEST.parquet"
N_HOURS = 500
SEED = 7

rng = np.random.default_rng(SEED)
hours = pd.date_range("2025-01-01T00", periods=N_HOURS, freq="h", tz="UTC")

# A daily sine so some hours land in the top 5% and stress hours exist.
t = np.arange(N_HOURS)
demand = 20000 + 4000 * np.sin(2 * np.pi * t / 24) + rng.normal(0, 200, N_HOURS)
forecast = demand + rng.normal(0, 400, N_HOURS)
net_gen = demand + rng.normal(0, 150, N_HOURS)
interchange = net_gen - demand  # balance identity holds by construction

rows = []
for i, h in enumerate(hours):
    stamp = h.strftime("%Y-%m-%dT%H")
    rows += [
        {"period": stamp, "respondent": "TEST", "type": "D", "value": demand[i]},
        {"period": stamp, "respondent": "TEST", "type": "DF", "value": forecast[i]},
        {"period": stamp, "respondent": "TEST", "type": "NG", "value": net_gen[i]},
        {"period": stamp, "respondent": "TEST", "type": "TI", "value": interchange[i]},
    ]

df = pd.DataFrame(rows)

# --- Deliberate defects, one of each kind the pipeline claims to handle ------
first = hours[0].strftime("%Y-%m-%dT%H")
h10 = hours[10].strftime("%Y-%m-%dT%H")
h11 = hours[11].strftime("%Y-%m-%dT%H")
h12 = hours[12].strftime("%Y-%m-%dT%H")

# 1. duplicate row (same period + type)
df = pd.concat([df, df[(df.period == first) & (df.type == "D")]], ignore_index=True)
# 2. null demand
df.loc[(df.period == h10) & (df.type == "D"), "value"] = np.nan
# 3. zero demand (impossible)
df.loc[(df.period == h11) & (df.type == "D"), "value"] = 0.0
# 4. zero day-ahead forecast (impossible)
df.loc[(df.period == h12) & (df.type == "DF"), "value"] = 0.0
# 5. balance identity failure at a known hour
df.loc[(df.period == hours[20].strftime("%Y-%m-%dT%H")) & (df.type == "NG"), "value"] *= 1.5

OUT.parent.mkdir(parents=True, exist_ok=True)
df.to_parquet(OUT, index=False)
print(f"Wrote {OUT} ({len(df):,} rows)")
