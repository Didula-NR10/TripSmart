"""
02_bidirectional_lstm/model.py
─────────────────────────────────
Bidirectional stacked LSTM encoder + GRU-style RepeatVector decoder.

Two things differ from both the production model and 01_gru_seq2seq:

1. LSTM instead of GRU — a separate cell state alongside the hidden state,
   with an explicit forget gate. Usually similar to GRU in practice but
   sometimes better at retaining longer-range dependencies (relevant here:
   168 hours is a long context, and the diurnal pattern ~24 steps back and
   the "same time yesterday" ~24 steps back are both worth remembering).

2. Bidirectional encoder — reads the 168h context both forward and
   backward before compressing it. The model can't do this at INFERENCE
   for the horizon it's predicting (the future hasn't happened), but for
   the ENCODER — which only ever looks at the past, already-known 168h
   window — reading it in both directions lets, e.g., hour 100's
   representation be informed by hour 105 as well as hour 95, which can
   help the model place where "now" sits within the recent trend before
   it starts forecasting forward.
"""
from __future__ import annotations

import tensorflow as tf
from tensorflow.keras import layers, models


def build_model(
    input_window: int,
    n_features: int,
    horizon: int,
    n_targets: int,
    encoder_units: int = 96,
    decoder_units: int = 96,
    dropout: float = 0.25,
) -> tf.keras.Model:
    inputs = layers.Input(shape=(input_window, n_features), name="context_window")

    x = layers.Bidirectional(
        layers.LSTM(encoder_units, return_sequences=True), name="bidir_lstm_1"
    )(inputs)
    x = layers.Dropout(dropout, name="encoder_dropout_1")(x)

    x = layers.Bidirectional(
        layers.LSTM(encoder_units, return_sequences=False), name="bidir_lstm_2"
    )(x)
    x = layers.Dropout(dropout, name="encoder_dropout_2")(x)

    context = layers.RepeatVector(horizon, name="repeat_context")(x)
    decoded = layers.LSTM(decoder_units, return_sequences=True, name="decoder_lstm")(context)
    decoded = layers.Dropout(dropout, name="decoder_dropout")(decoded)

    outputs = layers.TimeDistributed(layers.Dense(n_targets), name="forecast_output")(decoded)

    model = models.Model(inputs, outputs, name="BiLSTM_Seq2Seq_Forecaster")
    return model
