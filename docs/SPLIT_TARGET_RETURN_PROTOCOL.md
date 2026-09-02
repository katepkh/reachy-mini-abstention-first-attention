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
                         success ---------------+--- failure -> power down
                            |
                            v
return preflight -> NEW return authorization -> return execution/observation
                                                        |
                                      success ----------+--- failure -> power down
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
nonterminal state to `ABORT_POWER_DOWN`. A failed outward leg also transitions
to `ABORT_POWER_DOWN`; it does **not** attempt a software return in a `finally`
block. The intended response is supervised normal power-down, followed by
inspection and review. This avoids issuing a second command from an unknown
state merely because the first command failed.

This is a deliberate change from the frozen V4 pilot. It does not claim that
power-down is mechanically risk-free in every failure mode; that question is
part of the requested external review.

## Still missing before implementation

- owner confirmation of the exact modified-software and physical-motion scope;
- independent approval of the complete proposal;
- live present/target observability;
- validated continuous health thresholds and trace freshness rules;
- a reviewed executor boundary with explicit command accounting; and
- evidence from a nonmoving mock/simulation integration test before any
  physical run.

Until those exist, the state machine remains design-only.
