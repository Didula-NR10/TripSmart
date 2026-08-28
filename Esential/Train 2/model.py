from __future__ import annotations

import numpy as np
import tensorflow as tf

from config import (
    DROPOUT_RATE, GRU1_UNITS, GRU2_UNITS, INPUT_WINDOW, L2_REG, LEARNING_RATE,
    RAIN_HIDDEN_UNITS,
)

def build_model(n_features: int) -> tf.keras.Model:
    reg = tf.keras.regularizers.l2(L2_REG)

    inputs = tf.keras.Input(shape=(INPUT_WINDOW, n_features), name="context_window")

    x = tf.keras.layers.GRU(GRU1_UNITS, return_sequences=True, kernel_regularizer=reg,
                              recurrent_regularizer=reg, name="rain_gru_1")(inputs)
    x = tf.keras.layers.Dropout(DROPOUT_RATE, name="rain_dropout_1")(x)
    x = tf.keras.layers.GRU(GRU2_UNITS, kernel_regularizer=reg, recurrent_regularizer=reg,
                              name="rain_gru_2")(x)
    x = tf.keras.layers.Dropout(DROPOUT_RATE, name="rain_dropout_2")(x)

    hidden = tf.keras.layers.Dense(RAIN_HIDDEN_UNITS, activation="relu", kernel_regularizer=reg,
                                     name="rain_hidden")(x)
    hidden = tf.keras.layers.Dropout(DROPOUT_RATE / 2, name="rain_hidden_dropout")(hidden)

    occurrence = tf.keras.layers.Dense(1, activation="sigmoid", kernel_regularizer=reg,
                                         name="rain_occurrence")(hidden)
    amount = tf.keras.layers.Dense(1, activation="relu", kernel_regularizer=reg,
                                     name="rain_amount")(hidden)

    return tf.keras.Model(
        inputs=inputs,
        outputs={"rain_occurrence": occurrence, "rain_amount": amount},
        name="TripSmart_Rain24h_Model",
    )

def weighted_occurrence_bce(pos_weight: float, neg_weight: float = 1.0):
    def loss(y_true, y_pred):
        y_true = tf.reshape(y_true, [-1])
        y_pred = tf.reshape(tf.clip_by_value(y_pred, 1e-7, 1 - 1e-7), [-1])
        return -(
            pos_weight * y_true * tf.math.log(y_pred)
            + neg_weight * (1 - y_true) * tf.math.log(1 - y_pred)
        )
    return loss

def occurrence_class_weights(occurrence_labels: np.ndarray, damping: float = 1.0) -> tuple[float, float]:
    n_pos = float(np.sum(occurrence_labels))
    n_neg = float(occurrence_labels.size - n_pos)
    if n_pos == 0 or n_neg == 0:
        return 1.0, 1.0
    pos_ratio = n_neg / n_pos
    neg_ratio = n_pos / n_neg
    pos_weight = max(1.0, 1.0 + (pos_ratio - 1.0) * damping)
    neg_weight = max(1.0, 1.0 + (neg_ratio - 1.0) * damping)
    return pos_weight, neg_weight

def compile_model(
    model: tf.keras.Model,
    pos_weight: float,
    neg_weight: float = 1.0,
    learning_rate: float = LEARNING_RATE,
):
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate, clipnorm=1.0),
        loss={"rain_occurrence": weighted_occurrence_bce(pos_weight, neg_weight), "rain_amount": "mse"},
        loss_weights={"rain_occurrence": 1.0, "rain_amount": 1.0},
    )
    return model

def best_threshold_by_f1(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    y_true_flat, y_prob_flat = y_true.ravel(), y_prob.ravel()
    best_t, best_f1 = 0.5, -1.0
    for t in np.linspace(0.01, 0.99, 99):
        pred = (y_prob_flat >= t).astype(int)
        tp = np.sum((pred == 1) & (y_true_flat == 1))
        fp = np.sum((pred == 1) & (y_true_flat == 0))
        fn = np.sum((pred == 0) & (y_true_flat == 1))
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        if f1 > best_f1:
            best_t, best_f1 = float(t), f1
    return best_t

def predict_rain(occurrence_prob: np.ndarray, amount_pred: np.ndarray, threshold: float) -> np.ndarray:
    return np.where(occurrence_prob >= threshold, np.clip(amount_pred, 0.0, None), 0.0)
