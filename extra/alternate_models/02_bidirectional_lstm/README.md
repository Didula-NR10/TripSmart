# 02_bidirectional_lstm — bidirectional stacked LSTM

A different recurrent cell (LSTM instead of GRU) plus a bidirectional
encoder — two changes bundled into one folder so you can see whether either
helps on your data, versus the plain GRU seq2seq in `01_gru_seq2seq`.

## Why this might do better (or worse)

- **LSTM vs GRU**: LSTM has a separate cell state and an explicit forget
  gate, on top of the hidden state GRU also has. In practice the two are
  often similar, but LSTM sometimes retains longer-range dependencies
  better — relevant here since 168 hours is a long context and "the same
  hour yesterday" (24 steps back) or "the same hour last week" (168 steps
  back) are both worth the model remembering clearly.
- **Bidirectional encoder**: reads the 168h context both forward and
  backward before compressing it into a decoder-initializing vector. This
  is only possible on the ENCODER side (the ever-already-known past) — the
  decoder still only unrolls forward, since the future hasn't happened.
  Reading the context both ways lets, e.g., hour 100's representation be
  informed by hour 105 as well as hour 95, which can help the model place
  "where we are" in the recent trend before forecasting forward.

Trade-off: bidirectional roughly doubles the recurrent compute of the
encoder layers, and LSTM has ~4/3 the gate parameters of GRU per unit — this
is the heaviest-per-epoch of the three deep models here (416,931 trainable
params). If it doesn't beat `01_gru_seq2seq` on your data, that's a
legitimate result — see `../leaderboard.py`.

## Steps — local (uses the repo's existing venv)

```bash
cd extra/alternate_models/02_bidirectional_lstm

# smoke test first (optional but recommended)
cd ../common && ../../../venv/Scripts/python.exe make_synthetic_data.py && cd ../02_bidirectional_lstm
../../../venv/Scripts/python.exe train.py --epochs 3

# real training run
../../../venv/Scripts/python.exe train.py --data path/to/your_data.xlsx --epochs 60
```

Expect this one to be the slowest locally on CPU of the three deep models —
Colab's free GPU is strongly recommended for a real run here specifically.

## Steps — Google Colab (free tier, T4 GPU)

```python
# Cell 1 — mount Drive
from google.colab import drive
drive.mount('/content/drive')

# Cell 2 — get the code onto Colab
!unzip /content/drive/MyDrive/alternate_models.zip -d /content/

# Cell 3 — install dependencies
%cd /content/alternate_models/02_bidirectional_lstm
!pip install -q -r ../common/requirements.txt

# Cell 4 — upload your xlsx
from google.colab import files
uploaded = files.upload()

# Cell 5 — train
!python train.py --data your_data.xlsx --epochs 80 --batch_size 128

# Cell 6 — copy artifacts back to Drive
!cp -r artifacts /content/drive/MyDrive/alternate_models_artifacts/02_bidirectional_lstm
```

## Parameters

```
--data           path to xlsx/csv (default: the synthetic smoke-test sample)
--sheet          sheet name, if the xlsx has multiple (default: first sheet)
--epochs         max epochs (default 60)
--batch_size     default 64; raise to 128-256 on a real GPU
--patience       epochs without val_loss improvement before stopping (default 10)
```

## Outputs (`./artifacts/`)

Same set as `01_gru_seq2seq`: `model.keras`, `scaler.pkl`,
`feature_cols.json`, `metrics.json`, `training_curve.png`,
`per_hour_metrics.png`, `sample_predictions.png`.

## After training

```bash
# from alternate_models/
python run_forecast.py 02_bidirectional_lstm --district Colombo
python compare_with_openmeteo.py 02_bidirectional_lstm --district Kandy
python leaderboard.py
```
