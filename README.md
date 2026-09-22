# Ammeter Testing Framework

A configuration-driven testing framework for current measurement across three
emulated ammeter types (Greenlee, ENTES, CIRCUTOR), built as part of an
embedded-systems QA exercise.

## Requirements

- Python 3.9+
- `pip install -r requirements.txt`. The framework itself needs only `pyyaml`
  (config) and `matplotlib` (the optional visualization feature - see below).
  The other listed packages (numpy/scipy/seaborn/pandas) are not used by the
  code. See [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) for why.

No additional libraries were installed beyond what is already listed in
`requirements.txt`.

## Project Structure

- `Ammeters/` - the ammeter emulators (given infrastructure)
  - `base_ammeter.py` - abstract base class; each subclass defines its own
    wire-protocol command (`get_current_command`) and measurement formula.
  - `Greenlee_Ammeter.py`, `Entes_Ammeter.py`, `Circutor_Ammeter.py` - one emulator per ammeter type.
  - `client.py` - low-level socket client (`request_current_from_ammeter`) that sends a command and returns the measured current as a `float`, raising `AmmeterCommunicationError` on any failure.
- `config/config.yaml` - all test parameters (ports, sampling strategy, statistical metrics, result storage). See below.
- `main.py` - starts the 3 emulator servers and takes one raw measurement from each (demonstrates that the client/server protocol works end-to-end).
- `src/testing/`
  - `ammeter_client.py` - `AmmeterClient`: a unified API (`measure(ammeter_type)`) that works the same way regardless of ammeter type.
  - `sampler.py` - `collect_samples(...)`: repeated, precisely-timed measurements per the sampling configuration, with per-measurement failure tolerance.
  - `analysis.py` - `analyze(values, metrics)`: mean / median / std_dev / min / max, plus `consistency_cv` (coefficient of variation - see below).
  - `visualization.py` - `generate_plots(...)`: optional line + histogram plots of a run (matplotlib), saved under `results/plots/`.
  - `results.py` - `save_result` / `list_results` / `load_result`: JSON persistence with a unique result ID and metadata.
  - `test_framework.py` - `AmmeterTestFramework.run_test(ammeter_type)`: orchestrates all of the above into a single call.
- `src/utils/` - `config.py` (YAML loading), `logger.py` (`TestLogger`), `Utils.py` (`generate_random_float`).
- `examples/run_tests.py` - the recommended ready-to-run entry point: starts the emulators, runs `AmmeterTestFramework.run_test(...)` for all three ammeter types, and prints a summary (stats + plot paths). Rewritten from the original template stub, which was a non-working placeholder marked "don't use it".
- `results/` - generated at runtime (git-ignored); JSON test results, logs, and plots (`results/plots/`).
- `sample_results/` - a few committed example outputs (a result JSON plus example plots), for reference (see Deliverables).

## Quick Start

### 1. Raw single measurement (sanity check)

```sh
python main.py
```

Starts the 3 emulator servers and requests one measurement from each - useful to confirm your Python environment and the client/server protocol both work.

### 2. Full test run (sampling + statistics + saved result)

The easiest way to try the full framework is the ready-to-run example:

```sh
python examples/run_tests.py
```

It starts all 3 emulators and runs `AmmeterTestFramework.run_test(...)` for
each ammeter type. If `config/config.yaml` has no sampling strategy
configured yet (it ships with all three fields `null` - see below), it will
ask you in the terminal to choose one of the two sampling strategies (a fixed
number of measurements, or a total duration + sampling frequency), instead of
failing.

When the run finishes, because `analysis.visualization.enabled` is `true` in
`config.yaml`, a line plot and a histogram are generated per ammeter type and
saved under `results/plots/` (their paths are printed in the summary). Open
them with any image viewer - e.g. `Invoke-Item results/plots` on Windows. This
requires `matplotlib` (installed via `requirements.txt`); if it is missing, the
run still succeeds and simply skips the plots.

To use `AmmeterTestFramework` directly in your own code:

```python
import threading, time
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Circutor_Ammeter import CircutorAmmeter
from src.testing.test_framework import AmmeterTestFramework

for ammeter in (GreenleeAmmeter(5000), EntesAmmeter(5001), CircutorAmmeter(5002)):
    threading.Thread(target=ammeter.start_server, daemon=True).start()
time.sleep(1)

framework = AmmeterTestFramework()  # loads config/config.yaml
result = framework.run_test("greenlee")
print(result)
```

`run_test` returns a dict with `result_id`, `attempts`, `failures`,
`success_rate`, the raw `values`, the computed `stats`, and `plots` (paths to
any generated plot files), and also persists the same data as a JSON file
under `results/`.

> **Note:** `config/config.yaml` ships with `testing.sampling` fields set to
> `null` on purpose (see below) - fill in a sampling strategy (e.g.
> `measurements_count: 20`) before calling `run_test` directly, otherwise a
> clear `SamplingConfigError` is raised. `examples/run_tests.py` handles this
> for you interactively.

## Configuration (`config/config.yaml`)

- **`ammeters`** - port for each ammeter type. The exact wire-protocol command
  is intentionally *not* duplicated here - it stays owned by each ammeter
  class, to avoid two sources of truth for the same protocol detail.
- **`testing.sampling`** - `measurements_count`, `total_duration_seconds`,
  `sampling_frequency_hz` (any complete, consistent combination is accepted -
  see `src/testing/sampler.py` for the full rules), plus `min_success_rate`
  (minimum fraction of successful measurements to accept a run, default 0.8).
  All three sampling fields ship as `null` - a sampling strategy must be
  chosen explicitly before running a test (a clear error is raised otherwise).
- **`analysis.statistical_metrics`** - which metrics to compute. Ships with
  `mean`, `median`, `std_dev`, `min`, `max`, and `consistency_cv` (coefficient
  of variation = `std_dev / mean`): a unitless "performance consistency"
  score where lower means more consistent readings relative to their size.
  Like `std_dev`, it is `null` when fewer than 2 measurements succeeded, and
  also `null` if the mean is 0.
- **`analysis.visualization`** - `enabled` (on/off) and `plot_types` (`line`,
  `histogram`). When enabled, each `run_test` also saves plots under
  `results/plots/`. Visualization is best-effort: if it fails (e.g. matplotlib
  is missing) the test run still succeeds and the failure is logged.
- **`result_management`** - output directory and format for saved results.

## Fixes to the provided starter code

1. **`main.py`**: the client previously sent partial/incorrect commands (e.g.
   `b'MEASURE_GREENLEE'` instead of the full `b'MEASURE_GREENLEE -get_measurement'`
   the server checks for), so the server never responded. Fixed by having the
   client read the exact command from each ammeter's own
   `get_current_command`, so client and server can never drift out of sync.
2. **`src/utils/logger.py`**: `TestLogger` computed a log file path but never
   attached a `FileHandler`, so nothing was ever written to disk. Fixed by
   wiring up a `FileHandler` + `Formatter` + log level.

See [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) for the reasoning behind these and other choices.

## Known Limitations / Not Implemented

- Cross-ammeter accuracy comparison (bonus)
- Error simulation (bonus)

## Ammeter Protocol Reference

### Greenlee Ammeter

- **Port**: 5000
- **Command**: `MEASURE_GREENLEE -get_measurement`
- **Measurement Logic**: Calculates current using voltage (1V - 10V) and (0.1Ω - 100Ω).
- **Measurement method** : Ohm's Law: I = V / R

### ENTES Ammeter

- **Port**: 5001
- **Command**: `MEASURE_ENTES -get_data`
- **Measurement Logic**: Calculates current using magnetic field strength (0.01T - 0.1T) and calibration factor (500 - 2000).
- **Measurement method** : Hall Effect: I = B * K

### CIRCUTOR Ammeter

- **Port**: 5002
- **Command**: `MEASURE_CIRCUTOR -get_measurement -current`
- **Measurement Logic**: Calculates current using voltage values (0.1V - 1.0V) over a number of samples and a random time step (0.001s - 0.01s).
- **Measurement method** : Rogowski Coil Integration: I = ∫V dt