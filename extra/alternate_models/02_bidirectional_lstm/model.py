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
