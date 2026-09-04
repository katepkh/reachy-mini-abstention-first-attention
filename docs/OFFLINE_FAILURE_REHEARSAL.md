# Offline temporary-daemon failure rehearsal

## Result

Four fixed local Python mock-process scenarios are exercised: start failure,
health timeout, state-stream disconnect while the process remains alive, and a
shutdown hang. The rehearsal starts no Reachy daemon, imports no Reachy package,
opens no socket or serial port, and sends no robot command.

The current deterministic result is `PASS_OFFLINE_MOCK_ONLY`. In every scenario:

- a duplicate mock-daemon lease was refused;
- restoration was refused while the mock process or lease remained active;
- process exit was confirmed before the mock restoration gate opened; and
- hardware restoration remained explicitly unauthorized.

The generated report and sidecar are
[`stage4a_offline_fault_rehearsal_v1.json`](../evidence/analysis/stage4a_offline_fault_rehearsal_v1.json)
and `stage4a_offline_fault_rehearsal_v1.json.sha256`.

## What this does not establish

This proves only the local harness's process-state and mutual-exclusion logic.
It does not show that a real daemon releases the serial bus, that torque is
disabled, that a stock daemon restart is safe, or that forced termination is an
appropriate response on Reachy. The Pollen community question remains the gate
for a unit-specific recovery sequence. Reachy should remain powered down until
that guidance is assessed.

## Reproduction

```bash
python scripts/run_offline_fault_rehearsal.py --check
```
