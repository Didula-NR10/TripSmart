---
title: Tripsmart Forecast API
emoji: 🌦️
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Tripsmart Backend

FastAPI service behind the Tripsmart / Rawana Ceylon app: the GRU weather
forecaster, district law/specialty data, ground reports, and accounts
(signup, OTP email verification, login, password reset/change).

Layered as `routers → services → repositories → (model | Open-Meteo | Supabase)`.

## Deploying this Space

1. **Push this `Backend/` folder as the root of a new Docker Space.**
   From your local machine (with this Space added as a git remote):
   ```
   cd Backend
   git init                                   # if not already a repo
   git remote add space https://huggingface.co/spaces/<you>/<space-name>
   git add .
   git commit -m "Deploy backend"
   git push space main
   ```
   The build follows `Dockerfile` automatically — nothing else to configure
   for the build itself.

2. **Set Secrets** — Space Settings → *Variables and secrets* → add these as
   **Secrets** (never as plain Variables, and never committed to `.env`):

   | Name | Required | Notes |
   |---|---|---|
   | `SUPABASE_DB_URL` | Yes, for persistence | Supabase **Session pooler** URI (IPv4). Percent-encode special characters in the password (`@` → `%40`). Without this the API still serves forecasts, but accounts, ground reports, and the notebook are disabled. |
   | `SMTP_USER` | Yes, for real signup/reset emails | Your sending address, e.g. a Gmail address. |
   | `SMTP_APP_PASSWORD` | Yes, alongside `SMTP_USER` | A Gmail **App Password** (Google Account → Security → 2-Step Verification → App passwords) — never your real Gmail password. |
   | `SMTP_HOST` / `SMTP_PORT` | No | Default `smtp.gmail.com` / `587`. Only change for a non-Gmail provider. |
   | `SMTP_FROM_EMAIL` | No | Defaults to `SMTP_USER`. |
   | `ALLOWED_ORIGINS` | Yes, for the real frontend | Comma-separated origins allowed to call this API, e.g. `https://your-app.expo.dev,http://localhost:8081`. |
   | `ENVIRONMENT` | Recommended | Set to `production` on the deployed Space. Leaving it `development` also accepts any `localhost:<port>` origin, which you don't want once this is public. |

   Without `SUPABASE_DB_URL` set, the app still starts and forecasts still
   work — persistence quietly disables itself rather than crashing (see
   `core/database.py`).

3. **Wait for the build**, then check `https://<you>-<space-name>.hf.space/api/v1/forecast/health`.
   `model_loaded: true` confirms the GRU + scaler loaded correctly.

## Local run (unchanged)

```
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Notes on this container

- Runs as a non-root user (HF Spaces' documented convention for Docker Spaces).
- Listens on `7860` — the port HF Spaces routes to Docker Spaces by default.
- `models/best_checkpoint.keras` and `models/scaler.pkl` are committed directly
  (both together are ~1.2 MB, well under Git LFS territory).
- `.env` is excluded from the image on purpose (`.dockerignore`) — real
  credentials only ever come from Space Secrets, never from a baked-in file.
