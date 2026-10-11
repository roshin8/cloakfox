# Cloakfox

A Firefox-based privacy browser with native fingerprint controls and container
identities. This worktree targets **Firefox 155.0.1** and keeps the cpp-first
architecture described in [CLAUDE.md](CLAUDE.md).

## Architecture

- **Gecko/C++ patches:** container configuration, canvas and WebGL readback,
  audio, font/layout metrics, navigator, screen, timezone and native network policy.
- **Privileged JSWindowActors:** Math, keyboard, timing and other page-facing
  surfaces that need JavaScript. Cloakfox Shield provides management UI and a
  privileged configuration bridge; it has no MAIN-world injection scripts.
- **Identity configuration:** a persistent container secret selects a broad
  Firefox persona. Protected noise keys use HMAC-SHA256 with Gecko’s top-level
  schemeful site, propagated to frames and workers. Related subdomains share a
  site key; distinct top-level sites receive distinct keys. Broad persona fields
  remain container-scoped, so this is not a guarantee of unlinkability.
- **Daily controls:** `about:cloakfox` manages identities, data clearing, routes,
  exact-host container rules, temporary containers and encrypted settings backups.

RFP remains disabled because it conflicts with Cloakfox’s native controls;
Firefox containers remain enabled. Generated User-Agent versions follow the
engine version, including migration of older stored personas.

## Daily-driver privacy work

The Firefox 155 worktree adds:

- Letterboxing with geometry/fullscreen probes.
- Persistent everyday preferences and HTTPS-Only defaults.
- A bundled, signed upstream uBlock Origin package. Users can disable/remove it,
  use its normal per-site controls, and receive normal addon/filter updates.
- Explicit container data forgetting, separate from changing appearance. It
  closes target tabs, clears site data and prunes current and fallback restore
  records. Shared history, passwords, bookmarks and ambiguous shared permissions
  are retained. This does not erase external profile copies or OS snapshots.
- Per-container required-proxy/blocked modes with no direct fallback, plus native
  WebRTC disabled/relay modes. Required-proxy containers disable WebRTC. Native
  proxy bypass destinations are rejected. Existing downloads can continue when
  a route changes; this is not a system-wide VPN kill switch.
- Public-IP lookup off by default, with an explicit opt-in and disclosure.
- Native exact-host container rules. Firefox’s opener/named-target exceptions
  still apply. Temporary containers clear on final tab/window closure and recover
  unfinished cleanup on the next startup.
- Password-encrypted named-container settings backups imported into fresh IDs.
  Cookies, passwords, history and bookmarks are excluded. Native full-profile
  backup settings are offered only when the platform/build supports them.

The Octo-inspired controls are also available in `about:cloakfox`:

- **Region:** one manual record for language headers, window/worker languages,
  formatting locale, timezone and optional coarse coordinates. Location still
  requires site permission. Explicit Intl locales remain intact.
- **Consistency inspector:** compares configured fields with an open normal-window
  tab and its worker, separates measured contradictions from heuristics, and offers
  narrow reversible repairs. It sends no network requests and does not certify
  anonymity.
- **Privacy policies:** standard, strict and geometry-compatible presets, plus
  expiring top-level site exceptions for geometry, canvas/WebGL readback and audio.
  Changing these settings preserves the identity secret. Reload pages/restart
  workers after changes to clear cached results.
- **Templates:** settings-only reuse with fresh secrets and empty storage. Includes
  optional region, policy, pinned persona, proxy reference, opening pages and
  temporary-container lifecycle.
- **Named proxies:** HTTP/HTTPS Basic or SOCKS5 credentials stored in Firefox's
  password manager, isolated by container and proxy revision. Rejected credentials
  fail closed without authentication prompts/retries. Optional user-supplied HTTPS
  diagnostics test reachability through the selected proxy.

Region discovery is manual; diagnostics do not infer an exit location. Templates
exclude credentials and refer to proxies already saved in this profile.

Additional privacy controls in `about:cloakfox`:

- Native tracking-link cleanup and bounce-storage purging, with URL-cleanup
  exceptions and expiring container-specific bounce exceptions.
- Browser-wide encrypted DNS with explicit system fallback or a native
  fail-closed guard, HTTPS endpoint validation and numeric resolver bootstrap.
- Stored permission grants with revocation, timed expiry and session expiry.
  Temporary tab grants remain in Firefox's tab permission controls.
- Separate-profile workspaces with independent passwords, history, extensions,
  settings and website sign-ins, created through Firefox's profile service.
- Host-compatible complete personas for new identities; existing identities keep
  their appearance until explicitly changed. The substitute-font bundle includes
  a validated hash manifest, attribution and licenses.
- Backup v2 includes regions, policies, opening pages, persona mode and proxy
  references, while retaining v1 import. Missing proxy references restore blocked.
  Host-compatible appearances adapt when imported onto a different operating
  system; the backup flow warns about this separately from preserving seeds.

Worker configuration changes propagate into existing workers for subsequent
native policy checks. Cached script results and already-created Intl objects
still require recreation. Runtime coverage and limitations are recorded in
[the current implementation report](docs/privacy-completion/README.md).

**Release limitations:** automatic updates remain disabled in development builds.
Owner-controlled MAR trust keys, HTTPS hosting and platform signing are required
for activation. The release tooling prepares authenticated native updater inputs,
verifies signed MARs and produces Firefox update XML; the release CI checks engine
freshness against Mozilla's live feed. See [release activation](docs/release/authenticated-updates.md).
This build lacks the Google Safe Browsing provider key. Settings checks the actual
local classifier lists and provider update age, and reports unavailable protection
rather than treating enabled preferences as successful list downloads.

Implementation reports and verification evidence are in
[docs/daily-driver-privacy](docs/daily-driver-privacy/). The original comparison is
[the feature-gap audit](docs/privacy-feature-gap-audit-2026-09-07.md).

## Build and test

A native build needs Mozilla’s supported Firefox toolchain, Python, Node.js,
Rust and cbindgen 0.29.4. The macOS port uses the toolchain recorded in
[the Firefox 155 port report](docs/firefox-155-compat/).

```sh
make fetch
make setup-minimal
make dir
make extension
make build
```

`make dir` applies the ordered patch stack. Do not apply it again to an already
patched source tree. `scripts/copy-additions.sh` also stages the pinned official
uBlock XPI and verifies cached/downloaded bytes against its manifest.

Pure regressions run with Node and Python. Live probes use Selenium and
geckodriver with disposable profiles; see
[tests/fingerprint/README.md](tests/fingerprint/README.md). No Vitest suite or
Juggler/Playwright browser API is provided on this branch.

```sh
node --test tests/fingerprint/test_*.mjs
python -m unittest discover -s tests/release
python -m unittest discover -s tests/blocker
python -m unittest discover -s tests/network
CLOAKFOX_BIN=/absolute/path/to/cloakfox python tests/fingerprint/run_daily_driver.py --output /tmp/cloakfox-daily-results
```

## Repository

- `patches/` and `patches/order.txt`: Gecko patches, followed by LibreWolf patches.
- `additions/cloakcfg/`: native configuration and site-seed helpers.
- `additions/browser/components/cloakfox/`: privileged modules, actors and settings.
- `additions/browser/extensions/cloakfox-shield/`: extension management UI/bridge.
- `settings/`: AutoConfig defaults, policies and blocker manifest.
- `scripts/`: fetch, staging, patch, build, packaging and release verification.
- `tests/fingerprint/`: behavioral regressions and live probes.

## FAQ

### macOS says "Cloakfox can't be opened because Apple cannot check it for malicious software"

This is normal for unsigned apps. Go to **System Settings → Privacy & Security**, scroll down — you'll see a message about Cloakfox being blocked. Click **"Open Anyway"**.

Alternatively, run this in Terminal before first launch:
```bash
xattr -dr com.apple.quarantine /Applications/Cloakfox.app
```

## License

MPL-2.0 — same as Firefox/Camoufox.

## Credits

- [Camoufox](https://github.com/daijro/camoufox) by daijro — C++ fingerprint spoofing engine
- [Firefox](https://www.mozilla.org/firefox/) by Mozilla — browser foundation
- [LibreWolf](https://librewolf.net/) — data reporting and build patches

### Bundled container extensions

Cloakfox includes the actual AMO-signed Firefox Multi-Account Containers 8.3.8
and Temporary Containers 1.9.2 extensions, alongside Cloakfox Shield and uBlock
Origin. Native container features are not substitutes for these extensions.
The distribution installs them into fresh profiles, with normal extension
management and AMO updates retained. Existing installations are not reset.

Package pins are in `settings/container-addons.json`. The build setup stages
verified packages with `scripts/stage_container_addons.py`; a missing or
modified package fails staging. Firefox validates the signatures on installation.
`probe_bundled_containers.py` verifies both are active and signed on first
launch and after restart in a disposable profile. This test verifies bundling,
not every interaction between native rules and extension automation.
