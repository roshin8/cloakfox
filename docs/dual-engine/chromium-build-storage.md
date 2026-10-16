# Chromium build storage after retiring the 157 worktree

The permanent build home is `/Users/zeus/cloakfox-builds/chromium`:

| Content | Location beneath that directory |
| --- | --- |
| Chromium and CEF source | `full-source/chromium/src` |
| Build orchestration and native patch originals | `full-source-tools` |
| Probe virtualenv | `full-source-tools/probe-venv` |
| Downloaded original CEF SDK/archive | `cef_binary_154.0.34+g14c5a08+chromium-154.0.8037.98_macosarm64` and matching tarball |
| Preserved original binary-SDK companion build | `legacy-binary-sdk-build` |

The maintained 158 checkout has ignored `.cef-prototype` links to these inputs.
Current orchestration scripts reference 158; virtualenv launchers reference the
permanent build home. Original scripts are backed up there. Historical build
provenance and logs retain their original paths; the relocation journal records
the moves. Other ignored 157 files were preserved in
`/Users/zeus/cloakfox-builds/legacy-157`, including the old Gecko build and packages.

Compiled objects, source SDKs and logs remain on `/Volumes/CloakfoxChromiumBuild`.
The disk image stays at `/Volumes/Untitled/CloakfoxChromiumBuild.sparsebundle`.
The local patched companion in the 158 checkout remains self-contained and needs
no external volume at runtime.

GN configuration is refreshed for the new source path. The compiled objects are
preserved; moving source invalidates absolute dependency/command paths, so a
future native build may need recompilation. Relocation does not perform a full
Chromium rebuild. Existing historical CMake caches are preserved as evidence;
use the maintained repo and a new build directory when rebuilding those variants.

See the permanent build home's `README.md` for build commands and
`/Volumes/CloakfoxChromiumBuild/source-build/source-location.json` for the active
source/tool paths. Native patch/source hash checks, SDK/app preservation checks
and the relocated probe runtime are verified before the old worktree is archived.

## Retirement verification — 2026-10-15

All 13 moved roots remain present. Native source patch replay/idempotence and
final hashes pass; source/SDK/embedded framework hashes and all three older SDK
frameworks/original binary companion remain unchanged. GN generated 34,454 targets
from 4,990 files at the new location. The relocated probe virtualenv passes the
owned TCP/QUIC certificate-rejection checks. Both engines pass the concurrent
storage/lifecycle probe after removal of the old worktree.

The old worktree was archived through Codex with a recoverable Git snapshot, then
`codex/dual-engine-prototype` was deleted locally and on origin. Its implementation
history remains merged into `codex/firefox-158-port`. See
[the relocation record](chromium-relocation-20261015.json).
