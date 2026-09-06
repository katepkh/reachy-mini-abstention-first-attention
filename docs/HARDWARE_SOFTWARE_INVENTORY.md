# Hardware and software inventory

Status: public, privacy-minimized inventory for the present research preview. Unknown fields are kept unknown rather than inferred from screenshots or operating-system defaults.

## Robot-side record

| Item | Recorded value | Evidence boundary |
|---|---|---|
| Robot | One borrowed Reachy Mini Wireless | Single unit; serial number and owner identity are not public. |
| Desktop application | v0.9.34 | Observed during the September 2026 command-free startup series. |
| Daemon | v1.9.0 | Observed in the desktop application and used for exact-tag source reconstruction. |
| Motor discovery | 9/9 motors found during maintenance triage | Discovery does not validate calibration, geometry, torque state, or safe recovery. |
| Low-level controller source reviewed | `reachy-mini-motor-controller` v1.5.5 | Source-review reference; not asserted as a readback of installed firmware. |
| Analytical kinematics source | Reachy Mini v1.9.0 plus Rust kinematics 1.0.3 for offline review | Offline calculation only. |
| Observational patch | Not installed | No receive-only present/target hardware trace has run. |

## Acquisition-computer record

| Item | Recorded value | Evidence boundary |
|---|---|---|
| Operating system at paper build | Windows 11, build 26200, x64 | Build environment; historical acquisition builds were not separately frozen. |
| Processor family at paper build | Intel64 Family 6 Model 158 Stepping 10 | Privacy-minimized identifier; exact laptop make/model is not public. |
| Paper/test Python | CPython 3.12.13, 64 bit | Resolved environment is recorded in `requirements-test.lock`. |
| Project minimum Python | 3.11 | Declared in `pyproject.toml`; the frozen paper environment and CI use Python 3.12. |
| V2 browser model | MediaPipe Face Landmarker float16/1 | SHA-256 `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`. |
| V2 browser runtime | `@mediapipe/tasks-vision` 1.0.1 | Tarball SHA-256 `ee318eaa3d42230aa10910d114faf2a488c577c4e4d33c7cb04126924aca505f`. |
| Camera make/model used for V2 | Not recorded in the public pilot artifact | Must be privately bound before confirmation. |
| Microphone make/model and selected input used for V2 | Not recorded in the public pilot artifact | Device dependence is a stated validity threat; do not infer it from successful capture. |
| Browser version used for V2 | Not recorded in the public pilot artifact | The pinned model/runtime narrows but does not eliminate browser dependence. |

## Dependency records

- `requirements-test.lock` records the resolved Python test environment used for the final paper verification.
- `pyproject.toml` remains the supported range declaration rather than a claim that future resolver output is identical.
- `evidence/manifests/av_synchrony_pilot_protocol_v2.json` and the private candidate freeze bind browser-model assets and implementation hashes.
- `docs/paper/generated/ARTIFACT_MANIFEST.json` binds every source, table, and figure used in the manuscript.

## Confirmation-study additions required

Before confirmation collection, the operator must privately bind the exact rooms, camera, microphone/audio input, browser, playback device, two consented recording hashes, volume, positions, and media settings. A headset microphone may be used only if fixed on a marked stand; wearing it would change source-to-sensor geometry across conditions.
