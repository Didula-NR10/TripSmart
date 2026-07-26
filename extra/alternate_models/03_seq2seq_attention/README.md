# 03_seq2seq_attention — encoder-decoder GRU with Luong attention

The most sophisticated of the three deep models here, and the one most
likely to beat both production and `01_gru_seq2seq` — IF there's enough
training data to justify the extra parameters.

## Why this might do better

`01_gru_seq2seq`'s decoder only ever sees a single fixed context vector
(the encoder's final state) at all 24 of its decode steps — all 168 hours
of history have to be compressed into that one vector up front, and every
forecast hour draws on exactly the same summary.

This model adds **attention**: at each of the 24 decode steps, the decoder
additionally looks back across ALL 168 encoder hours and computes a
weighted combination of them, with the weights learned to be relevant to
THAT specific step. Concretely, hour+1 (tonight) can learn to attend mostly
to the last few observed hours, while hour+24 (this time tomorrow) can
learn to attend more to the same hour-of-day roughly a week back in the
context window — without being told to do that explicitly; it emerges from
training. This is the same mechanism that gave a large step up over plain
encoder-decoder RNNs in machine translation, applied here to a weather
series instead of language.

188,035 trainable params — see `model.py` for the exact attention wiring
(`tf.keras.layers.Attention`, Luong-style dot-product) and more detail.

## Trade-off

More compute per step than `01_gru_seq2seq` (attention has to score every
one of 168 encoder positions at each of 24 decode steps) — the heaviest per-epoch of the
three deep models on top of being architecturally the most complex. Worth
it only with enough data (a few years, ideally many districts) for the
extra capacity to generalize instead of overfit. If it doesn't beat
`01_gru_seq2seq` on the leaderboard, that's a legitimate, useful result —
it tells you the simpler model was already sufficient for your data size.

## Steps — local (uses the repo's existing venv)

```bash
cd extra/alternate_models/03_seq2seq_attention

# smoke test first (optional but recommended)
cd ../common && ../../../venv/Scripts/python.exe make_synthetic_data.py && cd ../03_seq2seq_attention
../../../venv/Scripts/python.exe train.py --epochs 3

# real training run
../../../venv/Scripts/python.exe train.py --data path/to/your_data.xlsx --epochs 60
```

This is the one most likely to feel slow on an i5 3rd-gen / GTX 960 4GB
machine for a real run — Colab's free GPU is recommended.

## Steps — Google Colab (free tier, T4 GPU)

```python
# Cell 1 — mount Drive
from google.colab import drive
drive.mount('/content/drive')

# Cell 2 — get the code onto Colab
!unzip /content/drive/MyDrive/alternate_models.zip -d /content/

# Cell 3 — install dependencies
%cd /content/alternate_models/03_seq2seq_attention
!pip install -q -r ../common/requirements.txt

# Cell 4 — upload your xlsx
from google.colab import files
uploaded = files.upload()

# Cell 5 — train
!python train.py --data your_data.xlsx --epochs 80 --batch_size 128

# Cell 6 — copy artifacts back to Drive
!cp -r artifacts /content/drive/MyDrive/alternate_models_artifacts/03_seq2seq_attention
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

Same set as the other deep models: `model.keras`, `scaler.pkl`,
`feature_cols.json`, `metrics.json`, `training_curve.png`,
`per_hour_metrics.png`, `sample_predictions.png`.

## After training

```bash
# from alternate_models/
python run_forecast.py 03_seq2seq_attention --district Colombo
python compare_with_openmeteo.py 03_seq2seq_attention --district Kandy
python leaderboard.py
```
