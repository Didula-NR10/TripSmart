from __future__ import annotations

import logging
import os

log = logging.getLogger("trip_smart.training.data_source")

def fetch_all_districts() -> dict:
    source = os.environ.get("TRAINING_DATA_SOURCE", "database").strip().lower()

    if source == "archive":
        from training.pull_archive_data import fetch_all_districts as fetch_archive
        lookback_days = int(os.environ.get("TRAINING_ARCHIVE_LOOKBACK_DAYS", "365"))
        log.info("Data source: Open-Meteo historical archive (%d days lookback).", lookback_days)
        return fetch_archive(lookback_days=lookback_days)

    if source == "database":
        from training.pull_data import fetch_all_districts as fetch_db
        log.info("Data source: Supabase weather_observations (live app traffic).")
        return fetch_db()

    raise ValueError(f"Unknown TRAINING_DATA_SOURCE={source!r} — use 'database' or 'archive'.")
