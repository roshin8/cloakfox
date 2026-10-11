# CloakBrowser comparison and Cloakfox daily-driver privacy audit

Reviewed 2026-09-07 against the Firefox 155 compatibility worktree. This is a
source/configuration and public-documentation audit, not a new live privacy
benchmark or a verification of CloakBrowser's advertised detection scores.
No browser behavior was changed during this audit.

## Recommendation

Prioritize trustworthy updates, site isolation, honest identity controls, and
network enforcement. Cloakfox already has substantial fingerprint coverage;
adding more spoofed values is less valuable than fixing contradictions and
closing tracking paths outside the fingerprint APIs.

CloakBrowser is useful as an automation/profile-management reference. Its
reported CAPTCHA success does not establish resistance to cross-site tracking.
Neither a persistent profile nor a different fingerprint makes logged-in
activity anonymous.

## CloakBrowser feature inventory

The project advertises v0.5.10 and 73 engine patches. Platform/version statements
within its documentation differ, so verify actual release artifacts before
relying on a particular platform's version. Its public repository exposes the
wrapper, not a complete patch set comparable to our patches directory.

| Feature group | Publicly documented capability | Cloakfox comparison |
| --- | --- | --- |
| Fingerprint surfaces | Canvas, WebGL/WebGPU, audio, fonts, geometry, hardware, speech and storage quota | Broad overlap in native patches and actors; improve coherence and coverage rather than count patches |
| Identity control | Seeded or fresh identities; platform, GPU, brand, locale and timezone overrides | Container personas and overrides exist; site-specific seeds and coherent reset are incomplete |
| Proxy support | Authenticated HTTP/SOCKS5, QUIC tunneling and exit-IP alignment | Firefox proxy facilities exist, but an integrated container routing policy was not found |
| Automation | Python/JS/.NET, Playwright/Puppeteer/CDP, CLI, Docker and humanized input | Selenium works; automation parity has low daily-driver value |
| Persistent browsing | Persistent profiles, saved session state and extensions | Firefox persistence and extensions are inherited, not missing features |
| Compatibility | Optional Widevine setup and third-party-cookie controls | Test actual DRM/login behavior; expose narrow exceptions rather than global weakening |
| Distribution | Verified binary downloads, version pinning and release channels | Automatic updater disabled; release workflow uses ad-hoc macOS signing |

Sources: [engine/wrapper documentation](https://github.com/CloakHQ/CloakBrowser),
[current changelog](https://github.com/CloakHQ/CloakBrowser/blob/main/CHANGELOG.md).
These are vendor claims and descriptions; this audit did not run their binary.

The separate Manager supplies local persistent profiles, search/tags/edit/delete,
auto-launch, per-profile proxy/locale/hardware settings, native desktop windows,
Linux remote viewing and clipboard integration, optional UI/API authentication,
and status indicators. Our container popup and about:cloakfox cover persona
selection and overrides but not this complete workflow. Separate full profiles
also isolate more browser-level state than merely assigning a container ID;
we should offer both when stronger separation is wanted. [Manager documentation](https://github.com/CloakHQ/CloakBrowser-Manager).

## Confirmed findings in Cloakfox

1. **The Firefox 155 port still generates Firefox 146 personas.**
   `additions/browser/components/cloakfox/CloakfoxPersonas.sys.mjs:27` hard-codes
   `FIREFOX_VERSION = "146.0"`; lines 322–323 apply it to the UA. The copied build
   source contains the same constant. This is a port oversight that prior
   selected probes did not catch. Derive the advertised version from build
   metadata and migrate existing generated configurations without destroying
   seeds or intentional overrides. Verify fresh and existing profiles, HTTP UA,
   windows and workers. This should be addressed before release.

2. **No automatic security-update path.**
   `assets/base.mozconfig:9` disables the updater. The release workflow's macOS
   signing is ad-hoc (`.github/workflows/build.yml:105`). A daily driver needs
   authenticated update metadata and packages, prompt upstream security rebases,
   visible version/age, and a controlled recovery path. Test rejection of
   tampered updates and unwanted downgrades. A checksum alone is not an
   authenticated publisher identity. Build success is not update maintenance.

3. **Phishing and malware site protection are explicitly disabled.**
   `settings/cloakfox.cfg:80` and `:81` set the two protections false. The adjacent
   comment incorrectly dismisses the security cost for advanced users. Restore
   a supported protective default and document its network behavior. Review
   URL-list and download-check behavior separately rather than broadly removing
   both protections. [Mozilla's description](https://support.mozilla.org/en-US/kb/how-does-phishing-and-malware-protection-work).

4. **Fingerprint identity is container-scoped, not site-scoped.**
   The Math actor reads `cloakfox.container.<ucid>.math_seed` directly
   (`actors/CloakfoxMathChild.sys.mjs:93`). Native canvas/audio/font configuration
   is likewise keyed by container. A tracker operating on two sites can
   potentially correlate the same deterministic output. Design a site-keyed
   noise secret from container secret + top-level schemeful site, with correct
   Public Suffix handling. Carry that context through windows, iframes, workers
   and native reads. Keep the broad persona coherent; do not randomly change
   browser/OS for every request. This requires architectural work and tests,
   not just inserting a hash in one actor. Existing cookie partitioning does
   not prove fingerprint partitioning.

5. **Regenerate/reset does not mean forget identity.**
   `experiment-apis/cloakfox.js:155` changes seed/configuration preferences.
   `content/settings.js:560` clears persona preferences and overrides. Neither
   path shown clears cookies, IndexedDB, service workers or permissions. Keep
   a clearly named appearance-change action, and add a separate explicit
   “Forget this site/container” workflow. Define what is deleted, terminate
   affected contexts, clear the correct partitions, rotate secrets and reopen
   cleanly. Warn that retained logins/accounts still link activity. Test that
   reset cannot leave active tabs writing old identity data back into storage.

6. **WebRTC reporting is not enforced network isolation.**
   `CloakfoxWebRTCSync.sys.mjs:79` contains external IP-echo services; `startSync`
   starts detection asynchronously and explicitly allows the first page to
   race ahead. Results are shared globally, not keyed by container proxy.
   Rewriting ICE/SDP values does not by itself stop direct STUN or UDP traffic.
   The comments claiming there can be no divergent leak overstate the code's
   guarantee. Add explicit normal-calling, proxy-only/relay, and disabled modes,
   with a visible tradeoff for calling sites. In strict proxy mode, block direct
   fallbacks across DNS, IPv6, QUIC, WebRTC, speculative loads and background
   requests; verify with packet capture during startup, proxy failure and
   network changes. Merely obtaining a proxy-shaped displayed IP is insufficient.

7. **Unnecessary third-party startup contact.**
   The same WebRTC sync contacts ipify/icanhazip/ident.me as configured while the
   master switch is enabled. This is a separate third-party disclosure, even
   though those services necessarily receive the request IP. Offer an explicit
   network-identity check through the intended route, cache by route, and avoid
   treating successful lookup as a VPN kill switch. Local GeoIP lookup after
   obtaining an exit IP can avoid another remote geolocation lookup.

8. **Tracking blocking and per-site recovery need product integration.**
   The inspected distribution config does not install uBlock Origin; the
   inherited uBO bootstrap hook only acts if that extension exists. Add a
   maintained blocker with visible status and narrow site exceptions, keeping
   list updates functional. [uBlock Origin](https://github.com/gorhill/uBlock)
   supports Firefox and blocks ads, trackers and other unwanted content.
   The legacy `settings/chrome.css` also contains rules hiding the tracking
   shield and other browser controls. Verify whether those rules are active
   in the packaged browser and remove conflicting UI hiding before shipping.

9. **Daily preferences should survive restart.**
   Many ordinary settings use AutoConfig `pref()`, which can reassert values on
   startup. Audit which are mandatory invariants and which should be
   `defaultPref()` so the user's theme/accessibility/search/privacy choices
   persist. Search suggestions are explicitly enabled: expose that outgoing
   query behavior in onboarding. Keep permission decisions genuine; a fabricated
   US-city geolocation is not a useful default for maps, weather or delivery.

## Already present and worth preserving

- Firefox's normal history, bookmarks, passwords, reader mode, spellcheck,
  downloads and extension facilities; several are explicitly enabled in cfg.
- Containers, deterministic personas, native fingerprint hooks, actor coverage,
  a tab-aware popup and about:cloakfox settings.
- Reconciled content letterboxing, including legacy orientation and iframe CSS
  changes on resize/toggle.
- Native GPC preferences, disabled telemetry and prefetch, timer protection.
- Third-party cookie partitioning: `network.cookie.cookieBehavior = 5` is
  **BEHAVIOR_PARTITION_FOREIGN in Firefox 155**, verified in the actual source
  `netwerk/cookie/nsICookieService.idl:81`. Do not “fix” it to an obsolete value
  from older Firefox documentation. [Mozilla's Total Cookie Protection overview](https://support.mozilla.org/en-US/kb/introducing-total-cookie-protection-standard-mode).

Treat inherited features as present but not comprehensively tested. The port's
selected fingerprint checks did not establish password-manager, passkey, Sync,
DRM, WebRTC-call, screen-share, printing or profile-migration reliability.

## Proposed delivery order

| Priority | Work | Completion evidence |
| --- | --- | --- |
| Immediate | Build-derived UA, Safe Browsing default review, accurate reset/network wording | Fresh/existing profile tests; no stale 146 identity; settings survive restart |
| Before daily release | Signed updates and a security-rebase process | Tamper rejection, update/recovery tests, all supported platforms |
| High privacy value | Maintained blocker, HTTPS-Only and clear exceptions | Blocker/list status; payments/SSO work with scoped exceptions |
| High privacy value | Site-keyed fingerprint noise and real identity reset | Same site stable, different sites unlinkable by protected outputs, window/worker/iframe agreement |
| High privacy value | Per-container proxy policy and enforced no-direct fallback | Packet captures across DNS/STUN/IPv6/QUIC and failure transitions |
| Daily usability | Site-to-container rules, temporary containers, profile search and backup | Restore without mixing secrets; links open in intended container; clear backup disclosure |
| Daily usability | Permission and compatibility panel | Calls, screen share, passkeys, downloads, printing, accessibility and DRM tests |
| Later | Automation adapters and humanized inputs | Separate opt-in automation mode; no added remote-debugging surface by default |

HTTPS-Only can use Firefox's existing mechanism with site exceptions rather than
inventing a replacement. [Mozilla HTTPS-Only documentation](https://support.mozilla.org/en-US/kb/https-only-prefs).
DoH should be an explicit resolver/fallback policy coordinated with VPN/proxy
routing, including captive-portal and enterprise-network behavior; it does not
hide the destination IP from every network observer. [Mozilla DoH documentation](https://support.mozilla.org/en-US/kb/firefox-dns-over-https).

Avoid copying automation-specific concealment into the normal browsing default:
mouse-humanization, fake plugin/brand features, arbitrary Math constant changes,
and globally allowing third-party cookies do not establish privacy. Prefer a
coherent Firefox identity, small site-scoped noise where needed, blocked
trackers, and strong storage/network boundaries. Cookie exceptions should be
narrow and removable. Evaluate fingerprint linkability and website breakage,
not just whether a detector labels the session “human.”
