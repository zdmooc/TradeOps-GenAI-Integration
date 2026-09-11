from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)


def expected_calibration_error(
    y_true: np.ndarray, probabilities: np.ndarray, bins: int = 10
) -> float:
    if bins < 2:
        raise ValueError("bins must be >= 2")
    probabilities = np.clip(np.asarray(probabilities, dtype=float), 0.0, 1.0)
    y_true = np.asarray(y_true, dtype=int)
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = len(y_true)
    ece = 0.0
    for index in range(bins):
        lower = edges[index]
        upper = edges[index + 1]
        if index == bins - 1:
            mask = (probabilities >= lower) & (probabilities <= upper)
        else:
            mask = (probabilities >= lower) & (probabilities < upper)
        if not np.any(mask):
            continue
        confidence = float(np.mean(probabilities[mask]))
        accuracy = float(np.mean(y_true[mask]))
        ece += float(np.sum(mask)) / total * abs(confidence - accuracy)
    return float(ece)


def binary_classification_metrics(
    y_true: np.ndarray, scores: np.ndarray, threshold: float = 0.5
) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=int)
    scores = np.clip(np.asarray(scores, dtype=float), 1e-9, 1.0 - 1e-9)
    predictions = (scores >= threshold).astype(int)
    auc = 0.5
    if len(np.unique(y_true)) == 2:
        auc = float(roc_auc_score(y_true, scores))
    return {
        "accuracy": float(accuracy_score(y_true, predictions)),
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "roc_auc": auc,
        "brier": float(brier_score_loss(y_true, scores)),
        "log_loss": float(log_loss(y_true, scores, labels=[0, 1])),
        "ece": expected_calibration_error(y_true, scores),
        "positive_rate": float(np.mean(y_true)),
        "mean_score": float(np.mean(scores)),
        "n": float(len(y_true)),
    }
