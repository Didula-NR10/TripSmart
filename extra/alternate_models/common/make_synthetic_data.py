from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "synthetic_sample.xlsx"
DISTRICTS = {"Colombo": (6.9271, 79.8612), "Kandy": (7.2906, 80.6337)}
DAYS = 70

def make_district(name: str, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    hours = DAYS * 24
    start = pd.Timestamp("2025-01-01")
    dt = pd.date_range(start, periods=hours, freq="h")

    hour_of_day = dt.hour.values
    day_of_year = dt.dayofyear.values

    base_temp = 27 + 3 * np.sin(2 * np.pi * (day_of_year - 60) / 365)
    diurnal = 3.5 * np.sin(2 * np.pi * (hour_of_day - 9) / 24)
    temp = base_temp + diurnal + rng.normal(0, 0.6, hours)

    humidity = 78 - 12 * np.sin(2 * np.pi * (hour_of_day - 9) / 24) + rng.normal(0, 2.5, hours)
    humidity = np.clip(humidity, 40, 100)

    rain_prob = 0.08 + 0.05 * (np.sin(2 * np.pi * (hour_of_day - 15) / 24) > 0.3)
    rain = np.where(rng.random(hours) < rain_prob, rng.exponential(1.5, hours), 0.0)

    cloud = np.clip(40 + 20 * np.sin(2 * np.pi * (hour_of_day - 14) / 24) + rng.normal(0, 8, hours), 0, 100)
    wind = np.clip(10 + rng.normal(0, 3, hours), 0, None)
    gusts = wind + np.clip(rng.normal(5, 2, hours), 0, None)

    daylight = np.clip(np.sin(2 * np.pi * (hour_of_day - 6) / 24), 0, None)
    radiation = daylight * 900 * (1 - cloud / 150) + rng.normal(0, 15, hours)
    radiation = np.clip(radiation, 0, None)

    pressure = 1011 + 2 * np.sin(2 * np.pi * day_of_year / 365) + rng.normal(0, 0.8, hours)
    dewpoint = temp - (100 - humidity) / 5

    return pd.DataFrame({
        "datetime": dt,
        "district": name,
        "Temperature_C": temp.round(2),
        "Precipitation_mm": rain.round(3),
        "Humidity_%": humidity.round(1),
        "CloudCover_%": cloud.round(1),
        "WindSpeed_kmh": wind.round(2),
        "WindGusts_kmh": gusts.round(2),
        "radiation": radiation.round(1),
        "Pressure_hPa": pressure.round(1),
        "DewPoint_C": dewpoint.round(2),
    })

def main() -> None:
    frames = [make_district(name, seed=i * 7 + 1) for i, name in enumerate(DISTRICTS)]
    df = pd.concat(frames, ignore_index=True)
    OUT_PATH.parent.mkdir(exist_ok=True)
    df.to_excel(OUT_PATH, index=False)
    print(f"Synthetic sample written to {OUT_PATH} ({len(df)} rows, "
          f"{df['district'].nunique()} districts, {DAYS} days each).")

if __name__ == "__main__":
    main()
