"""
H2Open — Fill CRWA Physical Parameters from MWRA Data
=======================================================
The USGS stations on the Charles River don't have continuous water quality
monitoring going back to 1995, so we fall back to the MWRA physical dataset
(cr_physical.xlsx) which has excellent coverage.

Strategy: nearest-date join with a 14-day tolerance.
For each CRWA sample date, find the closest MWRA sampling day and
use its basin-wide daily mean physical readings. MWRA samples ~2x/month
so the worst case gap is ~7 days, which is acceptable for slow-changing
parameters like temperature and conductance.

Run from backend/ml/:
    python fill_crwa_physical.py

Updates crwa_with_rainfall.csv in place.
"""

from pathlib import Path
import numpy as np
import pandas as pd

CRWA_CSV  = Path("crwa_with_rainfall.csv")
PHYS_FILE = Path("cr_physical.xlsx")
MAX_DAYS  = 14   # maximum allowed gap for nearest-date match


def load_mwra_daily() -> pd.DataFrame:
    """Load MWRA physical data and compute daily basin-wide averages."""
    print("Loading MWRA physical data...")
    phys = pd.read_excel(
        PHYS_FILE,
        sheet_name="MWRA Physical Data all yrs",
        header=5
    )
    phys["date_only"] = pd.to_datetime(
        phys["Date/time (EASTERN STANDARD TIME)"]
    ).dt.date
    phys = phys[phys["Surface or Bottom"] == "S"]

    daily = phys.groupby("date_only").agg(
        temperature_c  = ("Temperature (C)",              "mean"),
        conductance_ms = ("Specific Conductance (mS/cm)", "mean"),
        do_mg_l        = ("Dissolved Oxygen (mg/L)",      "mean"),
        ph             = ("pH",                           "mean"),
        turbidity_ntu  = ("Turbidity (NTU)",              "mean"),
    ).reset_index()

    print(f"  MWRA sampling days: {len(daily)}")
    print(f"  Date range: {daily['date_only'].min()} → {daily['date_only'].max()}")
    return daily


def nearest_date_join(
    crwa_dates: pd.Series,
    mwra_daily: pd.DataFrame,
    max_days: int,
) -> pd.DataFrame:
    """
    For each CRWA date, find the nearest MWRA sampling date within max_days.
    Returns a DataFrame aligned to crwa_dates with physical columns filled.
    """
    mwra_dates = pd.to_datetime(mwra_daily["date_only"]).dt.as_unit("s")
    crwa_dt    = pd.to_datetime(crwa_dates).dt.as_unit("s")

    # Use merge_asof for efficient nearest-date matching
    crwa_df = pd.DataFrame({"date": crwa_dt}).sort_values("date")
    mwra_df = mwra_daily.copy()
    mwra_df["date"] = mwra_dates

    merged = pd.merge_asof(
        crwa_df,
        mwra_df.sort_values("date"),
        on="date",
        direction="nearest",
        tolerance=pd.Timedelta(days=max_days),
    )

    # Restore original row order
    merged.index = crwa_df.index
    return merged.reindex(crwa_dates.index)


def main():
    if not CRWA_CSV.exists():
        print(f"ERROR: {CRWA_CSV} not found. Run build_crwa_dataset.py first.")
        raise SystemExit(1)
    if not PHYS_FILE.exists():
        print(f"ERROR: {PHYS_FILE} not found. Place cr_physical.xlsx in backend/ml/")
        raise SystemExit(1)

    mwra_daily = load_mwra_daily()

    print(f"\nLoading {CRWA_CSV}...")
    crwa = pd.read_csv(CRWA_CSV)
    n    = len(crwa)
    print(f"  {n} CRWA rows")

    print(f"\nRunning nearest-date join (tolerance: {MAX_DAYS} days)...")
    filled = nearest_date_join(
        crwa["date_collected"],
        mwra_daily,
        MAX_DAYS,
    )

    # Only fill NaN cells — don't overwrite any existing values
    for col in ["temperature_c", "conductance_ms", "do_mg_l", "ph", "turbidity_ntu"]:
        crwa[col] = crwa[col].combine_first(pd.Series(filled[col].values, index=crwa.index))

    crwa.to_csv(CRWA_CSV, index=False)

    print(f"\nFill rates after nearest-date join:")
    for col in ["temperature_c", "conductance_ms", "do_mg_l", "ph", "turbidity_ntu"]:
        filled_n = crwa[col].notna().sum()
        print(f"  {col:20s}: {filled_n:6d} / {n} ({filled_n/n:.1%})")

    print(f"\nUpdated {CRWA_CSV}")
    print("Next step: python train_v2.py --crwa --mystic")


if __name__ == "__main__":
    main()