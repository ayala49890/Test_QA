# Design Decisions

This document summarizes the key design decisions made while extending the
provided starter code into a complete testing framework, and the reasoning
behind them.

## 1. Bug fix: client/server command mismatch (`main.py`)

`Ammeters/base_ammeter.py`'s server checks for an **exact** match between the
received bytes and `self.get_current_command` (e.g.
`b'MEASURE_GREENLEE -get_measurement'`). The original `main.py` sent only a
partial command (e.g. `b'MEASURE_GREENLEE'`), so the match always failed
silently - the server never responded, and the client printed "No data
received." with no exception raised.

**Fix**: `main.py` now creates each ammeter object once and reads the command
directly from `ammeter.get_current_command` instead of hand-typing it. This
guarantees the client and server can never drift out of sync, even if a
command string changes in the future or a new ammeter type is added.

## 2. Single source of truth: config vs. code

`config/config.yaml` is the source of truth for **test orchestration**
parameters (which ammeter types are included, their ports, sampling
strategy, statistical metrics, result storage). It is deliberately **not**
the source of truth for the exact wire-protocol command of each ammeter -
that remains owned by each ammeter class (`get_current_command`). Duplicating
the command string in both places would recreate the exact class of bug
described above if the two ever drifted apart.

## 3. Sampling configuration: no default, flexible validation

`testing.sampling` in `config.yaml` has three fields: `measurements_count`,
`total_duration_seconds`, `sampling_frequency_hz`. When set directly in
`config.yaml`, any *complete and mathematically consistent* combination of
these is accepted:

| count | duration | frequency | Behavior |
|---|---|---|---|
| ✓ | - | - | `count` measurements, run back-to-back (no pacing) |
| ✓ | ✓ | - | `count` measurements, evenly spread across `duration` seconds |
| ✓ | - | ✓ | `count` measurements, paced at `frequency` Hz |
| - | ✓ | ✓ | `count = duration * frequency`, paced at `frequency` Hz |
| ✓ | ✓ | ✓ | valid only if `count == duration * frequency`, else a clear error |
| any single field alone (except count) | - | - | error: not enough information |
| none set | - | - | error: no sampling strategy configured |

The all-three row is a **consistency guard**, not a mode intended for regular
use: if all three fields happen to be set, they must agree, otherwise a clear
error is raised rather than silently trusting one field over the others. It is
reachable only by editing `config.yaml` by hand - the interactive helper in
`examples/run_tests.py` deliberately exposes only the two natural modes (a
fixed count, or a duration + frequency pair).

The rule accepts every complete, consistent combination rather than a single
rigid pattern, which avoids ambiguous states. For example, if
`measurements_count` is left over from a previous edit while only
`total_duration_seconds` is newly filled in, the run fails with a clear error
instead of silently ignoring one of the two.

All three fields ship as `null` (no default value) - a sampling strategy must
be chosen explicitly before running a test. An earlier version of this
framework shipped with `measurements_count: 20` as a default (see git
history); it was removed once the validation above was in place, so that a
misconfiguration surfaces as an explicit error rather than silently falling
back to a default the user may not have intended.

This did introduce a UX gap: running `AmmeterTestFramework.run_test(...)`
directly on an unconfigured `config.yaml` raises a raw `SamplingConfigError`
traceback rather than a clean first-run experience. `examples/run_tests.py`
resolves this without reintroducing a hidden default: if no sampling
strategy is set, it asks interactively in the terminal - letting the user
choose between a fixed measurement count or a duration+frequency pair (the
same two independent modes `config.yaml` supports), rather than silently
assuming the user always wants a fixed count - preserving "no silent
default" while still letting the script be run immediately after cloning
the repo.

## 4. Precise timing (anti-drift)

`collect_samples` paces measurements using an accumulating target time
(`next_sample_time += interval`) rather than sleeping a fixed interval after
each measurement. This prevents the actual measurement time from
accumulating drift over a long sampling run, per the spec's "ensure precise
timing" requirement.

## 5. Per-measurement fault tolerance with a success-rate threshold

A single failed measurement (timeout, dropped connection) does not abort the
whole sampling run - it is caught, counted, and sampling continues. At the
end, if the success rate falls below `min_success_rate` (default 0.8 / 80%),
a clear error is raised instead of silently returning statistics computed on
too few samples. 80% was chosen deliberately: because measurements happen
over `localhost` TCP sockets (not real noisy embedded hardware), failures
here are far more likely to indicate a genuine bug than natural environmental
noise, so a stricter threshold than typical field-deployment tolerances is
appropriate; the value is configurable for use against real, noisier
hardware.

## 6. `statistics` (stdlib) instead of `numpy`

`numpy`, `scipy`, `pandas`, `matplotlib`, and `seaborn` are listed in
`requirements.txt` but were not used anywhere in the original codebase.
`analysis.py` uses Python's built-in `statistics` module for mean / median /
std_dev, since it is fully sufficient for this data size and avoids an
unnecessary dependency, per the "minimize external library dependencies"
constraint. The only external library the framework actually uses for
computation/output is `matplotlib`, for the visualization feature (section 10),
where there is no reasonable stdlib alternative; `numpy`/`scipy`/`pandas`/
`seaborn` remain unused.

## 7. Unified measurement API via a class, not per-type branching

`AmmeterClient.measure(ammeter_type)` uses a small registry
(`AMMETER_CLASSES`) mapping a type name to its emulator class, and calls
`ammeter.get_current_command` / `ammeter.port` polymorphically - the same
call site works for every ammeter type. This extends the polymorphism already
present on the server side (`AmmeterEmulatorBase.start_server` calling
`self.get_current_command()` / `self.measure_current()`) to the client side,
rather than introducing a parallel `if/elif` per ammeter type.

A class (rather than a bare function) was chosen to match the existing OOP
style of the codebase and to leave room for future extension (retries,
per-instance logging) without changing every call site.

## 8. Result storage: unique IDs and metadata

Each test run gets an ID of the form `<timestamp>_<6-char random suffix>`
(e.g. `20260916_175121_fu63dr`) - human-readable and chronologically
sortable, with the random suffix guaranteeing uniqueness even for runs in the
same second. Each result is saved as `<ammeter_type>_<id>.json` under
`results/`, containing the raw values, computed statistics, and the sampling
configuration used (`sampling_config`) as metadata - so any historical result
can be traced back to the exact conditions it was produced under.

## 9. `TestLogger` fix (outside the ammeter-emulation scope)

The spec explicitly permits fixing errors in the "existing ammeter emulation
infrastructure" (`Ammeters/`). `src/utils/logger.py` falls outside that
scope, but since `AmmeterTestFramework` relies on it for traceability, its
one structural bug was fixed: `_setup_logger` computed a log file path but
never attached a `FileHandler`, so nothing was ever written to disk,
regardless of timing or naming. This was fixed by adding the missing
`FileHandler` + `Formatter` + log level, without changing the existing
filename/timestamp logic.

A later refinement also guards against `logging.getLogger` returning a cached
logger: the logger name now includes the timestamp, and a `if not
logger.handlers` check prevents attaching a duplicate `FileHandler` (which
would double log lines and leak file handles) if the same test name is reused
within one process.

## 10. Visualization (bonus): config-gated, matplotlib only, best-effort

The starter `config.yaml` already shipped with `analysis.visualization.enabled:
true`, signalling that visualization was expected. `src/testing/visualization.py`
implements it: `generate_plots(...)` renders a line plot (current over samples)
and a histogram (value distribution) per run, saved under `results/plots/`.

Three deliberate choices:

- **`matplotlib` only, not `seaborn`.** `seaborn` produces prettier defaults but
  pulls in `pandas` at runtime purely for styling. `matplotlib` alone renders
  clear, professional line/histogram plots, so it is the minimal choice that
  honours the "minimize external library dependencies" constraint.
- **Config-gated, not a separate manual step.** Plotting runs inside
  `run_test` only when `analysis.visualization.enabled` is true, so the
  existing config flag actually drives behaviour - consistent with the
  project's configuration-driven design.
- **Best-effort, never fatal.** Plot generation is wrapped so that a failure
  (e.g. `matplotlib` not installed, or a bad `plot_types` value) is logged as a
  warning and the test run - whose measurements, statistics and JSON result
  already succeeded - still returns normally. Visualization is an enhancement of
  the reporting, not a prerequisite for it. The non-interactive `Agg` backend is
  used so plots render to files without a display, safe under the threaded
  emulator setup.

## 11. Performance consistency evaluation (bonus): coefficient of variation

`analysis.py` adds `consistency_cv`, the coefficient of variation
(`std_dev / mean`) - a standard, unitless measure of how consistent a set of
measurements is relative to their own size, which is exactly what the
"Performance consistency evaluation" bonus challenge asks for. A lower value
means the ammeter's readings are more consistent; it lets two ammeters (or
two runs of the same one) be compared on consistency even if their absolute
current levels differ.

It is implemented as a metric alongside `mean`/`median`/`std_dev`/`min`/`max`,
selectable the same way via `analysis.statistical_metrics` in `config.yaml`,
rather than as a separate code path - keeping `analyze()` as the single place
all statistics are computed. It returns `None` under the same n<2 condition
as `std_dev` (which it depends on), and also when the mean is 0, to avoid a
division-by-zero.
