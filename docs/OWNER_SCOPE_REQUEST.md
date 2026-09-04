# Robot-owner scope confirmation request

## Current status

The owner directly accepted a shorter written request to temporarily run a
separate minimally patched daemon, restore and verify the untouched original,
avoid recalibration and permanent installation, and allow the incidental normal
wake movement. The screenshot and exact transcription are preserved outside Git
in a byte-verified private v2 record.

Public cryptographic commitments:

- source screenshot SHA-256: `a107dfedfa35bdd91a7da6689957cb60a39d86286f2e5da115a20611be17ead1`;
- normalized private record SHA-256: `ea11d01481eb6b31fc987ae849e1057bb96d4608f861c1bff3273996c1e491ea`.

This is limited lifecycle/observability permission. The physical 3° target and
return legs, disassembly, recalibration, firmware or torque changes, and
publication of the owner's identity or correspondence were not requested and
are not inferred. Hash validation proves only byte preservation and record
structure; it does not authenticate the sender. Mapping the accepted
temporary-daemon request to the project's three command-free observability
action identifiers is a disclosed normalization judgment, not an item-by-item
reply from the owner.

## Unsent itemized template for any later expansion of scope

> I found that Reachy Mini daemon 1.9.0 drops target pose/joint fields from its
> read-only state response. I have a minimal four-field schema patch that has
> passed isolated mock-daemon tests, plus an offline-reviewed 3° trajectory.
> Before touching the borrowed robot, could you confirm the scope you are
> comfortable with?
>
> 1. May I power Reachy for a bounded baseline inventory and receive-only
>    diagnostic capture?
> 2. May I stop the original daemon, run the reviewed target-state schema patch
>    only from a separate temporary development environment, and then restart
>    the untouched original daemon? I will not replace the system-wide package.
>    This still runs modified software and can create logs; daemon startup may
>    initialize firmware when it judges that necessary and may perform a wake.
> 3. After independent protocol review, may I run one supervised 3° head target
>    leg and—only after a new preflight and separate authorization—one return
>    leg?
> 4. May I publish derived telemetry, code, protocol, and failure analysis, while
>    excluding raw audio/video, credentials, private network details, and your
>    identity unless you opt in?
> 5. For return, is “same condition” acceptable as matching the original
>    software/configuration/service/app inventory and normal operation, with all
>    differences and new logs disclosed? Literal zero wear or byte-identical
>    storage cannot be promised. Please specify anything else you require.
>
> I will not disassemble, recalibrate, bypass a failed gate, change torque/motor
> mode, run tracking, perform a system-wide install/factory reset, erase logs,
> or continue after abnormal noise, heat, shaking, stale telemetry, or unexpected
> motion. The detailed return protocol is `docs/RETURN_TO_BORROWED_CONDITION.md`.
> Please answer each item yes/no and add any conditions. “No” is completely fine.

## Scope matrix to preserve with the reply

| Action | Owner response | Required before action |
|---|---|---|
| Power for baseline inventory/receive-only state capture | confirmed within the limited temporary-daemon request | independent review of exact procedure still required |
| Create a separate temporary patched daemon environment | confirmed | independent review of exact procedure still required |
| Stop original daemon, start temporary daemon, then restore original service | confirmed | independently accepted rollback protocol still required |
| Restore/verify original installation; no recalibration or permanent install | confirmed | discrepancies must still be disclosed rather than erased |
| One 3° outward head leg | not requested; no approval inferred | explicit later yes + independent approval + fresh preflight + separate operator authorization |
| One separately authorized return leg | not requested; no approval inferred | explicit later yes + successful outward observation + new preflight + new authorization |
| Publish derived non-media data/code | not requested in this exchange | preserve existing privacy boundary; seek permission if owner-related material would be published |
| Disassembly or mechanical calibration | prohibited unless separately requested and approved | not requested |
| Torque/motor-mode changes or autonomous tracking | prohibited | not requested |

## Evidence record

Preserve the actual reply as a private text export or screenshot and hash its
bytes. A structured record should identify that artifact; it must not replace
it:

```json
{
  "schema": "reachy-stage4a-owner-scope-record-v2",
  "decision": "SCOPE_CONFIRMED",
  "recorded_by": "the robot owner's name or stable identifier",
  "recorded_at_utc": "YYYY-MM-DDTHH:MM:SSZ",
  "source_artifact": {
    "path": "owner_reply.txt",
    "sha256": "64 lowercase hexadecimal characters"
  },
  "approved_actions": [
    "powered_baseline_inventory_and_receive_only_capture",
    "temporary_target_state_observability_environment",
    "stop_original_start_temporary_and_restore_original_daemon"
  ],
  "motion_scope": {
    "target_leg": "yes/no/conditional",
    "separately_authorized_return_leg": "yes/no/conditional"
  },
  "publication_scope": "owner's exact response",
  "return_condition_definition": "owner's exact response",
  "conditions": []
}
```

[`external_records.py`](../reachy_stage4/external_records.py) can verify the
artifact hash and mandatory observability actions. It cannot authenticate who
sent a message or turn a manually entered record into proof of identity; the
original reply remains the source evidence.
