from __future__ import annotations

import logging

import numpy as np

from training.config import BIAS_FIT_FRACTION, MIN_ORIGINS_FOR_BIAS_FIT
from training.evaluate import mae, predict_real_units

log = logging.getLogger("trip_smart.training.bias_tables")

_ZERO_24 = [0.0] * 24

def regenerate(candidate_model, scaler, holdout: dict) -> tuple[dict, dict, dict]:
    districts = sorted(set(holdout["district"]))
    dist_arr = np.array(holdout["district"])

    temp_table: dict[str, list[float]] = {}
    hum_table: dict[str, list[float]] = {}
    report: dict[str, dict] = {}

    for district in districts:
        idx = np.where(dist_arr == district)[0]
        n = len(idx)

        if n < MIN_ORIGINS_FOR_BIAS_FIT:
            temp_table[district] = list(_ZERO_24)
            hum_table[district] = list(_ZERO_24)
            report[district] = {"n_origins": n, "status": "too few holdout origins, left uncorrected"}
            continue

        X_d, y_d = holdout["X"][idx], holdout["y"][idx]
        split = int(n * BIAS_FIT_FRACTION)
        fit_sl, eval_sl = slice(0, split), slice(split, n)

        pred = predict_real_units(candidate_model, X_d, scaler)
        temp_pred, hum_pred = pred[:, :, 0], pred[:, :, 2]
        temp_actual, hum_actual = y_d[:, :, 0], y_d[:, :, 2]

        temp_bias = np.mean(temp_actual[fit_sl] - temp_pred[fit_sl], axis=0)
        hum_bias = np.mean(hum_actual[fit_sl] - hum_pred[fit_sl], axis=0)

        temp_mae_raw = mae(temp_pred[eval_sl], temp_actual[eval_sl])
        temp_mae_corr = mae(temp_pred[eval_sl] + temp_bias, temp_actual[eval_sl])
        hum_mae_raw = mae(hum_pred[eval_sl], hum_actual[eval_sl])
        hum_mae_corr = mae(hum_pred[eval_sl] + hum_bias, hum_actual[eval_sl])

        use_temp = temp_mae_corr < temp_mae_raw
        use_hum = hum_mae_corr < hum_mae_raw

        temp_table[district] = [round(float(v), 3) for v in temp_bias] if use_temp else list(_ZERO_24)
        hum_table[district] = [round(float(v), 3) for v in hum_bias] if use_hum else list(_ZERO_24)

        report[district] = {
            "n_origins": n, "n_fit": split, "n_eval": n - split,
            "temp_mae_raw": round(temp_mae_raw, 3), "temp_mae_corrected": round(temp_mae_corr, 3),
            "use_temp_correction": use_temp,
            "hum_mae_raw": round(hum_mae_raw, 3), "hum_mae_corrected": round(hum_mae_corr, 3),
            "use_hum_correction": use_hum,
        }
        log.info("%s: temp correction %s, humidity correction %s (n=%d holdout origins)",
                  district, "kept" if use_temp else "dropped", "kept" if use_hum else "dropped", n)

    return temp_table, hum_table, report
