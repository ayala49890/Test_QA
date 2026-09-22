import sys
import threading
import time
from pathlib import Path

# Make the repo root importable regardless of the current working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Ammeters.Circutor_Ammeter import CircutorAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from src.testing.test_framework import AmmeterTestFramework


def start_emulators():
    # Started here (rather than relying on main.py) so this script is fully self-contained.
    ammeters = (GreenleeAmmeter(5000), EntesAmmeter(5001), CircutorAmmeter(5002))
    for ammeter in ammeters:
        threading.Thread(target=ammeter.start_server, daemon=True).start()
    time.sleep(1)


def ensure_sampling_config(sampling_config: dict) -> None:
    """config.yaml ships with sampling fields left null on purpose (see
    DESIGN_DECISIONS.md) - a strategy must be explicitly chosen. If nothing
    was set in the file, ask for it here instead of failing outright, so this
    script can still be run immediately after cloning the repo."""
    already_configured = any(
        sampling_config.get(field) is not None
        for field in ("measurements_count", "total_duration_seconds", "sampling_frequency_hz")
    )
    if already_configured:
        return

    print("No sampling strategy is configured in config/config.yaml.")
    print("1) Fixed number of measurements")
    print("2) Total test duration + sampling frequency")
    choice = input("Choose a sampling strategy (1/2) [1]: ").strip() or "1"

    if choice == "2":
        duration = input("Total test duration in seconds (e.g. 10): ").strip()
        frequency = input("Sampling frequency in Hz (e.g. 2): ").strip()
        sampling_config["total_duration_seconds"] = float(duration)
        sampling_config["sampling_frequency_hz"] = float(frequency)
    else:
        count = input("How many measurements should each test take? (e.g. 20): ").strip()
        sampling_config["measurements_count"] = int(count)


def main():
    start_emulators()
    framework = AmmeterTestFramework()
    ensure_sampling_config(framework.config["testing"]["sampling"])

    ammeter_types = ["greenlee", "entes", "circutor"]
    results = {}

    for ammeter_type in ammeter_types:
        print(f"Testing {ammeter_type} ammeter...")
        results[ammeter_type] = framework.run_test(ammeter_type)

    for ammeter_type, result in results.items():
        print(f"\nResults for {ammeter_type}:")
        print(f"  attempts={result['attempts']} failures={result['failures']} success_rate={result['success_rate']:.0%}")
        print(f"  stats={result['stats']}")

if __name__ == "__main__":
    main()
