from __future__ import annotations

from .models import TemporalMLSplit, WalkForwardMLWindow


def temporal_train_validation_calibration_test_split(
    n_records: int,
    train_fraction: float = 0.50,
    validation_fraction: float = 0.20,
    calibration_fraction: float = 0.15,
) -> TemporalMLSplit:
    if n_records < 20:
        raise ValueError("at least 20 records are required")
    fractions = (train_fraction, validation_fraction, calibration_fraction)
    if any(value <= 0.0 for value in fractions):
        raise ValueError("split fractions must be > 0")
    if sum(fractions) >= 1.0:
        raise ValueError("train+validation+calibration fractions must be < 1")
    train_end = max(1, int(n_records * train_fraction))
    validation_end = max(train_end + 1, train_end + int(n_records * validation_fraction))
    calibration_end = max(
        validation_end + 1,
        validation_end + int(n_records * calibration_fraction),
    )
    if calibration_end >= n_records:
        raise ValueError("test split would be empty")
    return TemporalMLSplit(
        train=(0, train_end - 1),
        validation=(train_end, validation_end - 1),
        calibration=(validation_end, calibration_end - 1),
        test=(calibration_end, n_records - 1),
    )


def slice_for(indices: tuple[int, int]) -> slice:
    return slice(indices[0], indices[1] + 1)


def walk_forward_ml_windows(
    n_records: int,
    train_records: int,
    validation_records: int,
    calibration_records: int,
    test_records: int,
    step_records: int | None = None,
) -> tuple[WalkForwardMLWindow, ...]:
    values = (train_records, validation_records, calibration_records, test_records)
    if any(value < 1 for value in values):
        raise ValueError("all window sizes must be >= 1")
    step = test_records if step_records is None else step_records
    if step < 1:
        raise ValueError("step_records must be >= 1")
    width = sum(values)
    windows: list[WalkForwardMLWindow] = []
    start = 0
    window_id = 1
    while start + width <= n_records:
        train = (start, start + train_records - 1)
        validation = (train[1] + 1, train[1] + validation_records)
        calibration = (validation[1] + 1, validation[1] + calibration_records)
        test = (calibration[1] + 1, calibration[1] + test_records)
        windows.append(
            WalkForwardMLWindow(
                window_id=window_id,
                train=train,
                validation=validation,
                calibration=calibration,
                test=test,
            )
        )
        start += step
        window_id += 1
    return tuple(windows)
