"""
alternate_models/common/scaling.py
─────────────────────────────────────
Same scaling strategy as production (Backend/forecast/utils.py /
core/database scaler.pkl): ONE MinMaxScaler fit on the full feature matrix
(all feature_cols, train split only), used both to scale model inputs and
— via a zero-placeholder trick — to inverse-transform the model's scaled
target outputs back to real units, since the 3 targets are a subset of the
scaled feature space rather than a separately-scaled space.

Fitting only on the training split (never val/test) matters: it's the same
reason you never peek at test data during feature engineering — a scaler
fit on the full dataset leaks future distribution info into training.
"""
from __future__ import annotations

import numpy as np
from sklearn.preprocessing import MinMaxScaler


def fit_scaler(X_train: np.ndarray) -> MinMaxScaler:
    """X_train: (n_samples, input_window, n_features). Fits on all rows of
    all training windows flattened to (n_samples * input_window, n_features)."""
    n_samples, window, n_features = X_train.shape
    flat = X_train.reshape(-1, n_features)
    scaler = MinMaxScaler()
    scaler.fit(flat)
    return scaler


def scale_windows(X: np.ndarray, scaler: MinMaxScaler) -> np.ndarray:
    n_samples, window, n_features = X.shape
    flat = X.reshape(-1, n_features)
    scaled = scaler.transform(flat).astype(np.float32)
    return scaled.reshape(n_samples, window, n_features)


def target_indices(feature_cols: list[str], target_cols: list[str]) -> list[int]:
    return [feature_cols.index(c) for c in target_cols]


def scale_targets(y: np.ndarray, scaler: MinMaxScaler, feature_cols: list[str],
                   target_cols: list[str]) -> np.ndarray:
    """y: (n_samples, horizon, n_targets) real units -> scaled, for training
    a model whose loss is computed in scaled space (keeps gradients well
    behaved across features with very different real-world ranges)."""
    n_samples, horizon, n_targets = y.shape
    idxs = target_indices(feature_cols, target_cols)
    n_features = len(feature_cols)

    placeholder = np.zeros((n_samples * horizon, n_features), dtype=np.float32)
    flat_y = y.reshape(-1, n_targets)
    for out_idx, feat_idx in enumerate(idxs):
        placeholder[:, feat_idx] = flat_y[:, out_idx]

    scaled = scaler.transform(placeholder)
    return scaled[:, idxs].reshape(n_samples, horizon, n_targets).astype(np.float32)


def inverse_transform_targets(y_scaled: np.ndarray, scaler: MinMaxScaler,
                               feature_cols: list[str], target_cols: list[str]) -> np.ndarray:
    """y_scaled: (n_samples, horizon, n_targets) scaled -> real units."""
    n_samples, horizon, n_targets = y_scaled.shape
    idxs = target_indices(feature_cols, target_cols)
    n_features = len(feature_cols)

    placeholder = np.zeros((n_samples * horizon, n_features), dtype=np.float32)
    flat = y_scaled.reshape(-1, n_targets)
    for out_idx, feat_idx in enumerate(idxs):
        placeholder[:, feat_idx] = flat[:, out_idx]

    real = scaler.inverse_transform(placeholder)
    return real[:, idxs].reshape(n_samples, horizon, n_targets)
