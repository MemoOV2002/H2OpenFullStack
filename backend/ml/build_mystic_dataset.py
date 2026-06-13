"""
H2Open — Mystic River Dataset Builder
=======================================
Merges Mystic River bacteria + physical data from MWRA into a CSV
ready to be combined with the MWRA Charles River and CRWA datasets
in train_v2.py.

Key decision: conductance is intentionally EXCLUDED because the
Mystic River is brackish (avg 7.9 PSU salinity) and its conductance
values are incompatible with the freshwater Charles River buoy readings.
All other physical parameters (temp, turbidity, pH, DO) are valid
across both environments and are included.

Run from backend/ml/:
    python build_mystic_dataset.py

Input files (place in backend/ml/):
    mr_bacteria.xlsx
    mr_physical.xlsx

Output:
    mystic_merged.csv
"""

from pathlib import Path
import numpy as np
import pandas as pd

BACT_FILE = Path("mr_bacteria.xlsx")
PHYS_FILE = Path("mr_physical.xlsx")
OUT_CSV   = Path("mystic_merged.csv")


def load_and_merge() -> pd.DataFrame:
    print("Loading Mystic River bacteria data...")
    bact = pd.read_excel(BACT_FILE, sheet_name="Mystic Bacteria all yrs", header=5)

    print("Loading Mystic River physical data...")
    phys = pd.read_excel(PHYS_FILE, sheet_name="Mystic Physical Data all yrs ", header=5)

    # Normalise join keys
    bact["date_only"] = pd.to_datetime(bact["Date/time (EASTERN STANDARD TIME)"]).dt.date
    phys["date_only"] = pd.to_datetime(phys["Date/time (EASTERN STANDARD TIME)"]).dt.date
    bact["Station ID"] = bact["Station ID"].astype(str)
    phys["Station ID"] = phys["Station ID"].astype(str)

    # Surface samples with measured E. coli only
    bact = bact[
        bact["E. coli (#/100mL)"].notna() &
        (bact["Surface or Bottom"] == "S")
    ].copy()
    phys = phys[phys["Surface or Bottom"] == "S"].copy()

    # Join physical — intentionally exclude Specific Conductance
    merged = bact.merge(
        phys[[
            "Station ID", "date_only",
            "Temperature (C)",
            "Dissolved Oxygen (mg/L)",
            "pH",
            "Turbidity (NTU)",
        ]],
        on=["Station ID", "date_only"],
        how="left",
    )
    print(f"  Merged rows: {len(merged)}")
    return merged


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()

    # Physical parameters — conductance left as NaN (incompatible water type)
    out["turbidity_ntu"]  = df["Turbidity (NTU)"]
    out["temperature_c"]  = df["Temperature (C)"]
    out["conductance_ms"] = np.nan          # excluded — brackish water
    out["ph"]             = df["pH"]
    out["do_mg_l"]        = df["Dissolved Oxygen (mg/L)"]

    # Rainfall lags — already in bacteria sheet from Logan Airport
    rain_d0 = df["Logan Rainfall (current day), in."].fillna(0)
    rain_2d = df["Logan Rainfall (current day + previous day), in."].fillna(0)
    rain_3d = df["Logan Rainfall (current day + previous 2 days), in."].fillna(0)

    out["rain_day0_in"]  = rain_d0
    out["rain_lag1_in"]  = (rain_2d - rain_d0).clip(lower=0)
    out["rain_lag2_in"]  = (rain_3d - rain_2d).clip(lower=0)
    out["rain_3day_cum"] = rain_3d

    # Temporal features
    dt = pd.to_datetime(df["Date/time (EASTERN STANDARD TIME)"])
    out["month"]   = dt.dt.month
    out["doy_sin"] = np.sin(2 * np.pi * dt.dt.dayofyear / 365)
    out["doy_cos"] = np.cos(2 * np.pi * dt.dt.dayofyear / 365)
    out["hour"]    = dt.dt.hour.fillna(10)

    out["station_id"]     = pd.to_numeric(df["Station ID"], errors="coerce").fillna(-1)
    out["ecoli_cfu"]      = df["E. coli (#/100mL)"].values
    out["date_collected"] = pd.to_datetime(df["Date/time (EASTERN STANDARD TIME)"])
    out["source"]         = "mystic"

    return out


def main():
    for f in [BACT_FILE, PHYS_FILE]:
        if not f.exists():
            print(f"ERROR: {f} not found. Place it in backend/ml/ and retry.")
            raise SystemExit(1)

    merged = load_and_merge()
    out    = build_features(merged)

    out.to_csv(OUT_CSV, index=False)

    print(f"\nSaved {len(out)} rows → {OUT_CSV}")
    print(f"Unsafe rate (>235 CFU): {(out['ecoli_cfu'] > 235).mean():.1%}")
    print("\nPhysical parameter fill rates:")
    for col in ["temperature_c", "turbidity_ntu", "ph", "do_mg_l"]:
        filled = out[col].notna().sum()
        print(f"  {col:20s}: {filled:5d} / {len(out)} ({filled/len(out):.1%})")
    print(f"  {'conductance_ms':20s}: excluded (brackish water — imputed at inference)")
    print("\nNext step: python train_v2.py --crwa --mystic")


if __name__ == "__main__":
    main()