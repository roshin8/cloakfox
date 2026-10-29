# Firefox159 GPU realism investigation and real-media verification

## Real camera, microphone and shared-window result

The explicit Firefox159 acceptance app passed real capture with the privacy master
switch enabled, fake devices off and permission bypass off. A disposable profile
requested normal browser/OS permission. Browser UI identified the FaceTime HD
camera and MacBook Pro microphone; the user selected the local test window for
sharing. No external service received media. Nothing was saved except scalar
metrics; encoded media chunks were discarded in memory and tracks stopped.

| Path | Observed |
| --- | --- |
| Real camera |59 decoded frames,640×480, live and unmuted |
| Real microphone |15,360 nonzero sample observations, varying waveform |
| Combined capture/encoding |71,752 bytes produced in memory |
| Real window sharing |92 decoded frames,1280×975, live and unmuted |
| Shared-window encoding |698,332 bytes produced in memory |

These verify local capture/decoding/encoding under the tested default protected
configuration. They do not certify remote HackerRank/Zoom transport, every optional
privacy toggle, a rebuilt installer, or every physical device. The raw capture
receipt is `physical-media.json`. This is the existing159 build, not a new build.

`manual_real_media.py` preserves this manual workflow behind explicit physical
media opt-in. Review found a possible stall retaining streams; an independent8s
watchdog and outer-timeout abort now stop them. Late asynchronous continuation
is checked before further resources are created. Five Node tests cover playback,
audio-start and recorder-stop stalls, late resolution and successful cleanup.
The physical run preceded that fixture-only hardening; its media flow is unchanged,
and no second physical capture was needed to exercise the cancellation logic.

## GPU findings — remains unfinished

All four BrowserForge-family profiles were measured in separate disposable
containers on159, with actual WebGL1/2 and WebGPU execution. No native product
code, privacy defaults, sandbox or hardware blocklist was changed.

The fixed8×8 WebGL corpus differed from the local master-off control in20 of256
channels, by at most1 byte, for each protected family. This small corpus had the
same protected pixel hash across families, while resource ceilings/uniform counts
differed. That neither proves driver equivalence nor establishes a new privacy
leak: canonical rendering intentionally removes host dependence, and a simple
shader can legitimately render identically across drivers. The implementation
still uses a common software backend, not four physical-driver emulators.

`local-gpu-corpus.json` retains actual authored-pixel results, capability/precision
observations and owner identifiers. No persona secret or user media is included.
It deliberately leaves `validatedEmulationProfiles` empty. The local browser's
sanitized GPU label is not an exact hardware/driver reference either.

## Online references researched

- [GPUInfo](https://opengl.gpuinfo.org/about.php) provides community desktop OpenGL
  capabilities by hardware/driver. These are not interchangeable with Firefox
  WebGL tables, WebGPU limits, or shader-execution output. Direct access returned403;
  readable cached pages were used only as background evidence.
- [Skia Gold](https://docs.skia.org/docs/dev/testing/skiagold/) maintains rendering
  baselines across OS/architecture/backend configurations. The public ANGLE metadata
  snapshot was retrieved through its documented v2 API; it contains Intel/NVIDIA
  traces but no Apple/AMD traces in this window, and is not a matching Firefox159
  corpus. Chrome Gold's API returned401 and was not bypassed.
- [WebGPU CTS](https://github.com/gpuweb/cts) is a conformance corpus, not a vendor
  emulation database.

Source URLs, access results and the downloaded metadata hash are recorded in
`online-reference-sources.json`. No local GPU/device data was uploaded.

An offline evidence checker now refuses capability-only/incomplete reports,
missing driver/backend provenance, mismatched browser/corpus/model, malformed
pixels and changed capabilities. Eleven Python tests cover those failures and
real-media receipt acceptance. Validation is structural, not authentication of a
claimed dataset; even an exact finite-corpus match never sets full emulation true.
No public dataset is consumed by production, and no detector recognition table
was substituted for rendering behavior.

## Remaining work

1. Obtain matching, versioned browser/model/backend/driver rendering and capability
   references for each required family, including shader/precision/boundary cases.
2. Implement the coherent catalog and any execution behavior needed to satisfy it,
   preserving owner/site isolation and the existing default-off toggle. Do not
   expose the host GPU or silently relabel the shared software backend.
3. Validate finite corpora and broader conformance/resource cases before marking
   individual model profiles supported. Keep unsupported coverage explicit.

This work does not close GPU realism. Native rebuild work was not started: disk
space dropped below1GiB during the task, and no checkpoints/builds were deleted or
interrupted to free space. Chromium's build inputs and processes were untouched.
Independent review found no remaining actionable issue after the fixture fixes.
