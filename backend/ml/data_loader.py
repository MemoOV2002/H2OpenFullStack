"""
Load and merge MWRA Charles River physical and bacteria Excel datasets.
"""
import pandas as pd
from pathlib import Path

# Excel files live in the project root (one level above backend/)
DATA_DIR = Path(__file__).parent.parent.parent

PHYSICAL_FILE = DATA_DIR / "cr_physical.xlsx"
BACTERIA_FILE = DATA_DIR / "cr_bacteria.xlsx"

PHYSICAL_SHEET = "MWRA Physical Data all yrs"
BACTERIA_SHEET = "MWRA Charles Bacteria all yrs"

# Rows 1-5 are metadata/disclaimer; row 6 is the header
SKIP_ROWS = 5


def load_physical() -> pd.DataFrame:
    df = pd.read_excel(PHYSICAL_FILE, sheet_name=PHYSICAL_SHEET, skiprows=SKIP_ROWS, engine="openpyxl")
    df.columns = df.columns.str.strip()
    df = df.rename(columns={"Date/time (EASTERN STANDARD TIME)": "datetime"})
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df["date"] = df["datetime"].dt.date
    return df


def load_bacteria() -> pd.DataFrame:
    df = pd.read_excel(BACTERIA_FILE, sheet_name=BACTERIA_SHEET, skiprows=SKIP_ROWS, engine="openpyxl")
    df.columns = df.columns.str.strip()
    df = df.rename(columns={"Date/time (EASTERN STANDARD TIME)": "datetime"})
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df["date"] = df["datetime"].dt.date

    # Resolve censored E. coli values:
    #   '<' (left-censored)  → use detection_limit / 2  (standard substitution)
    #   '>' (right-censored) → use value as-is
    ecoli_col = next(c for c in df.columns if "E. coli" in c and "#/100mL" in c)
    censor_col = next(c for c in df.columns if "E. coli" in c and ("'" in c or ">" in c))

    df["ecoli_cfu"] = pd.to_numeric(df[ecoli_col], errors="coerce")
    mask_lt = df[censor_col].astype(str).str.strip() == "<"
    df.loc[mask_lt, "ecoli_cfu"] = df.loc[mask_lt, "ecoli_cfu"] / 2

    # Normalise rainfall column names
    rain_map = {}
    for col in df.columns:
        if "Logan Rainfall" in col:
            if "previous 2 days" in col:
                rain_map[col] = "rainfall_3day"
            elif "previous day" in col:
                rain_map[col] = "rainfall_2day"
            else:
                rain_map[col] = "rainfall_1day"
    df = df.rename(columns=rain_map)

    return df


def load_merged() -> pd.DataFrame:
    """Merge physical and bacteria datasets on Station ID + date + Surface or Bottom."""
    phys = load_physical()
    bact = load_bacteria()

    bact_cols = ["Station ID", "date", "Surface or Bottom",
                 "ecoli_cfu", "rainfall_1day", "rainfall_2day", "rainfall_3day"]
    # Keep only columns that exist
    bact_cols = [c for c in bact_cols if c in bact.columns]

    merged = pd.merge(
        phys,
        bact[bact_cols],
        on=["Station ID", "date", "Surface or Bottom"],
        how="inner",
    )

    # Keep surface samples only (S) for consistency with buoy measurements
    merged = merged[merged["Surface or Bottom"].str.strip() == "S"].copy()

    return merged
