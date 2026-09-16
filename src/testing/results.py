import json
import random
import string
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from src.testing.sampler import SamplingResult


def _generate_result_id() -> str:
    """Timestamp + short random suffix - readable and sorts chronologically,
    while the suffix guarantees uniqueness even for runs in the same second."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{timestamp}_{suffix}"


def save_result(
    results_dir: str,
    ammeter_type: str,
    sampling_result: SamplingResult,
    stats: Dict[str, float],
    sampling_config: dict,
) -> str:
    """Persist a single test run (raw values + stats + metadata) as a JSON file.

    Returns the unique result_id (without the ammeter_type filename prefix),
    for use with load_result().
    """
    result_id = _generate_result_id()
    record = {
        "id": result_id,
        "timestamp": datetime.now().isoformat(),
        "ammeter_type": ammeter_type,
        "sampling_config": sampling_config,
        "attempts": sampling_result.attempts,
        "failures": sampling_result.failures,
        "success_rate": sampling_result.success_rate,
        "values": sampling_result.values,
        "stats": stats,
    }

    directory = Path(results_dir)
    directory.mkdir(parents=True, exist_ok=True)
    file_path = directory / f"{ammeter_type}_{result_id}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    return result_id


def list_results(results_dir: str) -> List[str]:
    """Return the filenames (without extension) of all stored results, most recent first."""
    directory = Path(results_dir)
    if not directory.exists():
        return []
    return sorted((path.stem for path in directory.glob("*.json")), reverse=True)


def load_result(results_dir: str, filename_stem: str) -> dict:
    """Load a previously saved result by its filename (without extension),
    e.g. the values returned by list_results()."""
    file_path = Path(results_dir) / f"{filename_stem}.json"
    if not file_path.exists():
        raise FileNotFoundError(f"No saved result found matching '{filename_stem}' in {results_dir}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
