# Playback preflight diagnostic

## Successor: three-position direction diagnostic (D028)

This separate tool advances M5–M6 by investigating the measured-versus-marked
direction discrepancy. It produces diagnostic observations, not pilot evidence,
calibration certification, or playback rejection. It displaces no higher-value
task. Stop after one three-position sequence, after an interrupted capture, or
if changing a frozen file, seal, threshold or robot authority would be required.
The earlier single-position diagnostic below remains unchanged.

Run `start_robot_direction_diagnostic.cmd`, then open
`http://127.0.0.1:8770/tools/robot_direction_diagnostic.html`. Stop previous
pilot/diagnostic servers with Ctrl+C and close their tabs first. Keep this new
terminal open throughout the check. Do not run any robot applications that move
the head; the diagnostic cannot command motion or a response.

The page guides exactly one 10-second capture at each position, in this order:

| Check | Single phone position, relative to Reachy's current head-forward axis | Nominal raw DoA axis |
|---|---|---|
| 1 | Front, 0° | 90° |
| 2 | 60° to Reachy's own left | 30° |
| 3 | 60° to Reachy's own right | 150° |

These nominal values use Pollen v1.9's documented `0=left, 90=front/back,
180=right` convention. They are predictions from manually established marks,
not measured ground truth or a new tolerance. The front/back ambiguity remains.
Positive stored face/sound bearings mean robot-left. The new metadata states
this explicitly and retains the inherited mislabelled contract separately.

Keep Reachy, its head, laptop, and existing marks fixed. Stay silent with your
face visible at the usual one-metre front mark. Use **one** iPhone 11, the same
recording, and **50%** volume. Use the existing right-hand phone mark's horizontal
distance from Reachy's head as the reference for all three positions; measure
and enter it in centimetres. For this diagnostic, keep the phone speaker level
with Reachy's head/microphones at every position, to avoid varying elevation.
This is explicitly confirmed by the operator, not sensor-measured. Add temporary front
and left marks, without moving the existing marks. Maintain the phone speaker's
orientation toward Reachy. Facing the robot, its right is your left.

Initialize the model, enable the matching laptop microphone, and confirm the
current phone placement. Restart the same recording from its beginning just
before each Record click, and let it play throughout. Stop playback before
moving only the phone. The microphone stops after each capture; use Prepare
next position and enable it again. Missing speech, missing/stale DoA, or
unexpected direction do not block capture; camera/face/processing and matching
microphone readiness still apply. Do not reposition to make a number pass.

Each position produces a separately named CSV/JSON pair in the distinct
`reachy-direction-diagnostic-capture-v1` schema. Send **all six files** after
the sequence. Summary statistics use only fresh, speech-active, in-range DoA;
raw observations including missing speech remain in the CSV. Camera/face loss
is retained, and does not silently erase an otherwise usable acoustic reading.
Rows are correlated repeated telemetry, not independent experimental trials.
No calibration fit, automatic correction, pass/fail, or pilot acceptance occurs.

The dedicated loopback origin keeps numeric CSV/JSON recovery copies in browser
local storage, keyed by build and binding. Download links survive reload; no
raw audio/video is retained. A capture is reserved before recording. Reload
during recording blocks continuation for review instead of allowing a silent
retry; previously completed pairs remain downloadable. An explicit early stop
exports the partial pair and stops the series. Storage/lock failures fail closed.
After all three checks, reload offers saved files only. Keep the files and the
browser recovery copies until review; clearing browser data is not permission
to repeat. The separate pilot browser storage, private setup and attempts are
never written. Close the page and Ctrl+C the server when done.

The new build fingerprints its own page, helpers and launcher plus the inherited
diagnostic build, which binds the unchanged pilot execution and commissioned
pipeline/model. HTTP access remains loopback-only and GET-only, with exact
asset/endpoint allowlists; no pilot page or private data path is served.

### Successor software verification

396 Python tests and 24 JavaScript tests pass. The synthetic-only browser check
records the full front/left/right sequence with no speech, unexpected direction,
and missing DoA, respectively; checks all six filename/position/hash-bound
exports, fixed distance, confirmation reset, microphone stop, reload recovery
without repeat, early-stop export, microphone mismatch and unchanged pilot
storage. The existing execution/private seal verifies unchanged. No live sensor
was opened for implementation testing; physical calibration remains unverified.

## Earlier single-position check (D027)

This work advances M5–M6 and the charter's live-speaker/playback distinction by
removing a diagnostic-observability blocker. It produces separate receive-only
instrumentation, not pilot evidence or a discrimination result. It displaces no
higher-value task. Stop after one diagnostic pair for review; stop implementation
if it would require changing a frozen pilot file, seal, gate or robot authority.

## Boundary

The operator reports fixed phone playback while the pilot page reports
`speech=false` and a direction warning. One screenshot cannot establish the
duration or acoustic cause. The original warning checks geometry even when
speech is false; it does not establish that the phone was physically misplaced.

The separate diagnostic uses the same commissioned camera/landmark/DoA pipeline
and sealed external microphone. Its page and loopback server are separate, with
a separate build fingerprint and `reachy-playback-diagnostic-capture-v1` schema.
It reads and verifies the existing seal but never writes pilot state, consumes
a pilot attempt, fits a candidate, opens validation, or changes an acceptance
threshold. Its downloads cannot be imported through the unchanged pilot schema
check. Do not rename/relabel them as trials. The diagnostic is not a substitute
for a failed pilot acquisition or permission to repeat outcomes.

The diagnostic start gate retains initialized landmarks, fresh usable camera,
face/processing quality, matching active microphone and explicit operator setup
confirmation. Speech, direction disagreement and absent/stale DoA are recorded
without blocking this diagnostic. Raw DoA is preserved, but direction is marked
unusable when speech is false or DoA is stale. Original pilot condition warnings
are retained for comparison, not displayed as placement instructions. Missing
speech is not a successful hard-negative rejection. Numeric summary counts are
correlated telemetry samples, not independent trials.

## Operator workflow

1. Stop the old pilot/commissioning terminal with Ctrl+C and close its browser
   tab so it cannot keep another sensor stream active.
2. Run `start_robot_camera_diagnostic.cmd` and keep the terminal open.
3. Open `http://127.0.0.1:8769/tools/robot_camera_diagnostic.html`.
4. Initialize the model; enable the laptop microphone. Keep the existing marks
   and fixed 50% iPhone volume. Stay silent at the front mark; phone remains at
   the 60-degree mark to Reachy's right.
5. Play the same recording aloud through the iPhone speaker and tick the setup
   confirmation. Restart it immediately before **Record 10-second diagnostic**.
   Speech/direction warnings do not disable that button.
6. Send the diagnostic CSV and metadata JSON. Links remain on the page if the
   browser blocks automatic downloads. The microphone stops after capture.

Stop microphone also ends an in-progress capture and exports a marked partial
pair. No waveform, pixels, transcript, or identity embedding is saved or uploaded.
No movement, response, firmware change, publication or live capture is authorized
by implementation tests. All test sensors are synthetic.

## Verification

The full Python suite passed (391 tests), including distinct-schema import
rejection, GET-only HTTP boundaries and seal verification without pilot writes.
Nineteen JavaScript tests passed. A headless browser exported 251 hash-bound
numeric rows while speech stayed false; unexpected direction and unavailable
DoA also left the diagnostic start button available. Early stop exported a
partial pair, microphone mismatch blocked capture, recovery download links
remained visible, and pilot browser storage was unchanged. The original pilot
execution fingerprint and private seal still verify, with zero accepted trials
and Trial 1 / attempt 1 unchanged. This tests software, not the live acoustic
cause or pilot discrimination.
