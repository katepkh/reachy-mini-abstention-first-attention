# Independent robotics review request

## Current status

**No independent approval has been recorded.** Passing unit tests and an AI
review do not satisfy this gate. The reviewer should be a human with relevant
robot motion, controls, safety, or Reachy Mini expertise, distinct from the
operator and identified in the preserved response.

The owner has confirmed the limited temporary-daemon, restore-and-verify scope;
the exact exchange is held in a hash-verified private record. That permission
does not cover the proposed 3° target or return legs. The reviewer is assessing
technical adequacy, not granting owner permission.

## Message for the independent reviewer

> Could you review this as a pre-actuation protocol, not as a polished demo? I
> want a blunt decision: `PROTOCOL_APPROVED`, `CHANGES_REQUESTED`, or `REJECTED`.
> Please focus on whether the evidence justifies even one supervised 3° head
> target and a separately authorized return on a borrowed Reachy Mini.
>
> Start with these files:
> - `docs/SUCCESSOR_REVIEW_MANIFEST.json` (the content-addressed packet index)
> - `docs/EXTERNAL_REVIEW.md`
> - `docs/BASELINE_RELATIVE_SUCCESSOR.md`
> - `docs/RECEIVE_ONLY_SUCCESSOR_TRACE.md`
> - `docs/TEMPORARY_DAEMON_LIFECYCLE.md`
> - `docs/SUCCESSOR_TRAJECTORY_REVIEW.md`
> - `docs/SPLIT_TARGET_RETURN_PROTOCOL.md`
> - `docs/RETURN_TO_BORROWED_CONDITION.md`
> - `docs/TARGET_STATE_OBSERVABILITY.md`
> - `docs/MAINTENANCE_TRIAGE.md`
> - `reachy_stage4/successor_trace.py`
> - `reachy_stage4/trajectory_review.py`
> - `reachy_stage4/split_authorization.py`
> - `reachy_stage4/daemon_lifecycle.py`
> - `reachy_stage4/failure_response.py`
> - `reachy_stage4/rollback_inventory.py`
> - `scripts/validate_successor_trajectory_v190.py`
> - `patches/reachy-mini-v1.9.0-target-state-observability.patch`
> - `patches/reachy-mini-v1.9.0-observation-lifecycle.patch`
>
> Known non-results: the patch is not installed; no live present/target trace
> exists; the offline margin result is not collision or load validation; the
> non-identity start-pose cause remains unknown; no successor command has been
> sent; and 0/4 physical directions are accepted. The lifecycle patch suppresses
> the daemon reflash helper but motor-controller 1.5.5 can still conditionally
> reboot a motor with a pre-existing non-voltage hardware error. Please state your expertise,
> assumptions, blocking findings, required changes, and assess the conditional
> failure-response matrix rather than choosing one universal power-down or return.
> Please separately
> decide whether the temporary deployment/rollback design can return a borrowed
> unit to a documented practical equivalent state; do not interpret that as a
> promise of literal zero wear or byte-identical storage.

The local mock-process fault rehearsal passes all four cases, but reviewers
must not treat mock exit as evidence of real torque removal, serial-bus release,
or a safe daemon restart. See [`OFFLINE_FAILURE_REHEARSAL.md`](OFFLINE_FAILURE_REHEARSAL.md).

## Required review questions

1. Is a baseline-relative 3° world-axis target defensible given the repeatable
   roughly 2.7° non-identity post-wake pose, or should the unit receive vendor
   maintenance first?
2. Does the receive-only trace expose enough simultaneous present/target state
   to detect stale targets and tracking failure? What rate, age, and residual
   thresholds should be preregistered?
3. Is the four-field `FullState` change genuinely observational, and what risks
   arise from installing/restarting it on the borrowed unit?
4. Is checking analytical IK against configured joint limits meaningful enough
   to continue, given that analytical `check_collision` is unused? Which
   collision, singularity, load/current, cable, and enclosure checks are
   missing?
5. Does the inclusive 100 Hz path-envelope calculation cover all geometric
   extrema for these paths? If not, what continuous or adaptive verification is
   needed?
6. Is splitting target and return authorization safer than an automatic
   `finally` return? For each failure class, is the proposed stay-clear,
   supported stop/disable, or owner-approved physical de-energization response
   appropriate? Neither normal shutdown nor hard power removal is assumed safe.
7. Are the candidate readiness limits (10° absolute RPY/geodesic, 8 mm
   translation, 0.25°/1 mm baseline drift, 50 frames) defensible? If not,
   replace them with source-backed or experimentally justified values.
8. What exact outcome would make one physical leg acceptable, and what outcome
   must terminate the entire series?
9. Is the return-to-borrowed-condition protocol adequate? In particular, assess
   baseline completeness, isolated caches/logs, temporary-versus-system
   installation, omission of `--wireless-version`, and the lifecycle patch's
   no-reflash/no-startup-app/no-mDNS controls. Does conditional motor reboot or
   the lack of proved torque removal after daemon failure require vendor review
   before any patched hardware startup?

## Expected response format

```text
Reviewer identity / stable identifier:
Relevant expertise:
Materials and commit reviewed:
Decision: PROTOCOL_APPROVED | CHANGES_REQUESTED | REJECTED
Blocking findings:
Nonblocking findings:
Required changes:
Answers to questions 1–9:
Return protocol decision: APPROVED | CHANGES_REQUESTED | REJECTED
Is vendor review additionally required before patched hardware startup? yes | no
Conditions and expiry of approval:
```

The reply should be preserved privately and hashed in a
`reachy-stage4a-independent-protocol-review-v2` record. The structured record
must include `reviewed_manifest_sha256`, `return_protocol_decision`, and
`vendor_review_required`; it cannot convert an ambiguous narrative into
approval. Recording a review does
not itself authorize a motion command; owner scope, fresh telemetry, and the
leg-specific operator authorization remain independent gates.
