from __future__ import annotations

import numpy as np

from .models import DriftFeature, DriftReport


def _psi(reference: np.ndarray, current: np.ndarray, bins: int = 5) -> float:
    quantiles = np.linspace(0.0, 1.0, bins + 1)
    edges = np.unique(np.quantile(reference, quantiles))
    if len(edges) < 3:
        return 0.0
    edges[0] = -np.inf
    edges[-1] = np.inf
    ref_counts, _ = np.histogram(reference, bins=edges)
    cur_counts, _ = np.histogram(current, bins=edges)
    epsilon = 1e-6
    ref_pct = np.maximum(ref_counts / max(1, ref_counts.sum()), epsilon)
    cur_pct = np.maximum(cur_counts / max(1, cur_counts.sum()), epsilon)
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def compute_drift(
    reference_matrix: np.ndarray,
    current_matrix: np.ndarray,
    feature_names: tuple[str, ...],
) -> DriftReport:
    if reference_matrix.shape[1] != current_matrix.shape[1]:
        raise ValueError("reference/current feature dimensions differ")
    if reference_matrix.shape[1] != len(feature_names):
        raise ValueError("feature_names length does not match matrix width")
    features: list[DriftFeature] = []
    for index, name in enumerate(feature_names):
        reference = reference_matrix[:, index]
        current = current_matrix[:, index]
        std = float(np.std(reference))
        mean_shift = (
            0.0
            if std < 1e-12
            else float(abs(np.mean(current) - np.mean(reference)) / std)
        )
        psi = _psi(reference, current)
        status = "OK"
        if psi >= 0.25 or mean_shift >= 1.0:
            status = "ALERT"
        elif psi >= 0.10 or mean_shift >= 0.5:
            status = "WATCH"
        features.append(
            DriftFeature(
                feature=name,
                psi=psi,
                standardized_mean_shift=mean_shift,
                status=status,
            )
        )
    overall = "OK"
    if any(item.status == "ALERT" for item in features):
        overall = "ALERT"
    elif any(item.status == "WATCH" for item in features):
        overall = "WATCH"
    return DriftReport(
        overall_status=overall,
        max_psi=max((item.psi for item in features), default=0.0),
        features=tuple(features),
    )
