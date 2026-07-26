# 01_gru_seq2seq — encoder-decoder GRU

The most direct upgrade over the currently-shipped model. Same recurrent
cell type (GRU), same base 12-feature contract, same 168h→24h shape — the
one thing that's different is the output head.

## Why this might do better

The production model (`Backend/models/best_checkpoint.keras`) is:
`GRU(128) → GRU(64) → Dropout → Dense(72) → reshape(24, 3)`. That
`Dense(72)` treats all 24 forecast hours as one flat regression problem — it
has no mechanism for its own hour+5 prediction to inform hour+6.

This model instead uses a proper **sequence decoder**:
`Encoder: GRU(128) → GRU(96) [final state kept]` then
`Decoder: RepeatVector(24) → GRU(96, initial_state=encoder_state) →
TimeDistributed(Dense(3))`. The decoder unrolls 24 steps from the encoder's
final state, and its own recurrent state carries information from step t to
step t+1 — closer to how the model would work if it were generating the
forecast one hour at a time.

184,995 trainable params (vs 96,456 in production) — see `model.py` for the
exact layer-by-layer architecture and more detail on the design reasoning.

## Steps — local (uses the repo's existing venv)

```bash
cd extra/alternate_models/01_gru_seq2seq

# smoke test first (optional but recommended) — proves the pipeline works
# before you wait on a real training run
cd ../common && ../../../venv/Scripts/python.exe make_synthetic_data.py && cd ../01_gru_seq2seq
../../../venv/Scripts/python.exe train.py --epochs 3    # fast sanity check

# real training run, once you have your xlsx
../../../venv/Scripts/python.exe train.py --data path/to/your_data.xlsx --epochs 60
```

CPU-only on this hardware will work but be slow for a full run (this is a
GRU, similar cost per step to production, but seq2seq unrolling adds some
overhead) — Colab's free GPU is recommended for the real run.

## Steps — Google Colab (free tier, T4 GPU)

```python
# Cell 1 — mount Drive (so artifacts/ survives the session ending)
from google.colab import drive
drive.mount('/content/drive')

# Cell 2 — get the code onto Colab (either upload the alternate_models
# folder as a zip and unzip, or clone your repo)
!unzip /content/drive/MyDrive/alternate_models.zip -d /content/

# Cell 3 — install dependencies (TensorFlow + GPU support already present on Colab)
%cd /content/alternate_models/01_gru_seq2seq
!pip install -q -r ../common/requirements.txt

# Cell 4 — upload your xlsx (or read it straight from Drive)
from google.colab import files
uploaded = files.upload()   # or point --data at a Drive path directly

# Cell 5 — train
!python train.py --data your_data.xlsx --epochs 80 --batch_size 128

# Cell 6 — copy artifacts back to Drive so they survive the session
!cp -r artifacts /content/drive/MyDrive/alternate_models_artifacts/01_gru_seq2seq
```

Colab's T4 has a real GPU; batch_size 128 or 256 will train noticeably
faster than the default 64 without hurting quality much — feel free to
raise it there.

## Parameters

```
--data           path to xlsx/csv (default: the synthetic smoke-test sample)
--sheet          sheet name, if the xlsx has multiple (default: first sheet)
--epochs         max epochs (default 60) — early stopping will likely stop sooner
--batch_size     default 64; raise to 128-256 on a real GPU
--patience       epochs without val_loss improvement before stopping (default 10)
```

## Outputs (`./artifacts/`)

- `model.keras` — the trained model, loadable with `tf.keras.models.load_model()`
- `scaler.pkl` — the fitted `MinMaxScaler` (needed at inference — see `../common/inference.py`)
- `feature_cols.json` — exact 12-feature order the model expects
- `metrics.json` — full R²/MAE/RMSE report (overall, per-target, per-lead-hour)
- `training_curve.png` — loss vs epoch (train + val)
- `per_hour_metrics.png` — MAE by lead hour 1-24, one panel per target
- `sample_predictions.png` — a few example predicted-vs-actual 24h windows

## After training

```bash
# from alternate_models/
python run_forecast.py 01_gru_seq2seq --district Colombo
python compare_with_openmeteo.py 01_gru_seq2seq --district Kandy
python leaderboard.py   # compare against the other 3 models, once trained
```
