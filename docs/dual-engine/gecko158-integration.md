# Chromium alongside Gecko 158

Merged the complete `codex/dual-engine-prototype` history through `a7afa2c1a7`
onto Gecko 158 parent `cade27d4f8`. The merge changes Chromium, engine tests,
verification documents and ignore rules. Gecko source, configuration and existing
application remain unchanged. This is the separate companion architecture;
shared settings, tabs and a combined release package remain pending.

## Verified on 2026-10-15

- Gecko 158.0-beta.26: 295 Node tests, 132 binary-enabled Python tests and six
  targeted runtime probes passed (defaults, site isolation, container workflows,
  settings UI, worker lifecycle and network policy).
- The companion rebuilt from this 158 checkout against the pinned source-built
  Chromium154/CEF SDK: all 68 engine tests and one C++ test passed.
- Native Metal/WebGL rendering, macOS renderer sandbox and storage isolation
  passed. TCP/QUIC fixtures still reject untrusted certificates; authenticated
  H2/H3 SETTINGS/ticket isolation is not claimed.
- Both engines ran concurrently against the same owned origin in disposable
  profiles. Cookies, localStorage and IndexedDB stayed engine/container-owned.
  Chromium private-context regeneration, stable canvas reads, Chromium restart,
  and either engine remaining usable after the other exits passed.
- The simultaneous check passed again using the local copied companion. Its
  opaque RGBA/BGRA/sRGB GPU readback regression also passed after relocation.
- Source output, SDK, original patched companion and 158 companion framework
  SHA256 match: `a7cd6e1b16a8a2bb555e03a616a4be0f727ba97c590f9d5572c660db64ab20ed`.
  All local app symlinks resolve inside its bundle. Native patch verification
  passes from this checkout against the preserved Chromium source.

The coexistence probe uses Gecko's default context and does not restart Gecko;
its assertions do not establish additional Gecko container/restart coverage.
Separate existing Gecko runtime probes exercise its container behavior. Privacy
parity between the engines is not claimed. Focused merge/probe review found no
blocking issue.

[Machine-readable result](gecko158-20261015/result.json),
[simultaneous run](gecko158-20261015/coexistence.json),
[local app run](gecko158-20261015/local-coexistence.json),
[Chromium tests](gecko158-20261015/chromium-tests.log),
[Gecko Python tests](gecko158-20261015/pytest.log),
[Gecko Node tests](gecko158-20261015/node.log).

## Launch and rerun

The local development app is at `engines/chromium/build/Release/CloakfoxChromium.app`
in this worktree. It contains the patched framework; running it does not need the
external drive. Launch disposable development windows with:

```sh
python3 engines/chromium/launch_prototype.py --url about:blank
```

The launcher uses a temporary profile and test Keychain mode. This is an
experimental companion, not the normal-account release configuration.

With Selenium/geckodriver installed, run both engines together:

```sh
python3 tests/engines/probe_dual_engine_coexistence.py \
  --gecko-binary /Applications/Cloakfox.app/Contents/MacOS/cloakfox \
  --chromium-binary engines/chromium/build/Release/CloakfoxChromium.app/Contents/MacOS/CloakfoxChromium \
  --require-pixel-privacy --report /tmp/cloakfox-dual-engine-result.json
```

Rebuilding the companion still needs the SDK on the build volume. If disconnected,
reconnect the external drive and mount `CloakfoxChromiumBuild.sparsebundle` from
its root. The Chromium source stays in the preserved `firefox-157-port` worktree;
that directory name is historical and is not the active Gecko version.
