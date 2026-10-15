# Canonical media producer work

The Mac experiment routes clear H.264, HEVC and AV1 decoding through the bundled
FFVPX module inside the existing remote decoder boundary. The Apple video module
keeps its established behavior when the experiment is off, and audio/encrypted
paths retain their existing security semantics. VPx alpha/SVC retains the bundled
VPX decoder instead of losing support. Decoder policy is captured per instance;
software DSP/bit-exact/fixed thread policy and successful decoding determine the
native decode marker. An old decoder never gains that marker after a pref change.

The scalar color path handles planar/interleaved input through existing native
plane extraction, 8/10/12/16-bit samples, full/limited range, 601/709/2020 matrix
coefficients, fixed D65 gamut transforms, SDR/linear/PQ/HLG transfer functions,
picture crop/center sampling, alpha and destination channel order. It uses the
bundled fdlibm and disables floating point contraction. HDR output has a fixed
100-nit SDR reference and clips at the output boundary. It never samples monitor
profiles, brightness, GPU conversion or platform color libraries. Tagged sRGB
RGB inputs retain exact bytes. The chosen SDR rendering and chroma sampling are
versioned policy choices, not a promise to reproduce every host player's colors.

The converter returns proof of the branch that actually produced the pixels.
Consumers stamp `CanonicalColorConversion` only from successful conversion's
returned proof; they never reread a live preference to classify old pixels.
Decode and conversion markers are independent of the owning policy record. Missing
or conflicting ownership stays unknown. Fresh successful decoded images establish
an ownerless native decode record; later fixed scalar conversion completes its
import proof. Existing assigned Unknown records are never cleared. Only the
strict native import predicate may accept the complete ownerless producer record;
the receiving canvas retains its own owner. Markers do not confer origin-clean or
permissions.

## Source review

The original Gecko FFVPX tree deliberately excludes the H.264/HEVC implementation;
enabling decoder configuration bits alone cannot provide those decoders. The
missing C decoder/helper subset is imported from the exact FFmpeg 9.0.1 release,
matching Gecko's vendored ABI, with per-file upstream/import hashes in
`additions/media/ffvpx/canonical-codec-manifest.json`. The release archive signature
was verified with the fingerprint published on the
[official download page](https://ffmpeg.org/download.html):
`FCF986EA15E6E293A5644F10B4322F04D67658D8`. Archive SHA256:
`cf38e0e28c7e5605942c4a77755349b0145804a397af37eb1fb4c77cb237f635`.
The detached signature and public key are retained beside this document.

The selected upstream configure invocation reports LGPL 2.1 or later; no GPL or
nonfree optional component is enabled. Source notices remain intact. The existing
Gecko no-op Dolby Vision encoder helpers remain no-op; the actual decoder metadata
structures/helpers are imported. New decoder translation units select generic C,
with platform SIMD entry points disabled for those units. Existing libavutil
helpers needed by the decoders are exported by name rather than supplied by a host
library. FFmpeg's [official licensing page](https://ffmpeg.org/legal.html) explains
source/linking obligations and distinguishes licensing from patent questions;
this implementation does not assert jurisdiction-independent patent clearance.

## Recorded verification

- Actual newly linked `libmozavcodec`/`libmozavutil` decode Gecko's black H.264 and
  white HEVC fixtures to exact Y=16/235 and neutral chroma. Luma-plane dimensions
  and output hashes are recorded in `media-codec-corpus.json`.
- A 28-case native first-frame corpus exercises H.264/HEVC/VP9/AV1, 8/10-bit,
  full/limited, GBR, BT709/BT2020, PQ and HLG. FFmpeg generic C and available
  SIMD decoding agree on this Mac. The recorded initial AV1 comparison predates
  the independent bundled dav1d CPU-mask hook and must be rerun after the integrated
  build to establish AV1 C-dispatch coverage. This is not cross-host acceptance or
  a full-stream media compatibility assessment.
- Executable native scalar tests link actual bundled fdlibm and exercise ranges,
  depths, transfer math, unaligned/pixel/negative row strides, crop, alpha,
  channel layout, invalid arguments, gamut conversion and exact authored sRGB.
  Premultiplied source color is unpremultiplied before transfer/gamut conversion;
  explicit output premultiply/unpremultiply operations retain their direction.
  P010/P210 storage is unpacked into logical ten-bit samples; all 1,024 full-range
  values match the equivalent planar representation.
- An explicit preference-race regression changes the preference in the legacy
  conversion branch and confirms it cannot acquire canonical proof afterward.
  A decoder creation regression changes the preference during CPU configuration
  and confirms the constructor receives the same captured request as DSP setup.

The initial `mach build media/ffvpx` was a no-op because Mach requires
`--allow-subdirectory-build`. Subsequent real build failures and corrections are
retained in numbered logs; only real compilation/linking counts as evidence.
The root task owns browser integration, installed/runtime transfer probes,
replacement gates and release status.

Raw WebCodecs Buffer constructors keep original YUV planes or RGB bytes for
`copyTo`. Successful copied YUV input stores a native private authored-buffer
flag; only a successful scalar RGB snapshot obtains completed raster proof.
RGB uses a separate fixed sRGB premultiplied rendered surface and retains the
original copied surface for byte-preserving `copyTo`. Generic native image
conversions and captured/host surfaces cannot request this authored-buffer path.
Gecko's existing same-process VideoFrame serialization retains the original Image
object and this frozen flag; no new cross-process clone permission is introduced.
