# Full pinned Chromium/CEF framework build and verification

User explicitly authorized the full source build using the experimental Apple
Command Line Tools path. No Apple sign-in, Xcode installation, global toolchain
selection or drive reformatting. Reuse codex/dual-engine-prototype.

1. Create a growing APFS sparse build image on the external ExFAT drive. Pin CEF
   commit 14c5a089e8452874cb1a556dc3fde26ed2d87723 and Chromium tag 154.0.8037.98.
   Keep the large checkout and output external; small depot_tools/CIPD caches may
   use the internal SSD because external synchronous cache updates are very slow.
2. Fetch source/dependencies without hooks/history. Apply the matching CEF patches,
   apply the pinned CLT adaptation, then run necessary Chromium hooks and CEF
   generation. Record tool revisions/arguments. Fail clearly on missing real tools;
   do not fabricate tools, disable sandboxing or bypass certificate checks.
3. Build //cef:cef_framework plus the distribution's sandbox prerequisites in one
   non-component arm64 release configuration, without symbols/ThinLTO. Target the
   framework rather than nib-based sample apps that require missing ibtool.
4. Package a source-built CEF SDK, build the native companion against it into a
   separate build directory, and verify actual CEF version/framework provenance.
5. Run container/popup/protocol, sandbox/permissions/crash and native transport
   probes against the new companion. Preserve the existing binary SDK, prototype
   and Gecko DMG. Report full success only with an actual linked framework and
   passing runtime evidence; otherwise record the exact blocking stage.
