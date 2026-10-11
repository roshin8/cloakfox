# Daily defaults — task 2

Implemented in `settings/cloakfox.cfg` and `settings/chrome.css`. Copied both to
`firefox-src/lw/` for the controller's rebuild. `settings/policies.json` was
reviewed and left unchanged: its tracking protection policy does not set
`Locked`, and it does not disable Safe Browsing or HTTPS-Only.

## Behavior

Fresh profiles default to phishing/malware Safe Browsing and HTTPS-Only enabled.
Search-provider suggestions default off in both global search and the URL bar;
explicit opt-in survives restart. Search/history/bookmark suggestions, new-tab
preferences, password saving, form filling, reader mode, tab warnings, spellcheck,
extension scopes and container UI visibility now use default preferences so
ordinary user choices persist. RFP=false and containers=true remain startup
invariants. The config no longer sets reduced motion, allowing native OS
accessibility behavior and explicit user overrides.

No user preference cleanup/migration is performed: existing user values (including
old AutoConfig-written Safe Browsing=false or reduced motion=0) survive. Firefox
cannot distinguish those old writes from an intentional user preference. Users
can reset those values in about:config or change them in Settings. Native
HTTPS-Only per-site exceptions are retained; the defaults do not touch permission
storage. Network/WebRTC settings remain owned by task 4.

Removed stylesheet rules hiding tracking protection, bookmarks, extensions,
notification panels, synced tabs, container identity stripes and tab controls.
Removed tab pointer-event/drag overrides that obstruct native interaction, and
fixed an unmatched comment delimiter. Remaining compact visual styling is kept.
This CSS is packaged as a resource by `lw/moz.build`; no loader/reference was
found in browser base content or browser themes. These source edits therefore
must not be advertised as a verified visible UI change. The live probe reports
whether this stylesheet is loaded and verifies native bookmark/extension control
presence. It does not yet prove tracking-panel behavior on a normal web page.

## Safe Browsing availability blocker

The current Firefox source retains Google v4/v5 provider list names and update/
gethash URLs in `modules/libpref/init/all.js`. `SafeBrowsing.sys.mjs` still
registers feature lists and supports updates. However, the current built
`obj-aarch64-apple-darwin/dist/bin/modules/AppConstants.sys.mjs` contains the
`no-google-safebrowsing-api-key` sentinel. `checkGoogleSafeBrowsingKey()` rejects
that sentinel and `updateProviderURLs()` clears Google provider update and gethash
URLs. Enabling feature prefs is therefore necessary but **not sufficient** for
functional phishing/malware protection in this build. A legitimate provider/build
API key and successful real list-update verification are still required before
claiming production protection. No key-check bypass or invented provider was added.

## Verification

- `node --test tests/fingerprint/test_daily_defaults.mjs`: **4 passed**. Before
  config changes, 3 failed (protective defaults disabled; history choice clobbered;
  forced reduced motion). This executes the real config in a VM with separate
  user/default branches modeled on Firefox AutoConfig `prefcalls.js`, carries
  saved user values through two startups and checks mandatory startup invariants.
- `python3 -m py_compile tests/fingerprint/probe_daily_defaults.py`: passed.
- New isolated Selenium probe: `CLOAKFOX_BIN=<built-binary> python3
  tests/fingerprint/probe_daily_defaults.py`. **Not run by this worker** to avoid
  concurrent browser/build access. Controller must run sequentially after rebuild.
  It disables automation's recommended preference overrides (which themselves
  turn Safe Browsing off), checks fresh defaults, changes user preferences and a
  native HTTP site exception, restarts the same disposable profile, and checks
  persistence plus invariants. It reports key readiness without exposing the key.
  The probe does not fetch provider lists or navigate to malicious sites.

Actual startup/restart verification and live provider-update verification remain
outstanding until the controller runs the probe and supplies provider credentials.
