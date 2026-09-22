import statistics
from typing import Dict, List, Optional

# Maps a config-facing metric name (config.yaml -> analysis.statistical_metrics)
# to how it's computed from a list of successful measurement values.
_METRIC_FUNCTIONS = {
    "mean": statistics.mean,
    "median": statistics.median,
    "min": min,
    "max": max,
}


def analyze(values: List[float], metrics: List[str]) -> Dict[str, Optional[float]]:
    """Compute the requested statistical metrics over `values`.

    `metrics` are names from config.yaml's analysis.statistical_metrics.
    std_dev requires at least 2 values; with fewer, its value is None instead
    of failing the whole analysis (mean/median/min/max still work with n=1).
    consistency_cv (coefficient of variation = std_dev / mean) is a unitless
    measure of how consistent the measurements are relative to their size -
    lower means more consistent. It is None under the same n<2 condition as
    std_dev, and also None if the mean is 0 (division by zero).
    """
    if not values:
        raise ValueError("Cannot compute statistics on an empty list of measurements.")

    known_metrics = set(_METRIC_FUNCTIONS) | {"std_dev", "consistency_cv"}
    unknown = [metric for metric in metrics if metric not in known_metrics]
    if unknown:
        raise ValueError(f"Unknown statistical metric(s) {unknown} in config.yaml. Known metrics: {sorted(known_metrics)}")

    results: Dict[str, Optional[float]] = {}
    for metric in metrics:
        if metric == "std_dev":
            results[metric] = statistics.stdev(values) if len(values) >= 2 else None
        elif metric == "consistency_cv":
            results[metric] = _coefficient_of_variation(values)
        else:
            results[metric] = _METRIC_FUNCTIONS[metric](values)
    return results


def _coefficient_of_variation(values: List[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    mean = statistics.mean(values)
    if mean == 0:
        return None
    return statistics.stdev(values) / mean
