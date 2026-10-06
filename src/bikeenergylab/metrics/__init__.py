"""Point and distribution metrics; undefined denominators stay explicit."""

import numpy as np


def point_metrics(observed: np.ndarray, predicted: np.ndarray) -> dict[str, float | None]:
    observed, predicted = np.asarray(observed, float), np.asarray(predicted, float)
    if (
        observed.shape != predicted.shape
        or not len(observed)
        or not np.isfinite([observed, predicted]).all()
    ):
        raise ValueError("Metrics require equal, nonempty finite vectors")
    error = predicted - observed
    denominator = np.sum((observed - observed.mean()) ** 2)
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "r2": float(1 - np.sum(error**2) / denominator) if denominator > 1e-12 else None,
    }


def interval_metrics(
    observed: np.ndarray, lower: np.ndarray, upper: np.ndarray
) -> dict[str, float]:
    observed, lower, upper = map(lambda a: np.asarray(a, float), [observed, lower, upper])
    if (
        observed.shape != lower.shape
        or lower.shape != upper.shape
        or not len(observed)
        or not np.isfinite([observed, lower, upper]).all()
        or np.any(lower > upper)
    ):
        raise ValueError("Invalid interval arrays")
    return {
        "coverage": float(np.mean((observed >= lower) & (observed <= upper))),
        "interval_width": float(np.mean(upper - lower)),
    }


def empirical_crps(samples: np.ndarray, observation: float) -> float:
    """Exact empirical CRPS in O(n log n), without quadratic pairwise allocation."""
    values = np.sort(np.asarray(samples, float))
    if (
        values.ndim != 1
        or not len(values)
        or not np.isfinite(values).all()
        or not np.isfinite(observation)
    ):
        raise ValueError("Finite nonempty one-dimensional predictive samples required")
    n = len(values)
    return float(
        np.mean(np.abs(values - observation))
        - np.sum((2 * np.arange(1, n + 1) - n - 1) * values) / (n * n)
    )
