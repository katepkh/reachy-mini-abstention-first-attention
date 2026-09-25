# Offline temporary-daemon failure rehearsal

## Result

Four fixed local Python mock-process scenarios are exercised: start failure,
health timeout, state-stream disconnect while the process remains alive, and a
shutdown hang. The rehearsal starts no Reachy daemon, imports no Reachy package,
opens no socket or serial port, and sends no robot command.

The current deterministic result is `PASS_OFFLINE_MOCK_ONLY`. In every process
fault scenario:

- a duplicate mock-daemon lease was refused;
- restoration was refused while the mock process or lease remained active;
- process exit was confirmed before the mock restoration gate opened; and
- hardware restoration remained explicitly unauthorized.

The separate
[`observation_executor.py`](../reachy_stage4/observation_executor.py) now
rehearses the complete stock-baseline, release, temporary-start, trace,
terminal-state, resource-release, and stock-restoration sequence with an
injected mock adapter. It refuses an adapter unless `offline_only=True`, ships
no concrete transport implementation, and records zero connections and zero
commands. Its tests additionally establish that:

- a stock resource that is not released prevents temporary startup;
- a trace fault rolls back only from fresh, unambiguous terminal state;
- stale, missing, or unknown terminal state requires the physical-power branch
  and never starts/restores another daemon;
- a fresh enabled terminal state rehearses exactly one safety-disable before
  stopping; and
- partial startup failure is treated as ambiguous, not as a clean stop.

The generated report and sidecar are
[`stage4a_offline_fault_rehearsal_v1.json`](../evidence/analysis/stage4a_offline_fault_rehearsal_v1.json)
and `stage4a_offline_fault_rehearsal_v1.json.sha256`.

## What this does not establish

This proves only the local harness's process-state and mutual-exclusion logic.
It does not show that a real daemon releases the serial bus, that torque is
disabled, that a stock daemon restart is safe, or that forced termination is an
appropriate response on Reachy. A pure terminal-state planner and offline
executor freeze and rehearse the intended stop/disable/physical-power branches,
but they have not executed those branches on hardware. A passing mock rehearsal
is not authority for another powered attempt or for motion.

## Reproduction

```bash
python scripts/run_offline_fault_rehearsal.py --check
```
