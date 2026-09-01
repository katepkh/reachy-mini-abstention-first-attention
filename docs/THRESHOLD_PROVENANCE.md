# Threshold provenance and calibration debt

This document distinguishes values selected from evidence from values that were simply fixed as conservative engineering choices. A frozen value is reproducible; it is not automatically optimal, calibrated, or portable to another robot, room, camera, or operator.

## Provenance labels

| Label | Meaning |
|---|---|
| **Development-selected** | A disclosed candidate grid and selection rule were applied to development evidence. Later fresh data, if any, remained separate. |
| **Protocol-fixed** | Frozen before the named collection so that the outcome could not change it, but not optimized in a documented calibration experiment. |
| **Project-fixed** | Chosen during implementation. The repository contains no adequate empirical selection record. |
| **Hardware-bound** | A deliberately narrow safety or mechanics limit for this pilot. It is not a certified safe limit. |

## Passive sensing and Stage 2A

| Boundary | Frozen value | Provenance | Evidence and caveat |
|---|---:|---|---|
| YuNet detector score | 0.90 | Project-fixed | Passed directly to OpenCV in [`face_detector.py`](../reachy_stage2a/face_detector.py#L27). The repository does not contain a detector-threshold calibration, and this must not be described as a YuNet default. |
| YuNet NMS / top-k / maximum analysis width | 0.30 / 5000 / 640 px | Project-fixed | Implementation limits in [`face_detector.py`](../reachy_stage2a/face_detector.py#L28-L30); no sensitivity study is available. |
| Minimum face confidence | 0.55 | Project-fixed | Frozen in [`config.py`](../reachy_stage2a/config.py#L31) and enforced by [`fusion.py`](../reachy_stage2a/fusion.py#L61). It is distinct from the detector's 0.90 proposal threshold. |
| Minimum acoustic confidence | 0.60 | Project-fixed | Frozen in [`config.py`](../reachy_stage2a/config.py#L32) and enforced by [`fusion.py`](../reachy_stage2a/fusion.py#L44). No receiver-operating-characteristic analysis was run. |
| Maximum face age | 750 ms | Project-fixed | Staleness boundary in [`config.py`](../reachy_stage2a/config.py#L30) and [`fusion.py`](../reachy_stage2a/fusion.py#L54-L56). |
| One-frame acoustic/visual error | 20 degrees | Project-fixed | Compatibility envelope in [`config.py`](../reachy_stage2a/config.py#L33). The later stages use stricter policies; this value is not speaker-ownership evidence. |
| Retrospective 3-hit policy | 3 hits / 900 ms / 10 degrees / 1000 ms lockout | Development-selected, retrospectively | Candidate and split are declared in [`tournament.py`](../reachy_stage2a/tournament.py#L52-L89). Repetitions 1–2 were used for selection and repetition 3 for internal evaluation, but the complete matrix had already been inspected; the split is not a pristine holdout. |

## Frozen Stage 3V horizontal policy

The current reference policy is [`FROZEN_REVISED_POLICY_V3`](../reachy_stage3v/revised_policy_v3.py#L39-L51). Its parameters have mixed provenance:

| Parameter | Frozen value | Provenance | Evidence and caveat |
|---|---:|---|---|
| Camera-to-diagram sign | -1 | Development-diagnosed | The stored camera and diagram headings had opposite signs; the correction was retained through the Stage 3V diagnosis chain. |
| Camera-to-diagram yaw offset | -4 degrees | Development-selected | Offsets from -8 to +4 degrees in 0.5-degree steps were compared across three disclosed development datasets in [`offline_diagnosis_v3.py`](../reachy_stage3v/offline_diagnosis_v3.py#L106-L124). The smallest worst-error passing offset was frozen before the fresh V3 confirmation. |
| Geometry envelope | 10 degrees | Development-selected then inherited | Earlier Stage 3V development replay compared 6, 8, 10, and 12 degrees and selected the smallest passing envelope under its rule in [`offline_diagnosis.py`](../reachy_stage3v/offline_diagnosis.py#L73-L102). Later repairs retained it. |
| Temporal consensus | 3 hits / 600 ms | Development-diagnosed then inherited | Frozen before the V2 and V3 fresh confirmations. The exact values were retained while the V2 search changed only speech-latch duration; this is not an independent calibration of temporal dynamics. |
| Hit-to-hit heading tolerance | 8 degrees | Project-fixed and inherited | Held constant throughout the disclosed candidate grids. The repository has no sensitivity analysis for this value. |
| Disagreement lockout | 1500 ms | Project-fixed and inherited | Held constant across the Stage 3V grids. It encodes conservative hysteresis but lacks a standalone calibration experiment. |
| Speech latch | 800 ms | Development-selected | Latches from 0 to 1200 ms in 200-ms increments were tested across two now-development datasets; the shortest passing value was selected in [`offline_diagnosis_v2.py`](../reachy_stage3v/offline_diagnosis_v2.py#L104-L123). |
| Held-out maximum target error | 8 degrees | Protocol-fixed | Declared in [`confirmation_protocol_v3.py`](../reachy_stage3v/confirmation_protocol_v3.py#L36-L42) before the fresh V3 collection. It is an acceptance bound, not a population performance estimate. |

## Stage 3P passive visual-cue boundary

The cue experiment kept the frozen V6 passive policy unchanged and added a separate `MOVE`-cue readiness gate. The broader V6 result remained failed; the targeted cue experiment did not relabel it. The gate has no robot command path.

| Parameter | Frozen value | Provenance | Evidence and caveat |
|---|---:|---|---|
| V6 fallback geometry / speech window | 13 degrees / 2500 ms | Development-selected after a failed V5 result | A disclosed 48-candidate grid tested geometry 10–15 degrees and speech windows 2500–4000 ms; 9 passed, and the deterministic selection rule chose 13/2500 in [`analysis_v6.py`](../reachy_stage3p/analysis_v6.py#L129-L170). This is vulnerable to development-set overfitting and required fresh confirmation. |
| V6 association consensus | 2 hits / 600 ms / 8 degrees | Mixed: development-selected hits, inherited fixed window/tolerance | Frozen in [`stage3p_selected_policy_v6.json`](../evidence/manifests/stage3p_selected_policy_v6.json). The components do not all have equal empirical support. |
| Pitch consensus | 3 hits / 600 ms / 4 degrees | Project-fixed and inherited | Frozen in the V6 policy manifest; no isolated sensitivity experiment was run. |
| Maximum passive pitch increment | 3 degrees | Protocol-fixed | A shadow-policy bound only; it did not authorize hardware. |
| Cue readiness | 3 consecutive centered rows | Protocol-fixed | Declared before collection in [`cue_confirmation_protocol.py`](../reachy_stage3p/cue_confirmation_protocol.py#L21-L25) and implemented in [`association_gated_cue.py`](../reachy_stage3p/association_gated_cue.py#L13-L17). |
| Centered pitch envelope | +/-2.5 degrees | Protocol-fixed | Frozen for the targeted cue confirmation. It was not optimized against the nine confirmation trials. |
| Ready timeout | 12 seconds | Protocol-fixed | Produces a fail-closed no-cue outcome. It is a usability choice as well as a safety boundary and has not been user-studied. |
| Post-cue scoring delay | 4000 ms | Protocol-fixed | Prevented immediate transition rows from being scored as stable correction; no sensitivity analysis was run. |

## Stage 4A experimental mechanical boundary

These values in [`reachy_stage4/config.py`](../reachy_stage4/config.py#L28-L43) were fixed for one supervised pilot. They are **not** manufacturer limits, certified safety limits, or evidence that the mechanism is healthy.

| Boundary | Frozen value | Provenance | Current status |
|---|---:|---|---|
| Relative head-only increment | 3 degrees | Hardware-bound | One V3 physical trial failed its unchanged mechanical gate. V4 has not run. |
| Move / return duration | 2.0 s / 2.0 s | Hardware-bound | Slow experimental motion profile, not independently validated. |
| Target / return settling dwell | 0.75 s / 0.75 s | Hardware-bound repair | Added after diagnosing premature V3 sampling; still unvalidated physically. |
| Preflight lifetime | 600 s | Project-fixed | Expiring one-shot operator session; not a safety proof. |
| Baseline neutral / recheck error | 1.0 / 1.0 degrees | Hardware-bound | The current controller/daemon neutral disagreement blocks preflight rather than being overridden. |
| Target / return error | 1.5 / 1.0 degrees | Hardware-bound | The failed V3 outcome was preserved; limits were not relaxed afterward. |
| Translation envelope | 8 mm | Hardware-bound | Prevents a nominally rotational trial from accepting excessive translation; not manufacturer-certified. |
| Control-loop frequency / interval | 40–60 Hz / <=0.1 s | Project-fixed | Runtime-health checks for this pilot implementation. |
| Telemetry age | <=2 s | Project-fixed | Stale-state rejection boundary. |

## What is still missing

1. A preregistered threshold-sensitivity analysis over trial-level outcomes, including coverage, false movement proposals, direction error, latency, and abstention duration.
2. Calibration and evaluation data separated by room, voice stimulus, and person—not merely repetition.
3. Confidence intervals or other uncertainty summaries at the trial level.
4. A documented rationale for project-fixed values, or replacement of those values with development-selected ones followed by genuinely fresh evaluation.
5. A machine-readable central registry. Today the authoritative values remain distributed across frozen policy/protocol objects to preserve their audit trail.

Until those gaps are closed, reuse should preserve the values only to reproduce this experiment—not because they are known to be generally correct.
