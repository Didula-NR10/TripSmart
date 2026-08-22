# Retraining pipeline

Implements: **collect new data -> retrain periodically -> test the new model
-> deploy only if it's better** — the loop discussed in
`extra/output/SYSTEM_DOCUMENTATION.md`.

## What runs automatically vs. what doesn't

| Step | Automatic? |
|---|---|
| Real weather gets logged to `weather_observations` | Yes — already happens on every live forecast request (`forecast/repositories.py`), no change needed. |
| Pipeline runs on a schedule | Yes, once this workflow is enabled — `.github/workflows/retrain-model.yml`, monthly (1st of each month, 03:00 UTC), or on-demand via the Actions tab's "Run workflow" button. |
| Retrain, evaluate, decide promote/keep | Yes — `training/pipeline.py`, triggered by the workflow above. |
| **Deploy to production** | **No, by design.** If the candidate wins, the workflow opens a pull request with the new model files and a metrics report. Render only redeploys on a push to `main`, so nothing goes live until a human reviews and merges that PR. |

## One-time setup before the schedule can do anything

1. Add `SUPABASE_DB_URL` as a **GitHub Actions secret**: repo → Settings →
   Secrets and variables → Actions → New repository secret. Use the exact
   same connection string that's in `Backend/.env` (the session-pooler URL,
   not the direct one — see `.env.example`'s comments).
2. Trigger the workflow manually once (Actions tab → "Retrain forecast
   model" → "Run workflow") to confirm it runs end-to-end before trusting
   the monthly schedule. Check the uploaded `retrain-report` artifact either
   way.

## Do you need to manually retrain anything first?

No. There's no separate manual training step to perform before this can
run — `pipeline.py` fine-tunes from whatever's already deployed
(`Backend/models/best_checkpoint.keras`) using whatever real data has
accumulated in `weather_observations`. What the first run actually *does*
depends entirely on how much real data exists yet:

- **Too little data (likely for a while after launch)** — the pipeline
  refuses to train at all (`MIN_TOTAL_WINDOWS` in `training/config.py`,
  default 300 windows across all districts combined) and the report just
  says so. This is the expected, correct outcome early on — not a bug.
- **Enough data, but the fine-tuned candidate doesn't beat the current
  model on held-out real data** — also expected to happen often; the
  report explains why (see `evaluate.is_better`), nothing changes.
- **Enough data AND the candidate genuinely improves on the same held-out
  backtest discipline used elsewhere in this repo** — a PR appears.

## Running it locally instead of waiting for CI

```bash
cd Backend
pip install -r requirements.txt
export SUPABASE_DB_URL="postgresql://...same string as .env..."   # PowerShell: $env:SUPABASE_DB_URL="..."
python -m training.pipeline
```

Output lands in `training/output/`: `retrain_report.json` (machine-readable)
and `retrain_report.md` (the same content, human-readable — this is what
becomes the PR body). If it promoted a candidate, `Backend/models/` will
have been updated in place in your working tree — review the diff like any
other change before committing.

## Why fine-tune instead of training from scratch every time

The original checkpoint was trained on a large multi-year dataset. Whatever
has accumulated in `weather_observations` since the app went live will, for
a long time, be much smaller than that — training a fresh network on just
that slice would likely be *worse* than the current model. Fine-tuning at a
low learning rate (`training/config.py: FINE_TUNE_LR`) instead treats new
real data as a correction on top of everything already learned. The
mandatory backtest-and-compare gate is what actually keeps this safe, not
the fine-tuning strategy by itself — a bad fine-tune still just gets
rejected.

## Why the bias-correction tables get regenerated too

`forecast/utils.py`'s per-district temperature/humidity correction tables
are fit *against a specific checkpoint*; SYSTEM_DOCUMENTATION.md §12.3
already flags that they go stale the moment the model changes. Promoting a
candidate here also regenerates them (`training/bias_tables.py`, same
fit-on-past/evaluate-on-held-out-future method as `extra/backtest.py`) and
writes `Backend/models/bias_correction.json`, which `forecast/utils.py`
loads automatically if present (falling back to the original hardcoded
tables if it's missing — a fresh clone with no `bias_correction.json`
behaves exactly as before this pipeline existed).
