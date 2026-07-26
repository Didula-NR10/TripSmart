"""
03_seq2seq_attention/model.py
─────────────────────────────────
Encoder-decoder GRU with Luong-style (dot-product) attention — the most
sophisticated of the three deep models here, and the one most likely to
beat both the production model and 01_gru_seq2seq if there's enough
training data to support the extra parameters.

Why attention helps for this problem specifically: 01_gru_seq2seq's decoder
only sees a single fixed context vector (the encoder's final state) at
every one of its 24 decode steps — it has to compress all 168 hours of
history into that one vector up front. With attention, at each decode step
t the decoder additionally gets to look back across ALL 168 encoder hours
and weight them by relevance to predicting THAT specific step — e.g. hour
+1 (tonight) can attend most to the last few observed hours, while hour +24
(this time tomorrow) can attend more to the same hour-of-day about a week
back in the context window, without the model being told to do that
explicitly. This is the same mechanism that made attention-based sequence
models a large step up over plain encoder-decoder RNNs in machine
translation, applied here to a weather time series instead of language.

Trade-off: more parameters and compute than 01/02 — worth it only if you
have enough training data (a few years, ideally several districts) for the
extra capacity to pay off rather than overfit. If 03 doesn't beat 01 on
your data, that's a legitimate result (see the top-level README's
leaderboard), not a sign anything is broken.
"""
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

    # Encoder: keep the FULL sequence of hidden states (attention needs
    # every timestep, not just the final one) as well as the final state
    # (used to initialize the decoder, same as 01_gru_seq2seq).
    enc_seq_1 = layers.GRU(encoder_units, return_sequences=True, name="encoder_gru_1")(inputs)
    enc_seq_1 = layers.Dropout(dropout, name="encoder_dropout_1")(enc_seq_1)
    encoder_seq, encoder_state = layers.GRU(
        decoder_units, return_sequences=True, return_state=True, name="encoder_gru_2"
    )(enc_seq_1)

    # Decoder: unrolls `horizon` steps, initialized from the encoder's final
    # state, fed the pooled context at every step (as in 01_gru_seq2seq) —
    # the addition here is the attention block right after.
    pooled_context = layers.GlobalAveragePooling1D(name="encoder_pool")(encoder_seq)
    repeated_context = layers.RepeatVector(horizon, name="repeat_context")(pooled_context)
    decoder_seq = layers.GRU(
        decoder_units, return_sequences=True, name="decoder_gru"
    )(repeated_context, initial_state=encoder_state)

    # Luong-style dot-product attention: for each of the 24 decoder steps
    # (query), attend over all 168 encoder steps (value/key) and return a
    # weighted combination — lets each forecast hour pull from whichever
    # part of the 168h history is most relevant to IT specifically.
    attended = layers.Attention(name="luong_attention")([decoder_seq, encoder_seq])

    merged = layers.Concatenate(name="decoder_plus_attention")([decoder_seq, attended])
    merged = layers.Dropout(dropout, name="decoder_dropout")(merged)
    merged = layers.TimeDistributed(layers.Dense(64, activation="relu"), name="post_attention_dense")(merged)

    outputs = layers.TimeDistributed(layers.Dense(n_targets), name="forecast_output")(merged)

    model = models.Model(inputs, outputs, name="GRU_Seq2Seq_Attention_Forecaster")
    return model
