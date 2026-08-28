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
    dropout: float = 0.25,
) -> tf.keras.Model:
    inputs = layers.Input(shape=(input_window, n_features), name="context_window")

    enc_seq_1 = layers.GRU(encoder_units, return_sequences=True, name="encoder_gru_1")(inputs)
    enc_seq_1 = layers.Dropout(dropout, name="encoder_dropout_1")(enc_seq_1)
    encoder_seq, encoder_state = layers.GRU(
        decoder_units, return_sequences=True, return_state=True, name="encoder_gru_2"
    )(enc_seq_1)

    pooled_context = layers.GlobalAveragePooling1D(name="encoder_pool")(encoder_seq)
    repeated_context = layers.RepeatVector(horizon, name="repeat_context")(pooled_context)
    decoder_seq = layers.GRU(
        decoder_units, return_sequences=True, name="decoder_gru"
    )(repeated_context, initial_state=encoder_state)

    attended = layers.Attention(name="luong_attention")([decoder_seq, encoder_seq])

    merged = layers.Concatenate(name="decoder_plus_attention")([decoder_seq, attended])
    merged = layers.Dropout(dropout, name="decoder_dropout")(merged)
    merged = layers.TimeDistributed(layers.Dense(64, activation="relu"), name="post_attention_dense")(merged)

    outputs = layers.TimeDistributed(layers.Dense(n_targets), name="forecast_output")(merged)

    model = models.Model(inputs, outputs, name="GRU_Seq2Seq_Attention_Forecaster")
    return model
