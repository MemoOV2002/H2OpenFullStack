"""
H2Open — E. coli Regression Model v2
=====================================
Switches from classification to regression (predict CFU directly).
Threshold comparison (235 CFU) happens outside the model.

Key changes from v1:
  - Regression target: log1p(E. coli CFU)
  - Model: LightGBM Regressor
  - Uncertainty Quantification: MAPIE conformal prediction
  - Feature selection: permutation importance + optional pruning
  - FNR control: upper CI bound compared against threshold
  - Optional datasets: CRWA (--crwa) and Mystic River (--mystic)

Usage:
    python train_v2.py                             # MWRA Charles River only
    python train_v2.py --crwa                      # + CRWA dataset
    python train_v2.py --crwa --mystic             # + CRWA + Mystic River
    python train_v2.py --crwa --mystic --prune-features
    python train_v2.py --coverage 0.90
"""

import argparse
import warnings
import joblib
import numpy as np
import pandas as pd
from pathlib import Path

from sklearn.model_selection import train_test_split
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
import lightgbm as lgb
from mapie.regression import SplitConformalRegressor

warnings.filterwarnings("ignore", category=UserWarning)

# ─── Paths ────────────────────────────────────────────────────────────────────
BACT_FILE    = Path("cr_bacteria.xlsx")
PHYS_FILE    = Path("cr_physical.xlsx")
CRWA_FILE    = Path("crwa_with_rainfall.csv")     # from build_crwa_dataset.py
MYSTIC_FILE  = Path("mystic_merged.csv")           # from build_mystic_dataset.py
MODEL_OUT    = Path("ecoli_model_v2.joblib")
MAPIE_OUT    = Path("ecoli_mapie_v2.joblib")
META_OUT     = Path("ecoli_meta_v2.joblib")

EPA_THRESHOLD = 235.0

FEATURE_COLS = [
    "turbidity_ntu", "temperature_c", "conductance_ms", "ph", "do_mg_l",
    "rain_day0_in", "rain_lag1_in", "rain_lag2_in", "rain_3day_cum",
    "month", "doy_sin", "doy_cos", "station_id",
]


# ─── 1. Load MWRA Charles River data ─────────────────────────────────────────
def load_mwra() -> pd.DataFrame:
    print("Loading MWRA Charles River bacteria data...")
    bact = pd.read_excel(BACT_FILE, sheet_name="MWRA Charles Bacteria all yrs", header=5)
    print("Loading MWRA Charles River physical data...")
    phys = pd.read_excel(PHYS_FILE, sheet_name="MWRA Physical Data all yrs", header=5)

    bact["date_only"] = pd.to_datetime(bact["Date/time (EASTERN STANDARD TIME)"]).dt.date
    phys["date_only"] = pd.to_datetime(phys["Date/time (EASTERN STANDARD TIME)"]).dt.date
    bact["Station ID"] = bact["Station ID"].astype(str)
    phys["Station ID"] = phys["Station ID"].astype(str)

    bact = bact[bact["E. coli (#/100mL)"].notna() & (bact["Surface or Bottom"] == "S")].copy()
    phys = phys[phys["Surface or Bottom"] == "S"].copy()

    merged = bact.merge(
        phys[[
            "Station ID", "date_only",
            "Temperature (C)", "Specific Conductance (mS/cm)",
            "Dissolved Oxygen (mg/L)", "pH", "Turbidity (NTU)"
        ]],
        on=["Station ID", "date_only"],
        how="left"
    )
    print(f"  MWRA rows: {len(merged)}")
    return merged


# ─── 2. Feature builders ──────────────────────────────────────────────────────
def build_features_mwra(df: pd.DataFrame) -> pd.DataFrame:
    feat = pd.DataFrame()
    feat["turbidity_ntu"]  = df["Turbidity (NTU)"]
    feat["temperature_c"]  = df["Temperature (C)"]
    feat["conductance_ms"] = df["Specific Conductance (mS/cm)"]
    feat["ph"]             = df["pH"]
    feat["do_mg_l"]        = df["Dissolved Oxygen (mg/L)"]

    rain_d0 = df["Logan Rainfall (current day), in."].fillna(0)
    rain_2d = df["Logan Rainfall (current day + previous day), in."].fillna(0)
    rain_3d = df["Logan Rainfall (current day + previous 2 days), in."].fillna(0)

    feat["rain_day0_in"]  = rain_d0
    feat["rain_lag1_in"]  = (rain_2d - rain_d0).clip(lower=0)
    feat["rain_lag2_in"]  = (rain_3d - rain_2d).clip(lower=0)
    feat["rain_3day_cum"] = rain_3d

    dt = pd.to_datetime(df["Date/time (EASTERN STANDARD TIME)"])
    feat["month"]   = dt.dt.month
    feat["doy_sin"] = np.sin(2 * np.pi * dt.dt.dayofyear / 365)
    feat["doy_cos"] = np.cos(2 * np.pi * dt.dt.dayofyear / 365)
    feat["hour"]    = dt.dt.hour.fillna(10)

    feat["station_id"] = pd.to_numeric(df["Station ID"], errors="coerce").fillna(-1)
    feat["ecoli_cfu"]  = df["E. coli (#/100mL)"].values
    feat["source"]     = "mwra"
    return feat


def build_features_from_csv(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """
    Generic builder for pre-processed CSVs (CRWA and Mystic).
    Both have the same column schema output by their respective build scripts.
    """
    feat = pd.DataFrame()
    feat["turbidity_ntu"]  = df["turbidity_ntu"]
    feat["temperature_c"]  = df["temperature_c"]
    feat["conductance_ms"] = df["conductance_ms"]   # NaN for Mystic (brackish)
    feat["ph"]             = df["ph"]
    feat["do_mg_l"]        = df["do_mg_l"]

    feat["rain_day0_in"]  = df["rain_day0_in"]
    feat["rain_lag1_in"]  = df["rain_lag1_in"]
    feat["rain_lag2_in"]  = df["rain_lag2_in"]
    feat["rain_3day_cum"] = df["rain_3day_cum"]

    dt = pd.to_datetime(df["date_collected"])
    feat["month"]   = dt.dt.month
    feat["doy_sin"] = np.sin(2 * np.pi * dt.dt.dayofyear / 365)
    feat["doy_cos"] = np.cos(2 * np.pi * dt.dt.dayofyear / 365)
    feat["hour"]    = dt.dt.hour.fillna(10)

    feat["station_id"] = df["station_id"].fillna(-1)
    feat["ecoli_cfu"]  = df["ecoli_cfu"].values
    feat["source"]     = source_name
    return feat


# ─── 3. Load & merge datasets ─────────────────────────────────────────────────
def load_data(use_crwa: bool, use_mystic: bool) -> tuple[pd.DataFrame, pd.Series]:
    mwra_feat = build_features_mwra(load_mwra())
    pieces    = [mwra_feat]

    if use_crwa:
        if not CRWA_FILE.exists():
            print(f"\nERROR: {CRWA_FILE} not found. Run build_crwa_dataset.py first.\n")
            raise SystemExit(1)
        print("Loading CRWA data...")
        crwa_feat = build_features_from_csv(pd.read_csv(CRWA_FILE), "crwa")
        print(f"  CRWA rows: {len(crwa_feat)}")
        pieces.append(crwa_feat)

    if use_mystic:
        if not MYSTIC_FILE.exists():
            print(f"\nERROR: {MYSTIC_FILE} not found. Run build_mystic_dataset.py first.\n")
            raise SystemExit(1)
        print("Loading Mystic River data...")
        mystic_feat = build_features_from_csv(pd.read_csv(MYSTIC_FILE), "mystic")
        print(f"  Mystic rows: {len(mystic_feat)}")
        pieces.append(mystic_feat)

    combined = pd.concat(pieces, ignore_index=True)

    print(f"\nCombined dataset: {len(combined)} rows")
    for src in combined["source"].unique():
        n = (combined["source"] == src).sum()
        unsafe = (combined.loc[combined["source"]==src, "ecoli_cfu"] > 235).mean()
        print(f"  {src:8s}: {n:6d} rows | unsafe rate: {unsafe:.1%}")

    X = combined[FEATURE_COLS].copy()
    y = np.log1p(combined["ecoli_cfu"])
    return X, y


# ─── 4. Feature importance & optional pruning ─────────────────────────────────
def evaluate_feature_importance(model_pipeline, X_val, y_val, feature_names):
    print("\n--- Permutation Feature Importance (validation set) ---")
    result = permutation_importance(
        model_pipeline, X_val, y_val,
        n_repeats=15, random_state=42, n_jobs=-1,
        scoring="neg_mean_squared_error"
    )
    imp_df = pd.DataFrame({
        "feature":    feature_names,
        "importance": result.importances_mean,
        "std":        result.importances_std,
    }).sort_values("importance", ascending=False)
    print(imp_df.to_string(index=False))
    return imp_df


def prune_features(imp_df, X_train, X_cal, X_test, threshold_ratio=0.01):
    top  = imp_df["importance"].max()
    keep = imp_df[imp_df["importance"] >= threshold_ratio * top]["feature"].tolist()
    dropped = [f for f in imp_df["feature"] if f not in keep]
    if dropped:
        print(f"\nPruning {len(dropped)} low-importance features: {dropped}")
    return X_train[keep], X_cal[keep], X_test[keep], keep


# ─── 5. Regression metrics ────────────────────────────────────────────────────
def regression_metrics(y_true_log, y_pred_log, label=""):
    y_true = np.expm1(y_true_log)
    y_pred = np.expm1(y_pred_log).clip(min=0)

    mae  = mean_absolute_error(y_true, y_pred)
    rmse = mean_squared_error(y_true, y_pred) ** 0.5
    r2   = r2_score(y_true_log, y_pred_log)

    unsafe_true = y_true > EPA_THRESHOLD
    unsafe_pred = y_pred > EPA_THRESHOLD
    tp = ((unsafe_true) & (unsafe_pred)).sum()
    fn = ((unsafe_true) & (~unsafe_pred)).sum()
    fp = ((~unsafe_true) & (unsafe_pred)).sum()
    tn = ((~unsafe_true) & (~unsafe_pred)).sum()

    fnr       = fn / (fn + tp) if (fn + tp) > 0 else 0
    fpr       = fp / (fp + tn) if (fp + tn) > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0

    print(f"\n{'='*50}")
    print(f"  {label}")
    print(f"{'='*50}")
    print(f"  Regression (CFU space): MAE={mae:.1f}  RMSE={rmse:.1f}  R²(log)={r2:.3f}")
    print(f"  Safety @ 235 CFU threshold:")
    print(f"    TP={tp}  FN={fn}  FP={fp}  TN={tn}")
    print(f"    FNR (false negative rate) = {fnr:.3f}  ← minimize this")
    print(f"    FPR (false positive rate) = {fpr:.3f}")
    print(f"    Precision = {precision:.3f}   Recall = {recall:.3f}")
    return {"fnr": fnr, "fpr": fpr, "mae": mae, "rmse": rmse}


def safety_with_upper_ci(y_true_log, y_pred_low_log, y_pred_high_log, label=""):
    y_true      = np.expm1(y_true_log)
    y_pred_high = np.expm1(y_pred_high_log).clip(min=0)

    unsafe_true = y_true > EPA_THRESHOLD
    unsafe_flag = y_pred_high > EPA_THRESHOLD

    tp = ((unsafe_true) & (unsafe_flag)).sum()
    fn = ((unsafe_true) & (~unsafe_flag)).sum()
    fp = ((~unsafe_true) & (unsafe_flag)).sum()
    tn = ((~unsafe_true) & (~unsafe_flag)).sum()

    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

    print(f"\n--- {label} (upper CI > {EPA_THRESHOLD} CFU) ---")
    print(f"  TP={tp}  FN={fn}  FP={fp}  TN={tn}")
    print(f"  FNR = {fnr:.3f}  FPR = {fpr:.3f}")
    return {"fnr": fnr, "fpr": fpr}


# ─── 6. Main ──────────────────────────────────────────────────────────────────
def main(args):
    coverage   = args.coverage
    prune      = args.prune_features
    use_crwa   = args.crwa
    use_mystic = args.mystic

    X, y = load_data(use_crwa, use_mystic)
    feature_names = list(X.columns)

    print(f"\nFeatures ({len(feature_names)}): {feature_names}")
    print(f"Target: log1p(E. coli)  |  samples: {len(y)}")
    print(f"Overall unsafe rate (>235 CFU): {(np.expm1(y) > EPA_THRESHOLD).mean():.1%}")

    # 60/20/20 split
    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42
    )
    X_train, X_cal, y_train, y_cal = train_test_split(
        X_temp, y_temp, test_size=0.25, random_state=42
    )
    print(f"\nSplit → train: {len(X_train)} | cal: {len(X_cal)} | test: {len(X_test)}")

    lgb_params = dict(
        n_estimators=800,
        learning_rate=0.05,
        num_leaves=63,
        min_child_samples=20,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=0.1,
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )

    model_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("lgb",     lgb.LGBMRegressor(**lgb_params)),
    ])

    print("\nFitting initial model for feature importance...")
    model_pipeline.fit(X_train, y_train)
    imp_df = evaluate_feature_importance(model_pipeline, X_test, y_test, feature_names)

    if prune:
        X_train, X_cal, X_test, feature_names = prune_features(
            imp_df, X_train, X_cal, X_test
        )
        print(f"Retained features ({len(feature_names)}): {feature_names}")
        model_pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("lgb",     lgb.LGBMRegressor(**lgb_params)),
        ])
        model_pipeline.fit(X_train, y_train)

    y_pred_test   = model_pipeline.predict(X_test)
    metrics_point = regression_metrics(y_test, y_pred_test, label="Point Estimate (test set)")

    print(f"\nFitting MAPIE conformal wrapper (target coverage={coverage:.0%})...")
    mapie = SplitConformalRegressor(
        estimator=model_pipeline,
        confidence_level=coverage,
        prefit=True,
    )
    mapie.conformalize(X_cal, y_cal)

    y_pred_mapie, y_pi = mapie.predict_interval(X_test)
    y_lo_log = y_pi[:, 0, 0]
    y_hi_log = y_pi[:, 1, 0]

    in_interval = ((y_test.values >= y_lo_log) & (y_test.values <= y_hi_log)).mean()
    print(f"Empirical interval coverage: {in_interval:.1%}  (target: {coverage:.0%})")

    metrics_uci = safety_with_upper_ci(
        y_test.values, y_lo_log, y_hi_log,
        label=f"Upper CI ({coverage:.0%} conformal interval)"
    )

    print("\n=== FNR Summary ===")
    print(f"  Point estimate FNR:       {metrics_point['fnr']:.3f}")
    print(f"  Upper CI FNR (safer):     {metrics_uci['fnr']:.3f}")
    print(f"  Upper CI FPR (tradeoff):  {metrics_uci['fpr']:.3f}")
    print()
    print("  → Recommended inference: flag UNSAFE if upper_CI > 235 CFU")

    joblib.dump(model_pipeline, MODEL_OUT)
    joblib.dump(mapie, MAPIE_OUT)
    joblib.dump({
        "feature_names":    feature_names,
        "coverage":         coverage,
        "epa_threshold":    EPA_THRESHOLD,
        "target_transform": "log1p",
        "point_fnr":        metrics_point["fnr"],
        "uci_fnr":          metrics_uci["fnr"],
        "used_crwa":        use_crwa,
        "used_mystic":      use_mystic,
        "n_samples":        len(y),
    }, META_OUT)

    print(f"\nSaved: {MODEL_OUT}, {MAPIE_OUT}, {META_OUT}")
    return model_pipeline, mapie, feature_names


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--crwa", action="store_true",
        help="Merge CRWA dataset (requires crwa_with_rainfall.csv)"
    )
    parser.add_argument(
        "--mystic", action="store_true",
        help="Merge Mystic River dataset (requires mystic_merged.csv)"
    )
    parser.add_argument(
        "--prune-features", action="store_true",
        help="Drop features with permutation importance < 1%% of top feature"
    )
    parser.add_argument(
        "--coverage", type=float, default=0.90,
        help="Conformal interval coverage (default: 0.90)"
    )
    args = parser.parse_args()
    main(args)