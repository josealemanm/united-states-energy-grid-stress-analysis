"""
03b_bootstrap_intervals.py
Block-bootstrap 95% confidence intervals for the stress-penalty metrics.

Resampling is by calendar day, not by hour, because forecast errors within a
day are heavily autocorrelated: an hourly bootstrap would treat 24 correlated
errors as 24 independent draws and produce intervals that are far too tight.

Writes reports/bootstrap_intervals.csv.

Run:  python src/03b_bootstrap_intervals.py   (after 04_export_for_bi.py)
"""

from pathlib import Path
import numpy as np
import pandas as pd

FACT_PATH = Path("data/processed/fact_grid_hourly.parquet")
OUT_PATH = Path("reports/bootstrap_intervals.csv")
N_ITER = 2000
SEED = 20260902

def main():
    rng = np.random.default_rng(SEED)

    fact = pd.read_parquet(
        FACT_PATH,
        columns=["ba_code", "date_key", "abs_pct_error", "is_stress_hour", "is_ramp_stress_hour"],
    )
    fact = fact.dropna(subset=["abs_pct_error"])

    rows = []


    def bootstrap_ba(grp, flag_col, prefix, rng):
        """Day-block bootstrap of the normal/stress split defined by flag_col."""
        stress = grp[flag_col].fillna(False).to_numpy(dtype=bool)
        err = grp["abs_pct_error"].to_numpy(dtype=float)
        day = grp["date_key"].to_numpy()

        per_day = pd.DataFrame({
            "day": day,
            "sum_normal": np.where(~stress, err, 0.0),
            "cnt_normal": (~stress).astype(float),
            "sum_stress": np.where(stress, err, 0.0),
            "cnt_stress": stress.astype(float),
        }).groupby("day", sort=True).sum()

        sum_normal = per_day["sum_normal"].to_numpy()
        cnt_normal = per_day["cnt_normal"].to_numpy()
        sum_stress = per_day["sum_stress"].to_numpy()
        cnt_stress = per_day["cnt_stress"].to_numpy()
        n_days = len(per_day)

        idx = rng.integers(0, n_days, size=(N_ITER, n_days))

        boot_normal = sum_normal[idx].sum(axis=1) / np.maximum(cnt_normal[idx].sum(axis=1), 1)
        boot_stress_cnt = cnt_stress[idx].sum(axis=1)
        boot_stress = np.divide(
            sum_stress[idx].sum(axis=1), boot_stress_cnt,
            out=np.full(N_ITER, np.nan), where=boot_stress_cnt > 0,
        )

        return {
            f"{prefix}mape_normal": boot_normal,
            f"{prefix}mape_stress": boot_stress,
            f"{prefix}stress_penalty_pp": boot_stress - boot_normal,
            f"{prefix}stress_multiple": np.divide(
                boot_stress, boot_normal,
                out=np.full(N_ITER, np.nan), where=boot_normal > 0,
            ),
        }


    for ba, grp in fact.groupby("ba_code", sort=True):
        # Collapse to per-day sufficient statistics. Because every metric here is a
        # ratio of sums, a bootstrap iteration only needs each day's error sum and
        # hour count, which makes 2000 iterations a matrix op rather than a loop.
        metrics = bootstrap_ba(grp, "is_stress_hour", "", rng)
        metrics.update(bootstrap_ba(grp, "is_ramp_stress_hour", "ramp_", rng))

        for metric, draws in metrics.items():
            lo, mid, hi = np.nanpercentile(draws, [2.5, 50, 97.5])
            rows.append({
                "ba_code": ba, "metric": metric,
                "lo": round(float(lo), 4),
                "mid": round(float(mid), 4),
                "hi": round(float(hi), 4),
            })

    out = pd.DataFrame(rows)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False)

    penalty = out[out["metric"] == "stress_penalty_pp"].copy()
    penalty["crosses_zero"] = (penalty["lo"] < 0) & (penalty["hi"] > 0)
    print(f"{N_ITER} day-block resamples per balancing authority, seed {SEED}\n")
    print(penalty[["ba_code", "lo", "mid", "hi", "crosses_zero"]].to_string(index=False))
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
