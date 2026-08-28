from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
OUT_PATH = BASE_DIR / "weather_verification.xlsx"

STATION_READINGS: dict[str, tuple[float, float, float]] = {
    "Anuradhapura": (35.0, 26.2, 0.0),
    "Badulla": (32.8, 19.6, 0.0),
    "Batticaloa": (33.5, 26.5, 0.0),
    "Colombo": (31.0, 27.6, 1.2),
    "Galle": (29.3, 25.6, 1.6),
    "Hambanthota": (30.8, 25.9, 0.1),
    "Jaffna": (32.6, 27.5, 0.0),
    "Monaragala": (36.9, 25.2, 0.0),
    "Katugasthota": (29.7, 22.5, 3.0),
    "Katunayake": (31.4, 27.0, 2.9),
    "Kurunagala": (32.2, 25.3, 0.1),
    "Mannar": (30.7, 27.1, 0.0),
    "Polonnaruwa": (38.6, 27.5, 0.0),
    "Nuwara Eliya": (20.5, 15.3, 4.1),
    "Pothuvil": (37.2, 26.3, 0.0),
    "Puttalam": (31.4, 27.0, 0.0),
    "Rathnapura": (31.4, 24.9, 15.5),
    "Trincomalee": (37.2, 26.9, 0.0),
    "Vavuniya": (36.5, 26.3, 0.0),
    "Mullaitivu": (36.6, 27.0, 0.0),
}

STATION_TO_DISTRICT: dict[str, str] = {
    "Anuradhapura": "Anuradhapura",
    "Badulla": "Badulla",
    "Batticaloa": "Batticaloa",
    "Colombo": "Colombo",
    "Galle": "Galle",
    "Hambanthota": "Hambantota",
    "Jaffna": "Jaffna",
    "Monaragala": "Monaragala",
    "Katugasthota": "Kandy",
    "Katunayake": "Gampaha",
    "Kurunagala": "Kurunegala",
    "Mannar": "Mannar",
    "Polonnaruwa": "Polonnaruwa",
    "Nuwara Eliya": "NuwaraEliya",
    "Pothuvil": "Ampara",
    "Puttalam": "Puttalam",
    "Rathnapura": "Ratnapura",
    "Trincomalee": "Trincomalee",
    "Vavuniya": "Vavuniya",
    "Mullaitivu": "Mullaitivu",
}

def main() -> None:
    rows = []
    for station, (max_t, min_t, rain) in STATION_READINGS.items():
        rows.append({
            "District": STATION_TO_DISTRICT[station],
            "Met_Station": station,
            "Max_Temp_C": max_t,
            "Min_Temp_C": min_t,
            "Rainfall_mm": rain,
        })

    result = pd.DataFrame(rows).sort_values("District").reset_index(drop=True)
    print(result.to_string(index=False))

    mode = "a" if OUT_PATH.exists() else "w"
    kwargs = {"if_sheet_exists": "replace"} if mode == "a" else {}
    with pd.ExcelWriter(OUT_PATH, engine="openpyxl", mode=mode, **kwargs) as writer:
        result.to_excel(writer, sheet_name="MetDept_PDF", index=False)

    print(f"\nSaved to {OUT_PATH} (sheet: MetDept_PDF)")

if __name__ == "__main__":
    main()
