"""
01_pull.py
Pull hourly EIA-930 grid operations data for eight U.S. balancing authorities.

Source: U.S. Energy Information Administration, API v2, Form EIA-930.
Writes one parquet file per balancing authority per dataset to data/raw/.

Run:  python src/01_pull.py
"""

import os
import time
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import requests
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

# ----------------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------------

load_dotenv()
API_KEY = os.getenv("EIA_API_KEY")
if not API_KEY:
    sys.exit("ERROR: no EIA_API_KEY in .env")

BASE_URL = "https://api.eia.gov/v2/"
PAGE_SIZE = 5000          # EIA maximum per request
MAX_RETRIES = 4
BACKOFF_SECONDS = 2       # doubles each retry
POLITE_DELAY = 0.25       # seconds between successful requests

RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

# The manifest lives in reports/, not data/raw/, so the provenance record is
# committed to the repo even though the raw parquet it describes is not.
MANIFEST_PATH = Path("reports/pull_manifest.csv")
MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

# Eight balancing authorities. See Part 4.5 of the build guide.
RESPONDENTS = ["PJM", "MISO", "CISO", "ERCO", "ISNE", "NYIS", "SWPP", "SOCO"]

# Region data type codes: demand, day-ahead forecast, net generation, interchange
REGION_TYPES = ["D", "DF", "NG", "TI"]

# 24 month window ending at the start of the current month.
# EIA data lags by a day or two, so we never ask for the current month.
# timezone.utc keeps these timezone-aware; datetime.utcnow() is deprecated
# and prints a warning on Python 3.12+.
_today = datetime.now(timezone.utc)
END_DT = datetime(_today.year, _today.month, 1, tzinfo=timezone.utc)
START_DT = END_DT - timedelta(days=730)

START = START_DT.strftime("%Y-%m-%dT%H")
END = END_DT.strftime("%Y-%m-%dT%H")

print(f"Pull window: {START} to {END} (UTC)")


# ----------------------------------------------------------------------------
# CORE FETCH LOGIC
# ----------------------------------------------------------------------------

def fetch_page(route, base_params, offset):
    """Fetch a single page with retry and exponential backoff."""
    params = list(base_params) + [("offset", offset), ("length", PAGE_SIZE)]
    url = BASE_URL + route

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=60)

            if resp.status_code == 200:
                payload = resp.json()
                if "response" not in payload:
                    raise ValueError(f"Malformed payload: {str(payload)[:300]}")
                return payload["response"]

            # 429 is rate limiting, 5xx is server side. Both are worth retrying.
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = BACKOFF_SECONDS * (2 ** attempt)
                print(f"  HTTP {resp.status_code}, retrying in {wait}s")
                time.sleep(wait)
                continue

            # 403 or 404 will not fix itself. Fail loudly.
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")

        except requests.exceptions.RequestException as exc:
            wait = BACKOFF_SECONDS * (2 ** attempt)
            print(f"  Network error ({exc}), retrying in {wait}s")
            time.sleep(wait)

    raise RuntimeError(f"Failed after {MAX_RETRIES} attempts: {route} offset {offset}")


def fetch_all(route, base_params, label):
    """Page through an entire result set and return a DataFrame."""
    first = fetch_page(route, base_params, offset=0)
    total = int(first.get("total", 0))

    if total == 0:
        print(f"  WARNING: {label} returned zero rows")
        return pd.DataFrame()

    rows = list(first["data"])
    n_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE

    for page in tqdm(range(1, n_pages), desc=f"  {label}", unit="page", leave=False):
        time.sleep(POLITE_DELAY)
        chunk = fetch_page(route, base_params, offset=page * PAGE_SIZE)
        rows.extend(chunk["data"])

    df = pd.DataFrame(rows)
    print(f"  {label}: {len(df):,} rows (API reported {total:,})")

    if len(df) != total:
        print(f"  WARNING: row count mismatch for {label}")

    return df


# ----------------------------------------------------------------------------
# DATASET BUILDERS
# ----------------------------------------------------------------------------

def pull_region_data(respondent):
    """Demand, forecast, net generation and interchange for one BA."""
    params = [
        ("api_key", API_KEY),
        ("frequency", "hourly"),
        ("data[0]", "value"),
        ("facets[respondent][]", respondent),
        ("start", START),
        ("end", END),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "asc"),
    ]
    for t in REGION_TYPES:
        params.append(("facets[type][]", t))

    return fetch_all("electricity/rto/region-data/data/", params, f"{respondent} region")


def pull_fuel_data(respondent):
    """Net generation by fuel type for one BA."""
    params = [
        ("api_key", API_KEY),
        ("frequency", "hourly"),
        ("data[0]", "value"),
        ("facets[respondent][]", respondent),
        ("start", START),
        ("end", END),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "asc"),
    ]
    return fetch_all("electricity/rto/fuel-type-data/data/", params, f"{respondent} fuel")


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------

def main():
    started = time.time()
    manifest = []

    for ba in RESPONDENTS:
        print(f"\n=== {ba} ===")

        region = pull_region_data(ba)
        if not region.empty:
            path = RAW_DIR / f"region_{ba}.parquet"
            region.to_parquet(path, index=False)
            manifest.append({"ba": ba, "dataset": "region", "rows": len(region)})

        fuel = pull_fuel_data(ba)
        if not fuel.empty:
            path = RAW_DIR / f"fuel_{ba}.parquet"
            fuel.to_parquet(path, index=False)
            manifest.append({"ba": ba, "dataset": "fuel", "rows": len(fuel)})

    # A manifest is how you prove later what you actually pulled and when.
    mf = pd.DataFrame(manifest)
    mf["pulled_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    mf["window_start"] = START
    mf["window_end"] = END
    mf.to_csv(MANIFEST_PATH, index=False)

    elapsed = time.time() - started
    print(f"\n{'='*60}")
    print(f"DONE in {elapsed/60:.1f} minutes")
    print(f"Total rows: {mf['rows'].sum():,}")
    print(mf.groupby('dataset')['rows'].sum().to_string())
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
