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
constraint. `matplotlib`/`seaborn` remain reserved for the visualization
bonus feature, where there is no reasonable stdlib alternative.

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
