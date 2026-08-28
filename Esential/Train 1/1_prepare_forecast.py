import numpy as np
import pandas as pd
import joblib
import gc
import sys
from pathlib import Path
from sklearn.preprocessing import MinMaxScaler

BASE_DIR       = Path(__file__).resolve().parent
ARTIFACTS_DIR  = BASE_DIR / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

RAW_DATA_PATH  = Path("/content/sri_lanka_labeled_final.xlsx")

X_TRAIN_PATH   = ARTIFACTS_DIR / "X_train.npy"
Y_TRAIN_PATH   = ARTIFACTS_DIR / "y_train.npy"
X_VAL_PATH     = ARTIFACTS_DIR / "X_val.npy"
Y_VAL_PATH     = ARTIFACTS_DIR / "y_val.npy"
X_TEST_PATH    = ARTIFACTS_DIR / "X_test.npy"
Y_TEST_PATH    = ARTIFACTS_DIR / "y_test.npy"
SCALER_PATH    = ARTIFACTS_DIR / "scaler.pkl"

SKIP_SHEET     = "All Districts"
INPUT_WINDOW   = 168      
TARGET_HORIZON = 24       
DROP_COLS = [
    "District", "Date", "DayOfWeek", "ClimateZone", "IsPoyaDay", "IsPeakSeason",
    "IsWeekend", "IsPublicHoliday", "HolidayName", "WeatherCode", "WeatherDesc",
    "ApparentTemp_C", "Label"
]

FINAL_FEATURE_COLS = [
    "Temperature_C", "Precipitation_mm", "Humidity_%", "CloudCover_%",
    "WindSpeed_kmh", "WindGusts_kmh", "DaylightScore",
    "Hour_sin", "Hour_cos", "Month_sin", "Month_cos", "Temp_Change_3h"
]

TARGET_COLS = ["Temperature_C", "Precipitation_mm", "Humidity_%"]

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Hour_sin"]  = np.sin(2 * np.pi * df["Hour"] / 24.0)
    df["Hour_cos"]  = np.cos(2 * np.pi * df["Hour"] / 24.0)
    df["Month_sin"] = np.sin(2 * np.pi * df["Month"] / 12.0)
    df["Month_cos"] = np.cos(2 * np.pi * df["Month"] / 12.0)
    df["Temp_Change_3h"] = df["Temperature_C"].diff(periods=3).fillna(0.0)
    
    existing_drops = [c for c in DROP_COLS if c in df.columns]
    df.drop(columns=existing_drops, errors="ignore", inplace=True)
    df = df[[c for c in FINAL_FEATURE_COLS if c in df.columns]]
    return df

def build_windows_memory_safe(df_scaled: pd.DataFrame, feat_idx: list, targ_idx: list):
    data = df_scaled.values
    n_rows = len(data)
    total_span = INPUT_WINDOW + TARGET_HORIZON
    n_windows = n_rows - total_span + 1
    
    if n_windows <= 0:
        return np.empty((0, INPUT_WINDOW, len(feat_idx)), dtype=np.float32), \
               np.empty((0, TARGET_HORIZON, len(targ_idx)), dtype=np.float32)
               
    X = np.empty((n_windows, INPUT_WINDOW, len(feat_idx)), dtype=np.float32)
    y = np.empty((n_windows, TARGET_HORIZON, len(targ_idx)), dtype=np.float32)
    
    for i in range(n_windows):
        X[i] = data[i : i + INPUT_WINDOW, feat_idx]
        y[i] = data[i + INPUT_WINDOW : i + total_span, targ_idx]
        
    return X, y

def main() -> None:
    print("=" * 70)
    print("  TRIP SMART — DISK STREAMING (MEMMAP) DATA PREPARATION PIPELINE")
    print("=" * 70)

    if not RAW_DATA_PATH.exists():
        print(f"[ERROR] Source file missing at absolute path: {RAW_DATA_PATH}")
        sys.exit(1)

    xl = pd.ExcelFile(RAW_DATA_PATH)
    valid_sheets = [s for s in xl.sheet_names if s.strip() != SKIP_SHEET]
    
    print("\n[STEP 1] Fitting global MinMaxScaler incrementally across sheets...")
    scaler = MinMaxScaler(feature_range=(0, 1))
    
    sheet_meta = {}
    
    for sheet in valid_sheets:
        df = None
        df_eng = None 
        try:
            df = xl.parse(sheet)
            if "Hour" not in df.columns or "Month" not in df.columns:
                print(f"  [WARN] Skipping informational sheet: {sheet}")
                continue
                
            df_eng = engineer_features(df)
            scaler.partial_fit(df_eng.values)
            
            n_windows = len(df_eng) - (INPUT_WINDOW + TARGET_HORIZON) + 1
            if n_windows > 0:
                sheet_meta[sheet] = {
                    "total_windows": n_windows,
                    "train": int(0.70 * n_windows),
                    "val": int(0.15 * n_windows),
                    "test": n_windows - int(0.70 * n_windows) - int(0.15 * n_windows)
                }
                print(f"  [OK] Parsed and scaled {sheet:15s} | Row Count: {len(df):,}")
        except Exception as e:
            print(f"  [ERROR] Failed to process sheet {sheet}: {e}")
        finally:
            if df is not None: del df
            if df_eng is not None: del df_eng
            gc.collect()

    joblib.dump(scaler, SCALER_PATH)
    print(f"\n[SCALER] Saved master scaling parameters to: {SCALER_PATH}")
    
    print("\n[STEP 2] Creating memory-mapped files directly on disk (0 RAM)...")
    total_train = sum(m["train"] for m in sheet_meta.values())
    total_val   = sum(m["val"] for m in sheet_meta.values())
    total_test  = sum(m["test"] for m in sheet_meta.values())
    
    X_train = np.lib.format.open_memmap(X_TRAIN_PATH, mode='w+', dtype='float32', shape=(total_train, INPUT_WINDOW, len(FINAL_FEATURE_COLS)))
    y_train = np.lib.format.open_memmap(Y_TRAIN_PATH, mode='w+', dtype='float32', shape=(total_train, TARGET_HORIZON, len(TARGET_COLS)))
    X_val   = np.lib.format.open_memmap(X_VAL_PATH, mode='w+', dtype='float32', shape=(total_val, INPUT_WINDOW, len(FINAL_FEATURE_COLS)))
    y_val   = np.lib.format.open_memmap(Y_VAL_PATH, mode='w+', dtype='float32', shape=(total_val, TARGET_HORIZON, len(TARGET_COLS)))
    X_test  = np.lib.format.open_memmap(X_TEST_PATH, mode='w+', dtype='float32', shape=(total_test, INPUT_WINDOW, len(FINAL_FEATURE_COLS)))
    y_test  = np.lib.format.open_memmap(Y_TEST_PATH, mode='w+', dtype='float32', shape=(total_test, TARGET_HORIZON, len(TARGET_COLS)))
    
    print(f"  Created X_train on disk : {X_train.shape}")

    feat_idx = [FINAL_FEATURE_COLS.index(c) for c in FINAL_FEATURE_COLS]
    targ_idx = [FINAL_FEATURE_COLS.index(c) for c in TARGET_COLS]
    
    idx_tr, idx_va, idx_te = 0, 0, 0
    
    for sheet, meta in sheet_meta.items():
        df = xl.parse(sheet)
        df_eng = engineer_features(df)
        
        scaled_data = scaler.transform(df_eng.values)
        df_scaled = pd.DataFrame(scaled_data, columns=df_eng.columns)
        
        X_sheet, y_sheet = build_windows_memory_safe(df_scaled, feat_idx, targ_idx)
        
        tr_len, va_len, te_len = meta["train"], meta["val"], meta["test"]
        
        X_train[idx_tr : idx_tr + tr_len] = X_sheet[0 : tr_len]
        y_train[idx_tr : idx_tr + tr_len] = y_sheet[0 : tr_len]
        X_val[idx_va : idx_va + va_len]   = X_sheet[tr_len : tr_len + va_len]
        y_val[idx_va : idx_va + va_len]   = y_sheet[tr_len : tr_len + va_len]
        X_test[idx_te : idx_te + te_len]  = X_sheet[tr_len + va_len : tr_len + va_len + te_len]
        y_test[idx_te : idx_te + te_len]  = y_sheet[tr_len + va_len : tr_len + va_len + te_len]
        
        print(f"  [OK] Processed and saved to disk: {sheet:15s}")
        
        idx_tr += tr_len
        idx_va += va_len
        idx_te += te_len
        
        del df, df_eng, df_scaled, X_sheet, y_sheet
        gc.collect()

    print("\n[STEP 4] Flushing data to disk and safely closing files...")
    X_train.flush()
    y_train.flush()
    X_val.flush()
    y_val.flush()
    X_test.flush()
    y_test.flush()
    
    del X_train, y_train, X_val, y_val, X_test, y_test
    print("  [SUCCESS] All optimized datasets safely stored on disk in /content/artifacts/")

if __name__ == "__main__":
    main()