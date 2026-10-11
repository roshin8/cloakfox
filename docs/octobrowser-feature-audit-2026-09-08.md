# Octo Browser comparison — 2026-09-08

Read-only feature audit against Cloakfox's Firefox 155 compatibility worktree.
No browser behavior was changed. Vendor descriptions were checked against local
source; Octo's binary and advertised checker results were not tested.

## Documented reference features

Octo advertises configurable fingerprints based on real devices, Android profiles,
and engine-level spoofing. [Fingerprint management](https://octobrowser.net/fingerprint-management/).
Its settings document region alignment, individual noise controls, hardware/media
settings, and warnings about manually edited identity fields.
[Profile settings](https://docs.octobrowser.net/en/profiles/browser-profile-settings/).
Reusable templates can hold settings while generated profiles receive distinct
noise. [Templates](https://docs.octobrowser.net/en/profiles/profile-templates/).
Its proxy manager includes credentials, connection status and exit information.
[Proxy manager](https://docs.octobrowser.net/en/proxy/proxy-manager/).
Separate profiles and password-protected synchronization are also documented.
[Profile management](https://docs.octobrowser.net/en/profiles/edit-profiles/).

## Recommended additions, in implementation order

### 1. Unified region configuration — medium effort, high value

Confirmed local gap: `CloakfoxPersonas.sys.mjs` lines 532–544 generate US English
headers/locale and coordinates from a US-city pool. The settings page separately
permits timezone, geolocation and RTC overrides. The proxy policy does not bind
these into a coherent region.

Add a per-container region record driving Accept-Language, navigator language(s),
Intl locale defaults, timezone and optional permission-gated coarse geolocation.
Offer manual regions first. Optional exit-region discovery must use that
container's enforced proxy route and an explicitly selected lookup provider;
manual mode should need no third-party request. IP geolocation is approximate:
never present its estimate as precise physical location. Language choice should
remain independent when the user deliberately prefers another language.

Tests: header/JS/worker agreement; DST and Intl formatting; geolocation permission
checks; proxy failure does not cause a direct lookup; switching containers does
not reuse another region's cached values.

### 2. Fingerprint consistency inspector — medium effort, high value

Our override setter checks recognized keys/types and merges fields independently
(`CloakfoxOverrides.sys.mjs:153` onward). A broader cross-field validation and
live diagnostics panel was not found. Add explanations for contradictions among
UA/version/platform, font families, GPU claims/capabilities, touch APIs/CSS, locale
and headers, or stale overrides. Provide a preview and reversible repair that
keeps the master seed, cookies and site data.

A local consistency report should distinguish measured mismatches from heuristics
and unsupported checks. A bilingual user or an IP/timezone difference is not
proof of a leak. Do not invent an anonymity percentage.

Tests: invalid combinations, intentional overrides, idempotent repair, no seed
rotation, and actual browser/worker observations rather than config-only checks.

### 3. Clear privacy presets and narrow site exceptions — medium–large effort

Noise controls and seed fields already exist, but they are not a unified
compatibility policy. Some geometry noise shares the canvas seed, so simply
zeroing it to repair a layout would also alter another protection.

Add named policies with explicit per-vector behavior and a top-level-site
exception such as disabling geometry perturbation for a broken editor while
retaining canvas/audio protection and container storage separation. Keep the
existing site-keyed default. Apply policy to native code and actors together;
show an expiry and reset control. Do not disable all protection merely to match
a checker score.

Tests: rendering/selection, frames/workers, exception expiry and scope, unchanged
unrelated noise, persistence, and live toggle behavior.

### 4. Reusable container templates — small–medium effort

Build on the current container workflows and encrypted settings export. Save
policy, region, proxy reference, opening pages and identity constraints, then
create each container with a fresh master secret. Copying settings must not copy
cookies, login state or fingerprint seeds. Examples: personal browsing, work,
research with temporary storage, and proxy-required browsing.

Tests: no secret/data reuse, stable generated identity after restart, template
migration, and fresh IDs during import.

### 5. Authenticated proxy management and diagnostics — medium–large effort

Required-proxy enforcement already exists. `normalizeProxyURL` deliberately
rejects embedded credentials; the UI has no credential store or saved proxy
catalog. Add named proxy entries with credentials stored in Firefox Login
Manager/OS-backed facilities, container bindings, explicit connection testing,
and visible last-checked status. Keep proxy secrets out of page-visible state,
logs and ordinary identity exports. Evaluate Firefox authentication callbacks
and connection reuse across containers before shipping.

Tests: two different authenticated proxies/credentials; HTTP and SOCKS behavior;
407/retry paths; DNS routing; no direct fallback; secret redaction and container
separation. No proxy purchasing or external service integration is part of this audit.

### 6. Persona-data refresh and validation — larger ongoing effort

We already sample a BrowserForge desktop-Firefox distribution
(`CloakfoxBayesianNetwork.sys.mjs`) and derive the UA version from the engine.
Improve dataset provenance/versioning, deterministic constraints, and real-device
lab coverage for GPU/font/screen combinations. Preserve Firefox's actual API and
network characteristics. Do not add Chromium identifiers solely because Octo
uses Chromium. Do not claim that a plausible generated tuple reproduces a real
GPU's rendering output without measuring it.

## Larger or lower-priority work

- Android personas require coordinated mobile APIs, viewport/input behavior,
  fonts and rendering. The new desktop-touch support is not mobile emulation.
  Treat this as a separate project after desktop consistency tests are strong.
- Full separate-profile workspaces offer boundaries that containers do not:
  browser-wide extension state, history and preferences need a different storage
  architecture. Our encrypted identity export contains settings, not a complete
  encrypted live profile. Profile vaults require a separate threat model and
  lifecycle design; prefer local storage for the daily-driver use case.
- Team sharing, cloud profile synchronization, bulk automation and cookie-farming
  workflows have low priority for this browser's stated personal-privacy goal.

Existing overlap includes native fingerprint hooks, many custom overrides,
BrowserForge sampling, persistent container identities, site-keyed noise,
temporary containers, enforced proxies, RTC policy, bundled blocking and encrypted
identity-settings backups. Feature counts alone do not establish privacy parity.


Implementation of the accepted five-item shortlist is documented in [the feature report](octo-features/README.md), with final test evidence and current limits.
