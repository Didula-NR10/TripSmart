from __future__ import annotations

import logging

import numpy as np

from training.config import (
    EARLY_STOPPING_PATIENCE,
    FINE_TUNE_BATCH_SIZE,
    FINE_TUNE_LR,
    FINE_TUNE_MAX_EPOCHS,
)

log = logging.getLogger("trip_smart.training.finetune")

def fine_tune(current_model, X_train: np.ndarray, y_train: np.ndarray,
              X_val: np.ndarray, y_val: np.ndarray):
    import tensorflow as tf

    candidate = tf.keras.models.clone_model(current_model)
    candidate.set_weights(current_model.get_weights())
    candidate.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=FINE_TUNE_LR),
        loss="mse",
        metrics=["mae"],
    )

    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=EARLY_STOPPING_PATIENCE, restore_best_weights=True,
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=max(2, EARLY_STOPPING_PATIENCE // 2),
        ),
    ]

    log.info("Fine-tuning: %d train windows, %d val windows, lr=%s, up to %d epochs.",
              len(X_train), len(X_val), FINE_TUNE_LR, FINE_TUNE_MAX_EPOCHS)

    history = candidate.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=FINE_TUNE_MAX_EPOCHS,
        batch_size=FINE_TUNE_BATCH_SIZE,
        callbacks=callbacks,
        verbose=2,
    )

    return candidate, history.history
