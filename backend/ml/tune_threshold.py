"""
H2Open — Inference Threshold Tuning
=====================================
Loads the trained model, reconstructs the exact test set used during
training, and evaluates FNR/FPR across a range of CFU thresholds.

The threshold is applied to the UPPER CI (not the point estimate).
Lowering it below 235 CFU trades more false alarms for fewer missed
unsafe readings — the right tradeoff for a public swim advisory.

Run from backend/ml/:
    python tune_threshold.py

Prints a table and saves the recommended threshold to threshold.json
so ecoli_predictor.py can load it instead of hardcoding 235.
"""

import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

warnings.filterwarnings("ignore", category=UserWarning)

MODEL_PATH  = Path("ecoli_model_v2.joblib")
MAPIE_PATH  = Path("ecoli_mapie_v2.joblib")
META_PATH   = Path("ecoli_meta_v2.joblib")
BACT_FILE   = Path("cr_bacteria.xlsx")
PHYS_FILE   = Path("cr_physical.xlsx")
CRWA_FILE   = Path("crwa_with_rainfall.csv")
OUT_JSON    = Path("threshold.json")

EPA_THRESHOLD = 235.0


# ── Rebuild the same dataset used for training ────────────────────────────────

def load_mwra_features() -> pd.DataFrame:
    bact = pd.read_excel(BACT_FILE, sheet_name="MWRA Charles Bacteria all yrs", header=5)
    phys = pd.read_excel(PHYS_FILE, sheet_name="MWRA Physical Data all yrs", header=5)

    bact["date_only"] = pd.to_datetime(bact["Date/time (EASTERN STANDARD TIME)"]).dt.date
    phys["date_only"] = pd.to_datetime(phys["Date/time (EASTERN STANDARD TIME)"]).dt.date
    bact["Station ID"] = bact["Station ID"].astype(str)
    phys["Station ID"] = phys["Station ID"].astype(str)

    bact = bact[bact["E. coli (#/100mL)"].notna() & (bact["Surface or Bottom"] == "S")].copy()
    phys = phys[phys["Surface or Bottom"] == "S"].copy()

    merged = bact.merge(
        phys[["Station ID", "date_only", "Temperature (C)",
              "Specific Conductance (mS/cm)", "Dissolved Oxygen (mg/L)",
              "pH", "Turbidity (NTU)"]],
        on=["Station ID", "date_only"], how="left"
    )

    feat = pd.DataFrame()
    feat["turbidity_ntu"]  = merged["Turbidity (NTU)"]
    feat["temperature_c"]  = merged["Temperature (C)"]
    feat["conductance_ms"] = merged["Specific Conductance (mS/cm)"]
    feat["ph"]             = merged["pH"]
    feat["do_mg_l"]        = merged["Dissolved Oxygen (mg/L)"]

    rain_d0 = merged["Logan Rainfall (current day), in."].fillna(0)
    rain_2d = merged["Logan Rainfall (current day + previous day), in."].fillna(0)
    rain_3d = merged["Logan Rainfall (current day + previous 2 days), in."].fillna(0)

    feat["rain_day0_in"]  = rain_d0
    feat["rain_lag1_in"]  = (rain_2d - rain_d0).clip(lower=0)
    feat["rain_lag2_in"]  = (rain_3d - rain_2d).clip(lower=0)
    feat["rain_3day_cum"] = rain_3d

    dt = pd.to_datetime(merged["Date/time (EASTERN STANDARD TIME)"])
    feat["month"]   = dt.dt.month
    feat["doy_sin"] = np.sin(2 * np.pi * dt.dt.dayofyear / 365)
    feat["doy_cos"] = np.cos(2 * np.pi * dt.dt.dayofyear / 365)
    feat["station_id"] = pd.to_numeric(merged["Station ID"], errors="coerce").fillna(-1)
    feat["ecoli_cfu"]  = merged["E. coli (#/100mL)"].values
    return feat


def load_crwa_features() -> pd.DataFrame:
    df = pd.read_csv(CRWA_FILE)
    feat = pd.DataFrame()
    feat["turbidity_ntu"]  = df["turbidity_ntu"]
    feat["temperature_c"]  = df["temperature_c"]
    feat["conductance_ms"] = df["conductance_ms"]
    feat["ph"]             = df["ph"]
    feat["do_mg_l"]        = df["do_mg_l"]
    feat["rain_day0_in"]   = df["rain_day0_in"]
    feat["rain_lag1_in"]   = df["rain_lag1_in"]
    feat["rain_lag2_in"]   = df["rain_lag2_in"]
    feat["rain_3day_cum"]  = df["rain_3day_cum"]

    dt = pd.to_datetime(df["date_collected"])
    feat["month"]      = dt.dt.month
    feat["doy_sin"]    = np.sin(2 * np.pi * dt.dt.dayofyear / 365)
    feat["doy_cos"]    = np.cos(2 * np.pi * dt.dt.dayofyear / 365)
    feat["station_id"] = df["station_id"].fillna(-1)
    feat["ecoli_cfu"]  = df["ecoli_cfu"].values
    return feat


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Loading model artifacts...")
    mapie = joblib.load(MAPIE_PATH)
    meta  = joblib.load(META_PATH)
    feature_names = meta["feature_names"]

    print("Rebuilding dataset...")
    mwra = load_mwra_features()
    pieces = [mwra]
    if CRWA_FILE.exists():
        pieces.append(load_crwa_features())
    combined = pd.concat(pieces, ignore_index=True)

    X = combined[feature_names].copy()
    y = np.log1p(combined["ecoli_cfu"])

    # Reproduce the exact same split as train_v2.py
    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42
    )
    X_train, X_cal, y_train, y_cal = train_test_split(
        X_temp, y_temp, test_size=0.25, random_state=42
    )

    print(f"Test set: {len(X_test)} rows  |  "
          f"unsafe rate: {(np.expm1(y_test) > EPA_THRESHOLD).mean():.1%}")

    # Get conformal intervals on test set
    print("Running conformal prediction on test set...")
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore")
        _, y_pi = mapie.predict_interval(X_test)

    y_hi_cfu   = np.expm1(y_pi[:, 1, 0]).clip(min=0)   # upper CI in CFU
    y_true_cfu = np.expm1(y_test.values)
    unsafe_true = y_true_cfu > EPA_THRESHOLD

    # Sweep thresholds
    thresholds = [50, 75, 100, 125, 150, 175, 200, 215, 225, 235, 250, 275, 300]

    print(f"\n{'Threshold':>10} {'FNR':>7} {'FPR':>7} {'TP':>6} {'FN':>6} {'FP':>6} {'TN':>6}")
    print("-" * 60)

    results = []
    for t in thresholds:
        unsafe_flag = y_hi_cfu > t
        tp = int(( unsafe_true &  unsafe_flag).sum())
        fn = int(( unsafe_true & ~unsafe_flag).sum())
        fp = int((~unsafe_true &  unsafe_flag).sum())
        tn = int((~unsafe_true & ~unsafe_flag).sum())
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
        marker = " ← EPA standard" if t == 235 else ""
        print(f"{t:>10}  {fnr:>6.1%}  {fpr:>6.1%}  {tp:>6}  {fn:>6}  {fp:>6}  {tn:>6}{marker}")
        results.append({"threshold": t, "fnr": fnr, "fpr": fpr,
                        "tp": tp, "fn": fn, "fp": fp, "tn": tn})

    # Pick recommended threshold: lowest FNR where FPR < 80%
    candidates = [r for r in results if r["fpr"] < 0.80]
    recommended = min(candidates, key=lambda r: r["fnr"]) if candidates else results[0]

    print(f"\nRecommended threshold: {recommended['threshold']} CFU")
    print(f"  FNR = {recommended['fnr']:.1%}  FPR = {recommended['fpr']:.1%}")
    print(f"  Missed unsafe readings: {recommended['fn']} / {recommended['fn']+recommended['tp']}")

    # Save so ecoli_predictor.py can load it
    out = {
        "inference_threshold_cfu": recommended["threshold"],
        "epa_threshold_cfu":       EPA_THRESHOLD,
        "fnr":                     recommended["fnr"],
        "fpr":                     recommended["fpr"],
        "sweep":                   results,
    }
    with open(OUT_JSON, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved → {OUT_JSON}")
    print("\nUpdate ecoli_predictor.py to load this threshold instead of hardcoding 235.")


if __name__ == "__main__":
    main()