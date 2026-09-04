# Split target/return authorization design

## Decision

The successor removes “automatic return.” Target and return are two different
motion legs with different preflights, different phrases, and different
authorization identifiers. The current implementation is a **pure design-state
evaluator** and authorizes zero commands.

```text
owner scope + independent review
              |
              v
target preflight -> target authorization -> target execution/observation
                                                |
                         success ---------------+--- failure -> no automatic return
                            |
                            v
return preflight -> NEW return authorization -> return execution/observation
                                                        |
                                      success ----------+--- failure -> no automatic return
```

The precise states and allowed transitions are in
[`split_authorization.py`](../reachy_stage4/split_authorization.py). An invalid
transition fails closed.

## Independent controls

| Leg | Required immediately before it | Exact authorization phrase |
|---|---|---|
| Target | fresh present/target trace, healthy daemon/control loop, reviewed baseline and target, clear area | `AUTHORIZE REACHY TARGET 3 DEGREES` |
| Return | a **new** trace from the measured post-target state, healthy daemon/control loop, reviewed return path, clear area | `AUTHORIZE REACHY RETURN TO CAPTURED BASELINE` |

The return identifier must differ from the target identifier. The return
preflight artifact must also differ from the target-observation artifact.

## Failure semantics

`HEALTH_FAILURE`, `TIMEOUT`, or `UNEXPECTED_MOTION` transitions every
nonterminal state to `ABORT_NO_AUTOMATIC_RETURN`. A failed motion leg enters the
same state. It does **not** attempt a software return in a `finally` block, and
it no longer assumes that either normal daemon shutdown or hard power removal
is automatically safe.

The pure [`failure-response matrix`](../reachy_stage4/failure_response.py)
distinguishes a torque-disabled observation failure, a responsive daemon with
fresh telemetry, daemon loss, and ambiguous/stale state. It authorizes no
response. Every branch preserves evidence, forbids automatic return, and points
to a separately reviewed unit-specific procedure. This is a deliberate change
from the frozen V4 pilot and the previous `ABORT_POWER_DOWN` design.

## Still missing before implementation

- owner confirmation of the exact modified-software and physical-motion scope;
- independent approval of the complete proposal;
- live present/target observability;
- validated continuous health thresholds and trace freshness rules;
- a reviewed executor boundary with explicit command accounting; and
- a Reachy-specific stop/de-energization procedure for daemon failure; and
- evidence from a nonmoving mock/simulation integration test before any
  physical run.

Until those exist, the state machine remains design-only.
