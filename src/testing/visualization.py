from pathlib import Path
from typing import List

# The Agg backend renders to files without a display, which is required here
# because plots are generated on a background/headless run, not shown on screen.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def generate_plots(
    values: List[float],
    ammeter_type: str,
    result_id: str,
    output_dir: str,
    plot_types: List[str],
) -> List[str]:
    """Render the requested plots for one test run and return the saved file paths.

    `plot_types` are the names from config.yaml (analysis.visualization.plot_types);
    currently 'line' (measurements over time) and 'histogram' (value distribution).
    Unknown plot types are ignored so a config typo never aborts a completed run.
    """
    if not values:
        return []

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    saved: List[str] = []

    if "line" in plot_types:
        saved.append(_plot_line(values, ammeter_type, result_id, directory))
    if "histogram" in plot_types:
        saved.append(_plot_histogram(values, ammeter_type, result_id, directory))

    return saved


def _plot_line(values: List[float], ammeter_type: str, result_id: str, directory: Path) -> str:
    file_path = directory / f"{ammeter_type}_{result_id}_line.png"
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(range(1, len(values) + 1), values, marker=".", linewidth=1)
    ax.set_title(f"{ammeter_type} - current over samples")
    ax.set_xlabel("Sample #")
    ax.set_ylabel("Current (A)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(file_path)
    plt.close(fig)
    return str(file_path)


def _plot_histogram(values: List[float], ammeter_type: str, result_id: str, directory: Path) -> str:
    file_path = directory / f"{ammeter_type}_{result_id}_histogram.png"
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(values, bins=min(20, len(values)), edgecolor="black", alpha=0.75)
    ax.set_title(f"{ammeter_type} - current distribution")
    ax.set_xlabel("Current (A)")
    ax.set_ylabel("Frequency")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(file_path)
    plt.close(fig)
    return str(file_path)
