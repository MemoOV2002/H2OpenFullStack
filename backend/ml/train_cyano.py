"""
train_cyano.py
Trains a binary Random Forest classifier to predict cyanobacteria bloom risk
on the Charles River using EPA buoy data.

Label:  est. cyano (cells/ml) >= 70,000  →  bloom = 1
        (MA DPH public health advisory threshold)

Features used at inference (match H2Open buoy sensors):
  - temperature      (temp c)
  - conductivity     (spcond (ms/cm) * 1000 → µS/cm)
  - ph               (ph)
  - turbidity        (turbidity (fnu), FNU ≈ NTU)

Output: cyano_model.pkl
"""

import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import classification_report, confusion_matrix

from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
DATA_PATH = Path(__file__).parent / "crbuoy.csv"
MODEL_OUT  = Path(__file__).parent / "model" / "cyano_model.pkl"
BLOOM_THRESHOLD = 70_000   # cells/mL — MA DPH advisory threshold

FEATURE_COLS = [
    "temp c",
    "spcond (ms/cm)",
    "ph",
    "turbidity (fnu)",
]

# ── Load ──────────────────────────────────────────────────────────────────────
print("Loading data...")
df = pd.read_csv(DATA_PATH)
print(f"  {len(df):,} rows loaded")

# ── Clean ─────────────────────────────────────────────────────────────────────
# Clip sensor artifacts (negative cyano readings)
df["est. cyano (cells/ml)"] = df["est. cyano (cells/ml)"].clip(lower=0)

# Clip negative turbidity (sensor noise at low end)
df["turbidity (fnu)"] = df["turbidity (fnu)"].clip(lower=0)

# Convert conductivity mS/cm → µS/cm to match buoy output
df["spcond (ms/cm)"] = df["spcond (ms/cm)"] * 1000

# ── Label ─────────────────────────────────────────────────────────────────────
df["bloom"] = (df["est. cyano (cells/ml)"] >= BLOOM_THRESHOLD).astype(int)

print(f"\nClass distribution:")
counts = df["bloom"].value_counts()
print(f"  No bloom (0): {counts[0]:,} ({100*counts[0]/len(df):.1f}%)")
print(f"  Bloom    (1): {counts[1]:,} ({100*counts[1]/len(df):.1f}%)")

# ── Features ──────────────────────────────────────────────────────────────────
X = df[FEATURE_COLS].copy()
y = df["bloom"]

# Rename to match inference-time column names from the buoy
X.columns = ["temperature", "conductivity", "ph", "turbidity"]

# ── Pipeline ──────────────────────────────────────────────────────────────────
pipeline = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("scaler",  StandardScaler()),
    ("model",   RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        class_weight="balanced",   # guards against future imbalanced datasets
        random_state=42,
        n_jobs=-1,
    )),
])

# ── Cross-validation ──────────────────────────────────────────────────────────
print("\nRunning 5-fold cross-validation...")
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

for metric in ["accuracy", "f1", "recall"]:
    scores = cross_val_score(pipeline, X, y, cv=cv, scoring=metric)
    print(f"  {metric:10s}: {scores.mean():.3f} ± {scores.std():.3f}")

# ── Final fit + report ────────────────────────────────────────────────────────
print("\nFitting final model on full dataset...")
pipeline.fit(X, y)

y_pred = pipeline.predict(X)
print("\nClassification report (training set):")
print(classification_report(y, y_pred, target_names=["No Bloom", "Bloom"]))

cm = confusion_matrix(y, y_pred)
tn, fp, fn, tp = cm.ravel()
fnr = fn / (fn + tp)
print(f"False Negative Rate: {fnr:.3f}  ({fn} missed blooms out of {fn+tp} total bloom readings)")

# ── Feature importance ────────────────────────────────────────────────────────
rf = pipeline.named_steps["model"]
importances = pd.Series(
    rf.feature_importances_,
    index=["temperature", "conductivity", "ph", "turbidity"]
).sort_values(ascending=False)

print("\nFeature importances:")
for feat, imp in importances.items():
    bar = "█" * int(imp * 40)
    print(f"  {feat:15s} {imp:.3f}  {bar}")

# ── Save ──────────────────────────────────────────────────────────────────────
joblib.dump(pipeline, MODEL_OUT)
print(f"\nModel saved → {MODEL_OUT}")