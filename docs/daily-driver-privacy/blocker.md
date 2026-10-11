# Maintained blocking integration

Status, 2026-09-07: staging and packaging integration implemented; packaged-browser
probe added for controller execution after build. No real user profile changed.

## Distribution choice and provenance

Bundle the unmodified Mozilla AMO XPI for **uBlock Origin by Raymond Hill**,
`uBlock0@raymondhill.net`, through Firefox's native `distribution/extensions`
mechanism. The reviewed pin is `settings/ublock-origin.json`: AMO add-on 607454,
author `gorhill`/11423598, version 1.74.0, minimum Firefox 115.0 (compatible with
155), GPL-3.0-only, 4,617,614 bytes, SHA-256
`175756d74468c9ba45863f7fc333d3be670f82d5b066314e915814dd547d1652`.

The [official AMO metadata](https://addons.mozilla.org/api/v5/addons/addon/ublock-origin/)
was read and the [pinned XPI](https://addons.mozilla.org/firefox/downloads/file/4981431/ublock_origin-1.74.0.xpi)
was downloaded and checked against that hash. Manifest ID/version, update routing
and JAR/COSE signature envelope files were inspected without executing extension
code. The public AMO API's `is_mozilla_signed_extension: false` field should not
be mistaken for proof the XPI lacks ordinary AMO signing: the actual XPI carries
`META-INF/mozilla.rsa`, `mozilla.sf`, `manifest.mf` and COSE signing files.
Cryptographic signature acceptance is checked by Firefox at runtime and asserted
in the live probe; mere presence of those files is not a signature verification.

The upstream project/source and license are recorded in the pin. The XPI is
shipped verbatim, including its license and bundled assets. Release maintainers
must meet redistribution/source-availability obligations and preserve the
corresponding upstream source version. The project is
[gorhill/uBlock](https://github.com/gorhill/uBlock), not similarly named blockers.

## Build and package behavior

`scripts/stage_ublock.py --output-dir firefox-src/lw/ublock-origin` downloads only
the reviewed immutable AMO URL, verifies exact size/hash and manifest identity,
and rejects a custom update URL. It stages `uBlock0@raymondhill.net.xpi`. Repeated
calls verify and reuse that same staged file with no network contact. A corrupt
or stale cached XPI fails clearly; it is never packaged or silently trusted. A
fresh checkout needs network access or the exact reviewed XPI prepositioned in
that directory. Pin refresh is a deliberate code review, not a mutable latest
URL evaluated on every build.

`patches/config.patch` installs this file with
`FINAL_TARGET_FILES.distribution.extensions` and adds it to the package manifest.
The corresponding existing Firefox source files were updated. Controller
integration in `scripts/copy-additions.sh`, after `mkdir -p lw`, is:

```sh
python3 "$REPO/scripts/stage_ublock.py" --output-dir lw/ublock-origin || exit 1
```

Do not hide download failure or make missing blocker files optional. The staged
XPI lives under ignored `firefox-src/`; no binary/vendor cache is committed.
The helper uses Python standard-library TLS/ZIP/hash facilities. HTTPS redirects
are required; bytes are still constrained by the committed hash. It never
extracts or executes the downloaded archive.

`settings/policies.json` adds only `default_area: navbar` for the blocker. It does
not force installation, lock the add-on, or set managed filter options. Its own
manifest also requests navbar placement. The Firefox source shows
`--disable-system-policies` skips Windows/macOS system policy providers and Linux
system-directory policy lookup, while always retaining the distribution JSON
provider. The chosen XPI distribution installation is independent of that policy
provider in any case.

## User control, updates and recovery

Firefox's `XPIProvider.installDistributionAddons` and
`XPIInstall.installDistributionAddon` copy the distribution XPI into profile
scope. `extensions.installedDistroAddon.<id>` records installation; if the user
later removes it, distribution installation skips it even on an app upgrade.
An already newer profile add-on is not downgraded to the bundled version.
`normal_installed`/`force_installed` enterprise policy would constrain removal,
so neither is used.

Firefox's existing defaults require extension signatures, enable extension
update checks and enable automatic add-on updates. Profile scope is outside the
build's unsigned app/system scopes used by Cloakfox Shield. The unmodified XPI
has no custom update URL, retaining AMO update routing. Users can disable/remove
it in about:addons or change automatic-update preferences. No policy or helper
reasserts those choices. Existing profiles that deliberately disabled distro
installation/signature/update settings remain user-controlled; the probe checks
new-profile defaults rather than overriding them to pass.

The uBO filter-list engine and upstream assets remain unchanged; no managed
bootstrap replacement or list-update restriction is introduced. The inherited
LibreWolf managed-storage hook only overrides assets when its preference is
nonempty; no value is configured here. uBO's normal filter-list updates contact
its configured upstream list hosts; ordinary add-on updates/metadata contact
Mozilla. This is expected maintenance traffic, separate from browser telemetry.

The uBO toolbar popup shows blocking for the current site and exposes a site
power toggle; its dashboard exposes enabled lists/update status and exceptions.
Use its site-specific exception when compatibility needs it, and remove the
exception to restore blocking. Firefox's native ETP shield remains present and
its protections are independent of uBO. A bundled add-on's existence does not
prove effective filtering or that every current list downloaded successfully.

## Tests and remaining release checks

`python3 -m unittest discover -s tests/blocker -v` passes six tests after initially
failing for the absent helper: exact identity/hash, altered archive, unexpected
ID, missing signature envelope, unexpected update endpoint and corrupt cache.
The synthetic test ZIPs deliberately contain placeholder signature files; they
exercise pin/structure validation, not Firefox's signature verification.

The real AMO XPI was successfully downloaded/staged and a second invocation
verified its cache. `git apply --numstat patches/config.patch` parses the patch.
The changed package/mozbuild sources reference the expected exact XPI filename.

After building/packaging, run sequentially using a disposable profile:

```sh
CLOAKFOX_BIN=/absolute/path/to/cloakfox \
  python3 tests/fingerprint/probe_bundled_blocker.py
```

The probe asserts the packaged distribution XPI exists, installed ID/signature
and active status, native update/signature defaults, disable/remove permissions,
ETP control presence, absence of managed asset override, disable persistence
across restart, and no reinstatement after removal and a simulated app-version
change. It does not manually install an XPI to conceal packaging omissions.
The controller must still run it: no browser/build tool was used by this worker.

Before release also verify real tracker blocking, fresh filter-list download,
site exception and restoration, update to a newer signed add-on, no downgrade of
an existing newer add-on, private-window behavior under Firefox's user-granted
permission model, and ordinary SSO/payment/media flows. Blocking/filter health
must remain visibly distinguishable from mere installed status. Test each
supported packaged platform; source/static tests alone do not establish them.
