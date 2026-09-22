from typing import Dict

from src.testing.ammeter_client import AmmeterClient
from src.testing.analysis import analyze
from src.testing.results import save_result
from src.testing.sampler import collect_samples
from src.utils.config import load_config
from src.utils.logger import TestLogger


class AmmeterTestFramework:
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = load_config(config_path)
        self.client = AmmeterClient(self.config["ammeters"])

    def run_test(self, ammeter_type: str) -> Dict:
        """Run a full sampling + analysis + persistence cycle for one ammeter type."""
        logger = TestLogger(ammeter_type)
        logger.info(f"Starting test run for {ammeter_type}")

        sampling_config = self.config["testing"]["sampling"]
        try:
            sampling_result = collect_samples(self.client, ammeter_type, sampling_config)
            stats = analyze(sampling_result.values, self.config["analysis"]["statistical_metrics"])
        except Exception as exc:
            logger.error(f"Test run failed: {exc}")
            raise

        result_id = save_result(
            self.config["result_management"]["results_dir"],
            ammeter_type,
            sampling_result,
            stats,
            sampling_config,
        )
        logger.info(f"Test run complete, saved as {result_id}")

        return {
            "result_id": result_id,
            "ammeter_type": ammeter_type,
            "attempts": sampling_result.attempts,
            "failures": sampling_result.failures,
            "success_rate": sampling_result.success_rate,
            "values": sampling_result.values,
            "stats": stats,
        }
