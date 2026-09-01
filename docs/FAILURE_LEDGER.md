# Failure ledger

## Why keep a failure ledger?

An embodied-system result is not trustworthy if unsuccessful attempts disappear, a post-hoc threshold turns red into green, or a new protocol inherits an old label. This ledger makes those boundaries explicit.

## Stage 2A: source ownership failure

**Observed:** a silent visible face plus spatially separate phone speech produced 13 confirmations over 63 tracked rows.

**Meaning:** angular agreement can be caused by reflection, endpoint variation, or coincidence. A visible face spatially compatible with DoA is not proof that the person is speaking.

**Response:** kept the system passive; added stricter temporal consensus and hard-negative selection criteria. No identity claim was introduced.

## Stage 2A: visual boundary degradation

**Observed:** a single face at the image edge frequently appeared as no face or multiple faces.

**Meaning:** detector state is not a stable proxy for the number of people at a boundary.

**Response:** missing, multiple, stale, and boundary-unstable observations lock out passive target confirmation.

## Stage 3P versions before V6

Earlier vertical-policy versions produced wrong-sign, accuracy, coverage, and pre-transition-association failures. Their frozen manifests remain in `evidence/manifests/`. New policy versions were created; old outcomes were not overwritten.

## Stage 4A V3 physical pilot

**Observed:** a requested 3° head-only movement yielded 1.349887° robust measured motion. Target error was 2.079459° and return error was 1.677847°. The mechanical gate failed.

**Diagnostic root causes:**

1. target pose sampled before the frozen settling dwell;
2. return pose sampled with no settling dwell;
3. trace angle applied directly to slightly non-orthonormal forward-kinematics matrices;
4. absolute-neutral targeting did not guarantee a 3° increment from the captured baseline.

**Integrity decision:** the failed trial remains frozen and failed. Thresholds were not weakened, and the same protocol may not be rerun as though fresh. A corrected protocol must receive a new fingerprint and new evidence.

**Current blocker:** after power cycles and visible controller zeroing, read-only preflight still reported the head 2.49°–4.43° from the daemon's neutral reference. Motor discovery/configuration diagnostics found all 9 motors and all inspected configuration fields OK. This separates bus/configuration health from coordinate-frame/readiness agreement; it does not justify bypassing the gate.
