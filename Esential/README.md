# TripSmart — Essential Files

This folder is a self-contained bundle of the two trained forecasting models
(scripts + the actual trained artifacts) and the app's user manual, pulled
out of the main repo for easy handoff. Everything here is a **copy** — the
originals still live in their normal places in the repo (`extra/output/Gru/`,
`extra/output/24_hour_rainfall/`, `Backend/models/`), nothing was moved out
of them.

## What's in here

| Folder / file | What it is |
|---|---|
| `Train 1/` | The **hourly forecast model** (GRU) — predicts temperature, humidity and rain for the next 24 hours, one value per hour. Training scripts (`1_prepare_forecast.py`, `2_train_forecast.py`, `train.py`) plus the actual deployed model (`best_checkpoint.keras`, `scaler.pkl`). |
| `Train 2/` | The **24-hour total rainfall model** — a separate hurdle model (occurrence + amount) that predicts one number: total rain expected over the next 24 hours. Training scripts (`config.py`, `data_prep.py`, `model.py`, `train_colab.py`), the deployed model (`rain24h_model.keras`, `rain24h_scaler.pkl`, `rain24h_calibration.json`), an alternate training run (`rain24h_model1.keras` / `Rainfall24/`), and the real evaluation charts (training curves, confusion matrix, ROC curve, calibration curve, accuracy table). |
| `TripSmart_User_Manual.docx` | The end-user guide to the app itself — not a training document. |

Both `Train 1` and `Train 2` are one model each, trained independently, and
both feed the same live app: `Train 1`'s model handles temperature and
humidity everywhere plus a rough hourly rain signal; `Train 2`'s model is
what actually produces the daily rain total shown to users, since rain is
far more predictable as a 24-hour total than as a single hour.

## Setting up TripSmart locally

The trained models above are already the ones the live app uses — you do
**not** need to retrain anything just to run the app. Retraining
instructions are in the second half of this file, only needed if you want
to reproduce or improve the models themselves.

### 1. Prerequisites

- Python 3.12
- Node.js (LTS) with npm
- A free [Supabase](https://supabase.com) project (Postgres database)
- A free [WeatherAPI](https://www.weatherapi.com/signup.aspx) key
- A free [SendGrid](https://signup.sendgrid.com/) account (for signup/reset emails)
- A Google Cloud API key with the Geocoding API enabled (for destination search)
- Expo Go app on your phone, or an Android/iOS emulator, to run the frontend

### 2. Backend

```bash
cd Backend
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in the real values — every variable
is explained inline in that file (where to find it, which are required vs
optional). At minimum you need `SUPABASE_DB_URL`, `WEATHERAPI_KEY`, and a
`JWT_SECRET` (generate one with
`python -c "import secrets; print(secrets.token_hex(32))"`). Email and
geocoding features degrade gracefully without their keys — the rest of the
app still runs.

Make sure the model files are in place (they already are, copied from this
`Esential` bundle originally in `Backend/models/`):

```
Backend/models/best_checkpoint.keras
Backend/models/scaler.pkl
Backend/models/rain24h_model.keras
Backend/models/rain24h_scaler.pkl
Backend/models/rain24h_calibration.json
```

If you're setting up a fresh checkout that's missing them, copy them there
from `Train 1/` and `Train 2/` in this folder.

Run the API:

```bash
uvicorn main:app --reload --port 8000
```

Check `http://localhost:8000/api/v1/forecast/health` — `model_loaded: true`
confirms both models loaded correctly. Database tables are created
automatically on first startup; nothing to run by hand in Supabase.

### 3. Frontend

```bash
cd Frontend
npm install
npm start
```

This opens the Expo dev server — scan the QR code with Expo Go on your
phone, or press `a` for an Android emulator / `i` for an iOS simulator.
Point the app at your local backend by setting the API base URL in
`Frontend/lib/config.ts` to `http://<your-machine-IP>:8000` (not
`localhost` — a physical phone can't resolve your computer's `localhost`).

### 4. Retraining a model (optional)

Both `Train 1/` and `Train 2/` are meant to be run in Google Colab (free
GPU tier) rather than locally — training uses several GB of windowed data
that a laptop CPU will be very slow at. Upload the folder plus the source
weather dataset (`sri_lanka_labeled_extended.parquet`) to a Colab notebook,
then:

- **Train 1**: run `1_prepare_forecast.py` first (builds the windowed
  `.npy` tensors), then `2_train_forecast.py` (trains and saves
  `best_checkpoint.keras` + `scaler.pkl`).
- **Train 2**: run `train_colab.py` directly — it calls `data_prep.py` and
  `model.py` internally, and saves `rain24h_model.keras` +
  `rain24h_scaler.pkl` + a full evaluation report.

Once a new model file is produced, drop it into `Backend/models/` (matching
the filenames above) to have the running backend pick it up.
