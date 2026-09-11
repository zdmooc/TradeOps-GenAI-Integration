# I5 — ML Signal Quality and Calibration

## Purpose

I5 ranks signal quality without moving deterministic market calculations, pattern detection, or risk vetoes into ML. The ML target is deliberately narrower: estimate whether an already-defined setup has favorable outcome quality (the synthetic I5 label represents TP-before-SL quality).

An uncalibrated classifier output is treated as a **score**, even when the underlying library exposes it through `predict_proba`. The runtime emits a probability-qualified status only after disjoint calibration and final chronological test checks.

## Feature contract

The versioned `i5-v1` contract uses only point-in-time features available at the feature timestamp:

- RSI, MACD histogram, ATR %, ADX;
- EMA slope and VWAP distance;
- volatility and volume z-score;
- market-structure and pattern scores;
- relative strength;
- session and regime encodings;
- distance to level in ATR units;
- spread, latency and data-quality score.

Names containing forward/outcome semantics such as `future`, `target`, `label`, `exit`, `pnl`, `profit`, `mfe`, `mae` or `tp_before_sl` are rejected by the feature contract. Each label timestamp must be strictly later than its feature cutoff.

## Temporal experiment discipline

The pinned experiment has no shuffle:

1. train 50%;
2. validation 20% for baseline selection;
3. calibration 15% for Platt fitting;
4. test 15% for final untouched metrics.

The fixed synthetic dataset contains 480 records, so the final test contains 72 observations.

Walk-forward windows use separate train / validation / calibration / test blocks. If a calibration block contains only one class, that window remains `score-only`; the code never fabricates a probability calibration from a degenerate sample.

## Baselines

I5 executes four deterministic-seed baselines:

- scikit-learn logistic regression;
- scikit-learn histogram gradient boosting;
- XGBoost;
- LightGBM.

Selection uses validation ROC-AUC first and Brier score as the deterministic tie-break. The champion is then frozen before the separate calibration and test segments are used.

## Calibration and probability gate

Platt scaling is fitted only on the calibration segment. Final metrics are measured only on the test segment:

- ROC-AUC;
- Brier score;
- log loss;
- expected calibration error (ECE);
- accuracy, precision and recall;
- observed positive rate and mean score.

The probability gate requires:

- at least 40 final-test observations;
- ECE <= 0.15;
- positive Brier skill versus the prevalence-only baseline;
- ROC-AUC above 0.5;
- no feature-drift ALERT.

For the versioned synthetic fixture, a passing result is labelled `CALIBRATED_OUT_OF_SAMPLE_SYNTHETIC`. This is calibration evidence for the implementation only. It is **not** permission to describe live-market model outputs as calibrated probabilities.

## Drift monitoring

I5 computes PSI and standardized mean shift for every feature. The current policy is:

- OK below PSI 0.10 and mean shift 0.5;
- WATCH at PSI >= 0.10 or mean shift >= 0.5;
- ALERT at PSI >= 0.25 or mean shift >= 1.0.

A drift ALERT demotes the experiment to `SCORE_ONLY` even if classification/calibration metrics otherwise pass.

## MLflow

The runtime includes a real MLflow integration that logs:

- dataset hash and feature-contract version;
- champion/calibration parameters;
- raw and calibrated test metrics;
- full I5 report artifact;
- the serialized calibrated model;
- a registered model version with qualification tags.

Tests use an isolated local MLflow store. Production architecture should use a remote tracking server and governed registry backend.

## Reproducibility

The synthetic dataset spec is checked into `data/ml/i5_signal_quality_dataset.json`; it pins the seed, time origin, frequency, label horizon and generator version. The generated canonical records are hashed before training. The protocol is pinned in `experiments/i5_signal_quality_protocol.json`.

## Non-claims

I5 does not claim:

- live or historical-market profitability;
- real-market calibrated probability;
- a production feature store;
- statistically stable alpha from the synthetic fixture;
- live execution authorization;
- any ability for ML to override the deterministic I3 risk veto.

Feast remains deferred because I5 does not yet demonstrate a real online/offline feature-consistency problem requiring a feature-store dependency.
