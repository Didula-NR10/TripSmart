from __future__ import annotations

import sys

from model_pipeline import DISTRICT_COORDS, predict_next_24h

def main() -> None:
    district = sys.argv[1] if len(sys.argv) > 1 else "Colombo"
    if district not in DISTRICT_COORDS:
        print(f"Unknown district '{district}'. Choose one of:")
        print(", ".join(sorted(DISTRICT_COORDS)))
        sys.exit(1)

    print(f"\nFetching last 168h of observations for {district} from Open-Meteo...")
    result = predict_next_24h(district)

    print(f"\nLast observation (Colombo time): {result['last_observation']}")
    print(f"\n{'Hour':<6}{'Valid time':<20}{'Temp (C)':<12}{'Rain (mm)':<12}{'Humidity (%)':<14}")
    print("-" * 64)
    for i, row in enumerate(result["forecast"], start=1):
        print(
            f"{i:<6}{row['valid_time'].strftime('%Y-%m-%d %H:%M'):<20}"
            f"{row['temperature_c']:<12}{row['precipitation_mm']:<12}{row['humidity_pct']:<14}"
        )
    print()

if __name__ == "__main__":
    main()
