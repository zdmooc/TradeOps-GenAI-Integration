from __future__ import annotations

from collections.abc import Callable
from typing import Any

from lightgbm import LGBMClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier


EstimatorFactory = Callable[[], Any]


def baseline_factories(seed: int = 20260911) -> dict[str, EstimatorFactory]:
    return {
        "sklearn_logistic": lambda: Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        max_iter=1000,
                        random_state=seed,
                        solver="lbfgs",
                    ),
                ),
            ]
        ),
        "sklearn_hist_gradient_boosting": lambda: HistGradientBoostingClassifier(
            learning_rate=0.06,
            max_iter=80,
            max_depth=4,
            l2_regularization=0.5,
            random_state=seed,
        ),
        "xgboost": lambda: XGBClassifier(
            n_estimators=80,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.0,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=seed,
            n_jobs=1,
            tree_method="hist",
        ),
        "lightgbm": lambda: LGBMClassifier(
            n_estimators=80,
            num_leaves=15,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.0,
            random_state=seed,
            n_jobs=1,
            verbosity=-1,
            deterministic=True,
            force_col_wise=True,
        ),
    }


def positive_class_score(model: Any, matrix: Any) -> Any:
    probabilities = model.predict_proba(matrix)
    return probabilities[:, 1]
