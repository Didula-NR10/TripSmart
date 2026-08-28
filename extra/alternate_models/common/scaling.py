from __future__ import annotations

import numpy as np
from sklearn.preprocessing import MinMaxScaler

def fit_scaler(X_train: np.ndarray) -> MinMaxScaler:
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
    n_samples, horizon, n_targets = y_scaled.shape
    idxs = target_indices(feature_cols, target_cols)
    n_features = len(feature_cols)

    placeholder = np.zeros((n_samples * horizon, n_features), dtype=np.float32)
    flat = y_scaled.reshape(-1, n_targets)
    for out_idx, feat_idx in enumerate(idxs):
        placeholder[:, feat_idx] = flat[:, out_idx]

    real = scaler.inverse_transform(placeholder)
    return real[:, idxs].reshape(n_samples, horizon, n_targets)
