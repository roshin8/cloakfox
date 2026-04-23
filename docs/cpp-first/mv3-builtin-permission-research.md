# MV3 Builtin Addon: `host_permissions` Auto-Grant Research

Research into why `cloakfox-shield@cloakfox` (MV3 builtin) shows
`contentScripts[i].matches.patterns.length === 0` at runtime even though
`host_permissions: ["<all_urls>"]` is declared.

Sources examined (Firefox 146.0.1 source tree, extracted from
`/Users/zeus/Documents/cloakfox/firefox-146.0.1.source.tar.xz`):

- `toolkit/components/extensions/Extension.sys.mjs`
- `toolkit/components/extensions/ExtensionProcessScript.sys.mjs`
- `toolkit/components/extensions/WebExtensionPolicy.cpp`
- `toolkit/mozapps/extensions/internal/XPIProvider.sys.mjs`
- `toolkit/mozapps/extensions/gen_built_in_addons.py`
- `browser/extensions/webcompat/manifest.json` (only builtin; all Firefox 146
  builtins — webcompat, formautofill, newtab, pictureinpicture — are MV2).

## MV2 vs MV3 Builtin: The Gap

`Extension.sys.mjs`:

- Line 2005 sets `originControls = manifestVersion >= 3 && type === "extension"`.
- Line 2046: `if (!result.originControls) { originPermissions.add(perm); }` —
  for MV2, host permissions land in `originPermissions` immediately. For MV3
  they are **treated as optional** and skipped here.
- Line 1263: `origins: this.originControls ? [] : this.getManifestOrigins()` —
  MV3 returns no origins from `permissionsObject`.
- Line 2361: `this.allowedOrigins = new MatchPatternSet(manifestData.originPermissions, ...)`
  is therefore empty for MV3 at load time.

The only path that re-populates origins for MV3 is
`_setupStartupPermissions` (line 4340):

```js
if (this.originControls &&
    this.startupReason === "ADDON_INSTALL" &&
    (this.manifest.granted_host_permissions || lazy.installIncludesOrigins)) {
  let origins = this.getManifestOrigins();
  lazy.ExtensionPermissions.add(this.id, { permissions: [], origins });
  this.allowedOrigins = new MatchPatternSet(origins.concat(allowed), ...);
}
```

Conditions to auto-grant for MV3:
1. `startupReason === "ADDON_INSTALL"` — only the *first* bootstrap after app
   install. Subsequent `APP_STARTUP` reads the grant from `ExtensionPermissions`
   store via `loadManifest` → line 2118.
2. Either `manifest.granted_host_permissions === true`, OR pref
   `extensions.originControls.grantByDefault` is true (line 133–136).
3. For `granted_host_permissions` to survive parsing, line 2022 requires
   `isPrivileged === true` (else it is hard-reset to `false`).

A builtin addon registered via `browser/extensions/<dir>` (picked up by
`gen_built_in_addons.py` → `chrome://browser/content/built_in_addons.json`) is
flagged `builtIn: true` (XPIProvider.sys.mjs line 1051, 2043), which makes
`Extension.getIsPrivileged` return true (line 1000–1007) → `isPrivileged: true`.

### The content_scripts matches link

Content-script `matches` come from the same manifest parse (Extension.sys.mjs
line 2159). `<all_urls>` itself parses fine regardless of `restrictSchemes`
(MatchPattern.cpp line 253). BUT `WebExtensionContentScript` is constructed
with `mCheckPermissions = true` for MV3 (WebExtensionPolicy.cpp line 774–777).
`MatchesURI` then falls through to `mExtension->CanAccessURI(...)` which
consults `allowedOrigins`. If `allowedOrigins` is empty, matches are moot.

The user's observation that `allowedOrigins.patterns` includes `<all_urls>`
but `contentScripts[i].matches.patterns.length === 0` therefore almost
certainly means the value was inspected on a cached `WebExtensionContentScript`
that was built before `ADDON_INSTALL` re-populated the origins (or the
`matches` field truly is empty because at the time `initExtensionPolicy` was
called, `extension.contentScripts` had already gone through `options.matches`
which came from a parse run where origins were dropped). Either way, the root
cause is the MV3 gate and the absent auto-grant hint.

## The Fix (concrete)

Patch the manifest. Add one key to
`/Users/zeus/Documents/cloakfox/additions/browser/extensions/cloakfox-shield/manifest.json`:

```json
{
  "manifest_version": 3,
  ...
  "granted_host_permissions": true,
  ...
}
```

This is a documented Firefox-only manifest key (see
`toolkit/components/extensions/schemas/manifest.json` line 265). The keep-alive
gate at Extension.sys.mjs line 2022 preserves it because `isPrivileged` is
true for builtins. The gate at line 4340 then runs `ExtensionPermissions.add`
on first bootstrap, and the allowed origins persist to subsequent
`APP_STARTUP`s via the ExtensionPermissions store.

Defensive belt-and-suspenders (optional): append to
`/Users/zeus/Documents/cloakfox/settings/cloakfox.cfg`:

```
pref("extensions.originControls.grantByDefault", true);
```

This makes `lazy.installIncludesOrigins === true` as a global fallback.

No C++ patch required. No new .patch file required if you just edit the
cloakfox-shield manifest directly (it lives under `additions/`, not the
Firefox source). Rebuild is omni.ja-only.

Downgrading to MV2 is NOT viable: `content_scripts[].world: "MAIN"` is
MV3-only and cloakfox-shield's inject/index.js MUST run in MAIN world to call
`window.setCanvasSeed()` etc. (see CLAUDE.md "Critical Constraints"). MV2
would require a workaround via `<script>` element injection which is
document_start-unsafe and adds a detectable timing gap.

## Validation

After rebuild, open Browser Console (Ctrl+Shift+J) and run:

```js
const { AddonManager } = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
const p = WebExtensionPolicy.getByID("cloakfox-shield@cloakfox");
console.log("allowedOrigins:", p.allowedOrigins.patterns.map(x => x.pattern));
console.log("contentScripts:", p.contentScripts.length);
console.log("cs[0].matches.patterns:", p.contentScripts[0].matches.patterns.map(x => x.pattern));
```

Expected after fix: both `allowedOrigins.patterns` and
`contentScripts[0].matches.patterns` contain `<all_urls>`.

Also confirm on a live page (e.g. https://example.com): open DevTools,
check `window.__HYDRA__` is undefined (deleted after read — means inject
ran) and canvas fingerprint is spoofed.
