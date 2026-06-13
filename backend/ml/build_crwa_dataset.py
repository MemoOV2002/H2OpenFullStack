"""
H2Open — CRWA Rainfall Backfill
=================================
Reads the CRWA E. coli CSV, fetches historical rainfall from Open-Meteo
for every sample date (Logan Airport coords), and saves a merged CSV
ready to be combined with the MWRA dataset in train_v2.py.

Run once from backend/ml/:
    python build_crwa_dataset.py

Output: crwa_with_rainfall.csv  (in the same ml/ directory)

Open-Meteo archive API:
  - Free, no API key needed
  - One request per year-chunk to avoid rate limits
  - Results cached locally in rainfall_cache.json so re-runs are fast
"""

import json
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# ── Config ────────────────────────────────────────────────────────────────────
CRWA_CSV    = Path("crwa_ecoli.csv")   # rename if needed
OUT_CSV     = Path("crwa_with_rainfall.csv")
CACHE_FILE  = Path("rainfall_cache.json")

# Logan Airport — matches the MWRA training data rainfall source
LAT = 42.3656
LON = -71.0096

OPENMETEO_URL = "https://archive-api.open-meteo.com/v1/archive"


# ── Rainfall fetching ─────────────────────────────────────────────────────────

def load_cache() -> dict:
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)


def fetch_year(year: int, cache: dict) -> dict:
    """
    Fetch full year of daily precipitation from Open-Meteo.
    Returns {date_str: inches} for every day in that year.
    Reads from cache if already fetched.
    """
    key = str(year)
    if key in cache:
        return cache[key]

    start = f"{year}-01-01"
    end   = f"{year}-12-31"

    print(f"  Fetching {year} from Open-Meteo...", end=" ", flush=True)
    try:
        r = requests.get(
            OPENMETEO_URL,
            params={
                "latitude":            LAT,
                "longitude":           LON,
                "start_date":          start,
                "end_date":            end,
                "daily":               "precipitation_sum",
                "timezone":            "America/New_York",
                "precipitation_unit":  "inch",
            },
            timeout=30,
        )
        r.raise_for_status()
        data  = r.json()
        dates = data["daily"]["time"]
        precip = data["daily"]["precipitation_sum"]
        year_data = {d: (p if p is not None else 0.0) for d, p in zip(dates, precip)}
        cache[key] = year_data
        save_cache(cache)
        print(f"done ({len(year_data)} days)")
        time.sleep(0.5)   # be polite to the API
        return year_data
    except Exception as e:
        print(f"FAILED: {e}")
        return {}


def build_rain_map(years: list[int]) -> dict:
    """Fetch all required years and return a single date→inches dict."""
    cache    = load_cache()
    rain_map = {}
    for year in years:
        year_data = fetch_year(year, cache)
        rain_map.update(year_data)
    return rain_map


def get_lags(sample_date: date, rain_map: dict) -> dict:
    """
    Compute the same rainfall lag features used in train_v2.py.
    Matches the MWRA Logan Airport columns exactly.
    """
    def r(d: date) -> float:
        return rain_map.get(d.isoformat(), 0.0)

    r0 = r(sample_date)
    r1 = r(sample_date - timedelta(days=1))
    r2 = r(sample_date - timedelta(days=2))

    return {
        "rain_day0_in":  round(r0, 3),
        "rain_lag1_in":  round(r1, 3),
        "rain_lag2_in":  round(r2, 3),
        "rain_3day_cum": round(r0 + r1 + r2, 3),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Loading CRWA CSV...")
    df = pd.read_csv(CRWA_CSV)
    print(f"  {len(df)} rows, {df['Site_ID'].nunique()} sites")

    # Parse dates
    df["date_only"] = pd.to_datetime(df["Date_Collected"]).dt.date
    years = sorted(set(d.year for d in df["date_only"]))
    print(f"  Date range: {min(years)}–{max(years)} ({len(years)} years)")

    # Fetch rainfall for all years
    print(f"\nFetching rainfall from Open-Meteo ({len(years)} years)...")
    rain_map = build_rain_map(years)
    print(f"  Total days in rain map: {len(rain_map)}")

    # Build lag features for each row
    print("\nComputing rainfall lag features...")
    lag_records = [get_lags(d, rain_map) for d in df["date_only"]]
    lag_df = pd.DataFrame(lag_records)

    # Assemble output dataframe with column names matching train_v2.py
    out = pd.DataFrame()
    out["ecoli_cfu"]       = df["Reporting_Result"].astype(float)
    out["date_collected"]  = pd.to_datetime(df["Date_Collected"])
    out["station_id"]      = pd.to_numeric(
        df["Site_ID"].str.extract(r"(\d+)")[0], errors="coerce"
    ).fillna(-1).astype(int)

    # Physical parameters — not in CRWA data, leave as NaN for imputation
    out["turbidity_ntu"]  = np.nan
    out["temperature_c"]  = np.nan
    out["conductance_ms"] = np.nan   # mS/cm
    out["ph"]             = np.nan
    out["do_mg_l"]        = np.nan

    # Rainfall features
    out["rain_day0_in"]  = lag_df["rain_day0_in"].values
    out["rain_lag1_in"]  = lag_df["rain_lag1_in"].values
    out["rain_lag2_in"]  = lag_df["rain_lag2_in"].values
    out["rain_3day_cum"] = lag_df["rain_3day_cum"].values

    # Source tag so we can inspect mix after merging
    out["source"] = "crwa"

    out.to_csv(OUT_CSV, index=False)
    print(f"\nSaved {len(out)} rows → {OUT_CSV}")
    print(f"Unsafe rate (>235 CFU): {(out['ecoli_cfu'] > 235).mean():.1%}")
    print("\nDone. Next step: run python train_v2.py")


if __name__ == "__main__":
    main()