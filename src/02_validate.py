"""
02_validate.py
Data quality assessment of raw EIA-930 pulls.
Writes reports/data_quality_report.md and a machine readable CSV.

Run:  python src/02_validate.py
"""

from pathlib import Path
import pandas as pd
import numpy as np

RAW_DIR = Path("data/raw")
REPORT_DIR = Path("reports")
REPORT_DIR.mkdir(exist_ok=True)

RESPONDENTS = ["PJM", "MISO", "CISO", "ERCO", "ISNE", "NYIS", "SWPP", "SOCO"]


def load_region(ba):
    df = pd.read_parquet(RAW_DIR / f"region_{ba}.parquet")
    df["period"] = pd.to_datetime(df["period"], utc=True)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


def wide_form(df):
    """Pivot the long type codes into one row per hour."""
    wide = df.pivot_table(
        index="period", columns="type", values="value", aggfunc="first"
    ).reset_index()
    for col in ["D", "DF", "NG", "TI"]:
        if col not in wide.columns:
            wide[col] = np.nan
    return wide


def check_ba(ba):
    raw = load_region(ba)
    wide = wide_form(raw)
    results = {"ba": ba}

    # --- Completeness ------------------------------------------------------
    span_start, span_end = wide["period"].min(), wide["period"].max()
    expected = pd.date_range(span_start, span_end, freq="h", tz="UTC")
    actual = set(wide["period"])
    missing = [h for h in expected if h not in actual]

    results["first_hour"] = span_start
    results["last_hour"] = span_end
    results["expected_hours"] = len(expected)
    results["actual_hours"] = len(actual)
    results["missing_hours"] = len(missing)
    results["pct_complete"] = round(100 * len(actual) / len(expected), 3)

    # --- Duplicates --------------------------------------------------------
    dupes = raw.duplicated(subset=["period", "type"]).sum()
    results["duplicate_rows"] = int(dupes)

    # --- Nulls -------------------------------------------------------------
    for col in ["D", "DF", "NG", "TI"]:
        results[f"null_{col}"] = int(wide[col].isna().sum())

    # --- Impossible values -------------------------------------------------
    # Demand and forecast must be positive per the EIA-930 form instructions.
    results["negative_D"] = int((wide["D"] < 0).sum())
    results["negative_DF"] = int((wide["DF"] < 0).sum())
    results["zero_D"] = int((wide["D"] == 0).sum())
    # A day-ahead forecast of exactly zero is a missing value wearing a number.
    results["zero_DF"] = int((wide["DF"] == 0).sum())
    # Demand below a fifth of the region's own median is not a real load drop;
    # it is a truncated or mis-scaled reading. Reported, not silently dropped.
    results["implausible_D"] = int((wide["D"] < 0.2 * wide["D"].median()).sum())
    # The same test applied to the forecast, which the earlier version of this
    # script did not run. A day-ahead forecast of 1,599 MW against 30,813 MW of
    # actual demand is not a bad forecast, it is a broken field, and left
    # unflagged a single day of them moves a region's stress penalty.
    results["implausible_DF"] = int((wide["DF"] < 0.2 * wide["D"].median()).sum())

    # --- Outliers (robust: median absolute deviation, not standard deviation)
    d = wide["D"].dropna()
    med = d.median()
    mad = (d - med).abs().median()
    if mad > 0:
        modified_z = 0.6745 * (d - med) / mad
        results["outlier_hours_D"] = int((modified_z.abs() > 6).sum())
    else:
        results["outlier_hours_D"] = 0

    # --- The balance identity: NG - TI should equal D ----------------------
    wide["imbalance_mw"] = wide["NG"] - wide["TI"] - wide["D"]
    wide["imbalance_pct"] = 100 * wide["imbalance_mw"] / wide["D"].replace(0, np.nan)

    results["median_abs_imbalance_pct"] = round(
        wide["imbalance_pct"].abs().median(), 3
    )
    results["p95_abs_imbalance_pct"] = round(
        wide["imbalance_pct"].abs().quantile(0.95), 3
    )
    results["hours_imbalance_over_5pct"] = int(
        (wide["imbalance_pct"].abs() > 5).sum()
    )

    # --- Headline forecast error (a preview of the real analysis) ----------
    wide["abs_pct_err"] = 100 * (wide["DF"] - wide["D"]).abs() / wide["D"].replace(0, np.nan)
    results["overall_MAPE"] = round(wide["abs_pct_err"].mean(), 3)

    # --- Forecast error restricted to hours that actually balance ----------
    # A region whose reported numbers do not add up can post a large "forecast
    # error" that is really a reporting artifact. Splitting the two apart is
    # the difference between blaming the forecaster and blaming the meter.
    # Three states, not two: the identity holds, it fails, or NG and TI are not
    # both reported so it cannot be evaluated at all. Folding the third into
    # "fails" overstates the failure count, which is where the 6,552 figure that
    # used to appear in the README came from.
    checkable = wide["imbalance_pct"].notna()
    clean = checkable & (wide["imbalance_pct"].abs() <= 5)
    dirty = checkable & (wide["imbalance_pct"].abs() > 5)
    results["hours_balance_clean"] = int(clean.sum())
    results["hours_balance_dirty"] = int(dirty.sum())
    results["hours_balance_unknown"] = int((~checkable).sum())
    results["MAPE_balance_clean"] = round(wide.loc[clean, "abs_pct_err"].mean(), 3)
    results["MAPE_balance_dirty"] = round(wide.loc[dirty, "abs_pct_err"].mean(), 3)

    return results


def main():
    rows = [check_ba(ba) for ba in RESPONDENTS]
    qa = pd.DataFrame(rows)
    qa.to_csv(REPORT_DIR / "data_quality_summary.csv", index=False)

    lines = [
        "# Data Quality Report",
        "",
        "Source: U.S. Energy Information Administration, Form EIA-930, API v2.",
        "Generated by `src/02_validate.py`.",
        "",
        "## Completeness",
        "",
        qa[["ba", "expected_hours", "actual_hours", "missing_hours",
            "pct_complete", "duplicate_rows"]].to_markdown(index=False),
        "",
        "## Null and impossible values",
        "",
        qa[["ba", "null_D", "null_DF", "null_NG", "null_TI",
            "negative_D", "zero_D", "zero_DF", "implausible_D",
            "implausible_DF", "outlier_hours_D"]].to_markdown(index=False),
        "",
        "`zero_DF` counts hours reporting a day-ahead forecast of exactly zero.",
        "The form instructions require a positive value, so these are missing",
        "values encoded as zero; each one would otherwise contribute a spurious",
        "100% forecast error. They are excluded in the warehouse build.",
        "",
        "`implausible_D` counts hours whose demand is below a fifth of that",
        "region's own median demand. These are truncated or mis-scaled readings",
        "rather than real load collapses. They are reported here and left in the",
        "warehouse, because dropping them needs a threshold this project has no",
        "principled basis to set; be aware that they dominate worst-hour",
        "statistics. The clearest example is SOCO at 2026-08-30 20:00 local,",
        "reporting 3,402 MW of demand against 39,978 MW of net generation.",
        "",
        "`implausible_DF` applies the same test to the day-ahead forecast, and",
        "it is the check this report was missing. NYIS's 92 are the zero-forecast",
        "hours already counted in `zero_DF`. All 14 of SWPP's fall on one day,",
        "2026-04-16, where the reported forecast runs between",
        "5% and 35% of actual demand hour after hour while net generation tracks",
        "demand normally. That is a broken field, not a forecast miss. It is",
        "left in for the same reason as `implausible_D`, but it is worth knowing",
        "that removing that single day cuts SWPP's stress penalty from +0.42 to",
        "+0.12 percentage points. SWPP's negative skill score survives it",
        "(-0.77 to -0.74), so that finding does not rest on the bad day.",
        "",
        "## Balance identity check (NG - TI = D)",
        "",
        "The EIA-930 accounting identity requires net generation minus total",
        "interchange to equal demand. Deviation indicates measurement or",
        "reporting error. Values are the absolute deviation as a percent of demand.",
        "",
        qa[["ba", "median_abs_imbalance_pct", "p95_abs_imbalance_pct",
            "hours_imbalance_over_5pct"]].to_markdown(index=False),
        "",
        "## Headline forecast error",
        "",
        qa[["ba", "overall_MAPE"]].to_markdown(index=False),
        "",
        "## Forecast error, split by whether the hour balances",
        "",
        "Hours where net generation minus interchange misses demand by more than",
        "5% are reported separately below. Where the two columns diverge sharply,",
        "the headline MAPE is partly measuring reporting quality rather than",
        "forecast quality, and the region's rank should be read with that in mind.",
        "`hours_balance_unknown` are hours where net generation or interchange is",
        "not reported, so the identity cannot be evaluated either way; they are",
        "neither clean nor dirty.",
        "",
        (qa[["ba", "hours_balance_clean", "hours_balance_dirty",
             "hours_balance_unknown", "MAPE_balance_clean", "MAPE_balance_dirty"]]
         .fillna({"MAPE_balance_dirty": "no such hours"})
         .to_markdown(index=False)),
        "",
        "CISO is the region where this matters most. It fails the balance check",
        "in 6,430 of the 17,399 hours where the check can be run, and its",
        "forecast error is markedly lower on the hours that do balance, so its",
        "headline MAPE and its stress",
        "penalty both partly measure reporting quality rather than forecasting.",
        "The warehouse carries `mape_clean` and `stress_penalty_clean_pp` in",
        "`analysis_stress_penalty` for exactly this reason; use those when",
        "ranking regions on forecast quality.",
        "",
        "## Handling decisions",
        "",
        "1. Hours missing any of D, DF, NG or TI are excluded from forecast",
        "   error statistics rather than interpolated. Interpolating a forecast",
        "   error would manufacture the exact quantity being measured.",
        "2. Hours where demand is zero or negative are dropped as impossible",
        "   per the EIA-930 form instructions.",
        "3. Balance identity failures are reported but not corrected. EIA",
        "   publishes adjusted series for this purpose; using raw values keeps",
        "   the provenance simple and the limitation visible.",
        "",
    ]

    (REPORT_DIR / "data_quality_report.md").write_text("\n".join(lines))
    print(qa.to_string(index=False))
    print("\nWrote reports/data_quality_report.md")


if __name__ == "__main__":
    main()
