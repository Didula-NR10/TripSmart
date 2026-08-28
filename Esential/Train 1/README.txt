Put the two model artifacts here:

  best_checkpoint.keras   (or trip_smart_gru_forecaster.keras — point MODEL_PATH at it)
  scaler.pkl

Paths are set in core/config.py (MODEL_PATH / SCALER_PATH) and can be
overridden from .env.

GET /api/v1/forecast/health reports whether both were found.
