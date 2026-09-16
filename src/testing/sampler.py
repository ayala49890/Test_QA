import time
from dataclasses import dataclass
from typing import List

from Ammeters.client import AmmeterCommunicationError
from src.testing.ammeter_client import AmmeterClient


class SamplingConfigError(Exception):
    """Raised when the sampling section of config.yaml is missing or ambiguous."""


class InsufficientSuccessfulSamplesError(Exception):
    """Raised when too many measurements failed to trust the collected sample."""


@dataclass
class SamplingResult:
    ammeter_type: str
    values: List[float]
    attempts: int
    failures: int

    @property
    def success_rate(self) -> float:
        return (self.attempts - self.failures) / self.attempts if self.attempts else 0.0


@dataclass
class SamplingPlan:
    count: int
    interval_seconds: float


def _resolve_sampling_plan(sampling_config: dict) -> SamplingPlan:
    """Turn measurements_count/total_duration_seconds/sampling_frequency_hz into
    a concrete (count, interval_seconds) plan.

    Any combination of the three fields is accepted as long as it is complete
    and, when all three are given, mathematically consistent. Fields that
    should not participate must be left null - see config.yaml for examples.
    """
    count = sampling_config.get("measurements_count")
    duration = sampling_config.get("total_duration_seconds")
    frequency = sampling_config.get("sampling_frequency_hz")

    has_count = count is not None
    has_duration = duration is not None
    has_frequency = frequency is not None

    if has_count and has_duration and has_frequency:
        expected_count = round(duration * frequency)
        if count != expected_count:
            raise SamplingConfigError(
                f"measurements_count ({count}) does not match total_duration_seconds * "
                f"sampling_frequency_hz ({duration} * {frequency} = {expected_count}). "
                "Set only the fields you actually want, and null the rest."
            )
        return SamplingPlan(count=count, interval_seconds=1.0 / frequency)

    if has_count and has_duration:
        # Exactly `count` measurements, spread evenly across `duration` seconds.
        return SamplingPlan(count=count, interval_seconds=duration / count)

    if has_count and has_frequency:
        return SamplingPlan(count=count, interval_seconds=1.0 / frequency)

    if has_duration and has_frequency:
        return SamplingPlan(count=max(1, round(duration * frequency)), interval_seconds=1.0 / frequency)

    if has_count:
        # No pacing information given - run back-to-back, as fast as possible.
        return SamplingPlan(count=count, interval_seconds=0.0)

    if has_duration or has_frequency:
        raise SamplingConfigError(
            "total_duration_seconds or sampling_frequency_hz is set on its own - that alone "
            "does not determine how many measurements to take. Set measurements_count, and/or "
            "the other of the two fields."
        )

    raise SamplingConfigError(
        "No sampling strategy configured - set measurements_count, and/or "
        "total_duration_seconds and sampling_frequency_hz, in config.yaml."
    )


def collect_samples(client: AmmeterClient, ammeter_type: str, sampling_config: dict) -> SamplingResult:
    """Take repeated measurements from `ammeter_type`, per the sampling section of config.yaml."""
    plan = _resolve_sampling_plan(sampling_config)
    min_success_rate = sampling_config.get("min_success_rate", 0.8)

    values: List[float] = []
    failures = 0
    # Anchored to the previous target time (not to when the last measurement
    # finished) so the sampling rate does not drift over a long run.
    next_sample_time = time.perf_counter()

    for _ in range(plan.count):
        try:
            values.append(client.measure(ammeter_type))
        except AmmeterCommunicationError:
            failures += 1

        next_sample_time += plan.interval_seconds
        sleep_seconds = next_sample_time - time.perf_counter()
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    result = SamplingResult(ammeter_type=ammeter_type, values=values, attempts=plan.count, failures=failures)

    if result.success_rate < min_success_rate:
        raise InsufficientSuccessfulSamplesError(
            f"Only {plan.count - failures}/{plan.count} measurements of '{ammeter_type}' succeeded "
            f"({result.success_rate:.0%}), below the required {min_success_rate:.0%}."
        )

    return result
