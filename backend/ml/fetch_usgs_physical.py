"""
H2Open — USGS Physical Parameter Backfill
==========================================
Fetches historical daily water quality data from multiple USGS NWIS
stations on the Charles River and joins them to the CRWA and Mystic
datasets by date, filling in physical parameters that were previously NaN.

Strategy — multiple stations for spatial coverage:
  01103500  Charles River at Dover      (upper basin)
  01104500  Charles River at Waltham    (mid basin)   ← primary
  01104615  Charles River at Watertown  (lower basin)
  01104620  Charles River at Watertown  (lower basin, alt)

For each CRWA sample date, the script tries each station in priority order
and takes the first one that has data for that day. This maximises fill rate
across the 1995–2024 range where different stations may have gaps.

Parameters fetched (USGS parameter codes):
  00010  Temperature, water (°C)
  00095  Specific conductance (µS/cm) — used only for CRWA (freshwater)
  00300  Dissolved oxygen (mg/L)
  00400  pH
  63680  Turbidity (FNU ≈ NTU)

Run from backend/ml/ after build_crwa_dataset.py has completed:
    python fetch_usgs_physical.py

Outputs (both updated in place):
    crwa_with_rainfall.csv   — physical columns filled
    mystic_merged.csv        — temp, DO, pH, turbidity filled (conductance skipped)
"""

import json
import time
from pathlib import Path

import pandas as pd
import requests

# ── Config ────────────────────────────────────────────────────────────────────
CRWA_CSV   = Path("crwa_with_rainfall.csv")
MYSTIC_CSV = Path("mystic_merged.csv")
CACHE_FILE = Path("usgs_physical_cache.json")

# Charles River stations in priority order (most data → least data)
CHARLES_STATIONS = [
    ("01104500", "Charles River at Waltham"),
    ("01104615", "Charles River above Watertown Dam"),
    ("01104620", "Charles River at Watertown"),
    ("01103500", "Charles River at Dover"),
]

# Mystic River station for temp/DO/pH/turbidity (conductance excluded)
MYSTIC_STATIONS = [
    ("01102500", "Aberjona River at Winchester"),   # closest continuous monitor
]

PARAMS = {
    "00010": "temperature_c",
    "00095": "conductance_us",   # µS/cm, converted to mS/cm for Charles only
    "00300": "do_mg_l",
    "00400": "ph",
    "63680": "turbidity_ntu",
}

START_DATE = "1995-01-01"
END_DATE   = "2024-12-31"

USGS_DV_URL = "https://waterservices.usgs.gov/nwis/dv/"


# ── API fetch ─────────────────────────────────────────────────────────────────

def fetch_station(site_no: str, label: str, cache: dict) -> dict:
    """
    Fetch all daily mean values for a single USGS station.
    Returns {param_code: {date_str: value}}.
    Uses cache to avoid repeat downloads.
    """
    if site_no in cache:
        counts = {p: len(v) for p, v in cache[site_no].items()}
        print(f"  {site_no} ({label}): loaded from cache — {counts}")
        return cache[site_no]

    print(f"  Fetching {site_no} ({label})...", flush=True)
    param_str = ",".join(PARAMS.keys())

    try:
        r = requests.get(
            USGS_DV_URL,
            params={
                "format":      "json",
                "sites":       site_no,
                "parameterCd": param_str,
                "startDT":     START_DATE,
                "endDT":       END_DATE,
                "statCd":      "00003",   # daily mean
                "siteStatus":  "all",
            },
            timeout=60,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"    ERROR: {e}")
        return {}

    data   = r.json()
    result = {code: {} for code in PARAMS}

    for ts in data.get("value", {}).get("timeSeries", []):
        var_code = ts["variable"]["variableCode"][0]["value"]
        if var_code not in PARAMS:
            continue
        for v in ts.get("values", [{}])[0].get("value", []):
            date_str = v["dateTime"][:10]
            try:
                result[var_code][date_str] = float(v["value"])
            except (ValueError, TypeError):
                pass   # -999999 sentinel or null

    counts = {p: len(v) for p, v in result.items() if v}
    print(f"    Retrieved: {counts}")
    cache[site_no] = result
    time.sleep(0.5)   # be polite
    return result


def fetch_all_stations(station_list: list, cache: dict) -> dict:
    """
    Fetch all stations and merge into a single
    {param_code: {date_str: value}} dict using priority order.
    Earlier stations in the list take precedence on any given date.
    """
    merged = {code: {} for code in PARAMS}

    # Fetch in reverse priority so highest-priority overwrites at the end
    for site_no, label in reversed(station_list):
        station_data = fetch_station(site_no, label, cache)
        for code in PARAMS:
            merged[code].update(station_data.get(code, {}))

    return merged


# ── Join helpers ──────────────────────────────────────────────────────────────

def fill_physical(df: pd.DataFrame, phys: dict, include_conductance: bool) -> pd.DataFrame:
    """
    Map USGS daily values onto a DataFrame using the date_collected column.
    conductance_us is converted to mS/cm and only applied if include_conductance=True.
    """
    date_keys = pd.to_datetime(df["date_collected"]).dt.strftime("%Y-%m-%d")

    df["temperature_c"]  = date_keys.map(phys.get("00010", {}))
    df["do_mg_l"]        = date_keys.map(phys.get("00300", {}))
    df["ph"]             = date_keys.map(phys.get("00400", {}))
    df["turbidity_ntu"]  = date_keys.map(phys.get("63680", {}))

    if include_conductance:
        # USGS gives µS/cm — convert to mS/cm to match training schema
        conductance_us = date_keys.map(phys.get("00095", {}))
        df["conductance_ms"] = conductance_us / 1000.0
    # else: leave conductance_ms as NaN (already set by build_mystic_dataset.py)

    return df


def coverage_report(df: pd.DataFrame, label: str):
    n = len(df)
    print(f"\n{label} — physical fill rates after USGS join:")
    for col in ["temperature_c", "turbidity_ntu", "ph", "do_mg_l", "conductance_ms"]:
        filled = df[col].notna().sum()
        note   = " (excluded — brackish)" if col == "conductance_ms" and filled == 0 else ""
        print(f"  {col:20s}: {filled:6d} / {n} ({filled/n:.1%}){note}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Load cache
    cache = {}
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        print(f"Loaded cache with {len(cache)} station(s) already fetched.")

    # ── Charles River stations → CRWA dataset ─────────────────────────────────
    if CRWA_CSV.exists():
        print(f"\n=== Fetching Charles River stations for {CRWA_CSV} ===")
        charles_phys = fetch_all_stations(CHARLES_STATIONS, cache)

        df_crwa = pd.read_csv(CRWA_CSV)
        df_crwa = fill_physical(df_crwa, charles_phys, include_conductance=True)
        df_crwa.to_csv(CRWA_CSV, index=False)
        coverage_report(df_crwa, "CRWA")
    else:
        print(f"\nSkipping CRWA — {CRWA_CSV} not found (run build_crwa_dataset.py first)")

    # ── Mystic stations → Mystic dataset ──────────────────────────────────────
    if MYSTIC_CSV.exists():
        print(f"\n=== Fetching Mystic River station for {MYSTIC_CSV} ===")
        # Mystic already has temp/DO/pH/turbidity from the MWRA physical join,
        # but gaps exist (~20-55%). Fill those gaps with USGS where available.
        # Conductance is intentionally excluded (brackish water incompatible).
        mystic_phys = fetch_all_stations(MYSTIC_STATIONS, cache)

        df_mystic = pd.read_csv(MYSTIC_CSV)

        # Only fill NaN cells — don't overwrite real MWRA readings
        date_keys = pd.to_datetime(df_mystic["date_collected"]).dt.strftime("%Y-%m-%d")
        for param_code, col in [
            ("00010", "temperature_c"),
            ("00300", "do_mg_l"),
            ("00400", "ph"),
            ("63680", "turbidity_ntu"),
        ]:
            usgs_vals = date_keys.map(mystic_phys.get(param_code, {}))
            df_mystic[col] = df_mystic[col].fillna(usgs_vals)

        df_mystic.to_csv(MYSTIC_CSV, index=False)
        coverage_report(df_mystic, "Mystic")
    else:
        print(f"\nSkipping Mystic — {MYSTIC_CSV} not found (run build_mystic_dataset.py first)")

    # Save updated cache
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)
    print(f"\nCache saved: {CACHE_FILE}")
    print("\nNext step: python train_v2.py --crwa --mystic")


if __name__ == "__main__":
    main()