from __future__ import annotations

import tensorflow as tf
from tensorflow.keras import layers, models

def build_model(
    input_window: int,
    n_features: int,
    horizon: int,
    n_targets: int,
    encoder_units: int = 128,
    decoder_units: int = 96,
    dropout: float = 0.2,
) -> tf.keras.Model:
    inputs = layers.Input(shape=(input_window, n_features), name="context_window")

    x = layers.GRU(encoder_units, return_sequences=True, name="encoder_gru_1")(inputs)
    x = layers.Dropout(dropout, name="encoder_dropout_1")(x)
    _, encoder_state = layers.GRU(decoder_units, return_state=True, name="encoder_gru_2")(x)

    context = layers.RepeatVector(horizon, name="repeat_context")(
        layers.GlobalAveragePooling1D(name="encoder_pool")(x)
    )
    decoded = layers.GRU(decoder_units, return_sequences=True, name="decoder_gru")(
        context, initial_state=encoder_state
    )
    decoded = layers.Dropout(dropout, name="decoder_dropout")(decoded)

    outputs = layers.TimeDistributed(layers.Dense(n_targets), name="forecast_output")(decoded)

    model = models.Model(inputs, outputs, name="GRU_Seq2Seq_Forecaster")
    return model
