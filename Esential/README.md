# TripSmart — Essential Files

## What's in here

| Folder / file | What it is |
|---|---|
| `Train 1/` | Hourly forecast model (GRU). Scripts: `1_prepare_forecast.py`, `2_train_forecast.py`, `train.py`. Model: `best_checkpoint.keras`, `scaler.pkl`. |
| `Train 2/` | 24-hour rainfall model (hurdle). Scripts: `config.py`, `data_prep.py`, `model.py`, `train_colab.py`. Model: `rain24h_model.keras`, `rain24h_scaler.pkl`, `rain24h_calibration.json`. |
| `TripSmart_User_Manual.docx` | End-user app guide. |

---

## 1. Install prerequisites

### Python 3.12

- Windows: `winget install Python.Python.3.12`
- Mac: `brew install python@3.12`
- Linux: `sudo apt install python3.12 python3.12-venv`
- Manual: https://www.python.org/downloads/

Verify:
```bash
python --version
```

### Node.js (LTS) + npm

- Windows: `winget install OpenJS.NodeJS.LTS`
- Mac: `brew install node`
- Linux: `sudo apt install nodejs npm`
- Manual: https://nodejs.org/

Verify:
```bash
node --version
npm --version
```

### Expo Go (to run the app on a phone)

- Install "Expo Go" from the Play Store (Android) or App Store (iOS).
- Alternative: Android Studio emulator or Xcode iOS simulator.

### Accounts / keys needed

- [Supabase](https://supabase.com) — free project, Postgres database
- [WeatherAPI](https://www.weatherapi.com/signup.aspx) — free API key
- [SendGrid](https://signup.sendgrid.com/) — free account, for signup/reset emails
- Google Cloud — API key with Geocoding API enabled, for destination search

---

## 2. Run the backend

```bash
cd Backend
pip install -r requirements.txt
```

Copy `.env.example` to `.env`, then fill in:

| Variable | Required |
|---|---|
| `SUPABASE_DB_URL` | Yes |
| `WEATHERAPI_KEY` | Yes |
| `JWT_SECRET` | Yes — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `SENDGRID_API_KEY`, `SMTP_FROM_EMAIL` | No — signup/reset emails print to the console instead |
| `GOOGLE_MAPS_API_KEY` | No — destination search disabled without it |

Model files must be present at:
```
Backend/models/best_checkpoint.keras
Backend/models/scaler.pkl
Backend/models/rain24h_model.keras
Backend/models/rain24h_scaler.pkl
Backend/models/rain24h_calibration.json
```
If missing, copy them from `Train 1/` and `Train 2/` in this folder.

Start the server:
```bash
uvicorn main:app --reload --port 8000
```

Check: `http://localhost:8000/api/v1/forecast/health` → `model_loaded: true`.

---

## 3. Run the frontend

```bash
cd Frontend
npm install
npm start
```

Scan the QR code with Expo Go, or press `a` (Android emulator) / `i` (iOS simulator).

Set the backend URL in `Frontend/lib/config.ts`:
```
http://<your-machine-IP>:8000
```
Use your machine's LAN IP, not `localhost` — a physical phone can't resolve `localhost` as your computer.

---

## 4. Retrain a model (optional)

Not required to run the app — the models above are already the ones deployed.

Run in Google Colab (free GPU tier), not locally — training needs several GB of windowed data. Upload the folder plus `sri_lanka_labeled_extended.parquet`.

- **Train 1**: run `1_prepare_forecast.py`, then `2_train_forecast.py`.
- **Train 2**: run `train_colab.py` directly.

Drop the resulting model file into `Backend/models/` (same filenames as above) to use it.
