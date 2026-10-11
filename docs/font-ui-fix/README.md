# Identity controls follow-up

Mixed-OS BrowserForge generation is again the default for new identities and
built-in templates. Existing saved host-mode identities are preserved; select
Windows, macOS and Linux and apply Change appearance to switch them explicitly.
The earlier privacy-completion report describes the superseded host default.

The main page now offers BrowserForge's 30 stable previews and fresh generation.
Selecting an entry alone does not change identity. Applying a preview pins its
coordinated tuple; explicit field overrides continue to take precedence.
There is no new hand-authored fingerprint catalog.

21 common/boolean fields have visible dropdown controls; arbitrary custom values
remain available for numeric/string choices. Other raw fields sit in Advanced
field overrides. Region has language/timezone presets and searchable timezone
suggestions, with manual editing retained. Region presets require Save region.

Settings text uses the system UI font, and decorative icons use SVG instead of
unavailable symbol glyphs. The original intermittent Menlo corruption was not
reproduced; this fixes the affected UI's font dependency, not a demonstrated
native font-engine defect.

Verification: 28 focused Node tests passed; probe_host_personas.py passed with
mixed-OS list, pinned selection, CPU override/reset and restart assertions;
probe_daily_settings_ui.py passed. A disposable headed session confirmed 31
identity choices, 21 field dropdowns and the region preset control. Screenshot:
identity-controls.png. Updated additions are mirrored into the local built app.
No native C++ changes or new full engine build were needed for this follow-up.

## Full form-layout follow-up

Fixed the nested `display: contents` grid that collapsed Advanced rows into a
single column. Each row now owns its label/control/action columns, and stacks
at narrow widths. Dynamic panels share input, select, textarea, button, label,
focus, disabled and status styles. Empty status paragraphs are hidden; privacy
exceptions have an explicit empty state. Current Graphics/Region values remain
visible. Raw editable values are keyboard-accessible buttons. Fixed duplicate
Default container entry and hidden-button CSS precedence.

BrowserForge previews are grouped by Windows/macOS/Linux in the main and template
pickers. The main picker has an OS filter; filtering selects a preview without
applying it. Fresh-generation labels explicitly state the applicable OS mode.
The displayed density is rounded for readability without altering configuration.

Verification: 183 Node tests passed (layout-unit-tests.log). Host-persona probe
checks OS groups/filtering, unchanged current identity, full-width Advanced rows,
hidden empty statuses, pinning, overrides and restart persistence. Daily settings
probe also passed. Headed desktop and narrow-window screenshots were inspected
for Display, Region, Proxies and Privacy. Capture via Selenium chrome context:
content-context screenshots in this spoofed browser capture incorrect scroll
regions. Final `polish-*.png` files use chrome-context capture.

The already-running development app can cache old chrome resources: use
Command-Shift-R on about:cloakfox to load the latest UI files.

## Container-first sidebar

Reorganized the existing settings controls into 11 sidebar categories. The
selected container and current identity stay visible while desktop navigation
switches panels. Container customization, organization, and browser-wide settings
are grouped separately. Narrow windows use a wrapping navigation area.

Search reveals matching settings sections with a no-results state. Category
changes preserve DOM form drafts and never apply persona or privacy changes.
Existing section anchors and container query links continue working. Persona
selection still uses the OS-grouped BrowserForge picker and explicit application.
Async container-workflow mounting is included in category visibility.

Verification: all 183 Node tests passed (sidebar-unit-tests.log), plus live
probe_settings_navigation.py, probe_host_personas.py and
probe_daily_settings_ui.py. The new navigation probe is included in the browser
suite runner and covers category visibility, unsaved region draft retention,
container context, search, empty state, deep-link navigation and expanded row
layout. Existing smoke probes now navigate categories before reading visible
text. Headed desktop and narrow-window screenshots are sidebar-*.png.

## Switchable compact layouts (2026-09-08)

Added the selected Extension console and Grouped controls designs to the real
settings shell. Console presents category sections as keyboard-accessible tabs;
Grouped controls presents the same DOM panels as collapsible groups. Switching
retains drafts and container context. Search reveals matching sections and deep
links select/open their target. Layout and explicit Slate blue light / Graphite
& teal dark choices persist in `cloakfox.ui.layout` and `cloakfox.ui.theme`.
No identity or protection preferences are changed by these controls.

Mirrored settings.js and settings.css individually to the Firefox source content
folder used by the existing development app. No native rebuild required.

Validation: node syntax check; live probe_settings_navigation.py passed layout and
theme persistence, drafts, tabs, deep links, search and overflow checks at 1280,
848 and 600 pixels. probe_host_personas.py passed including fresh generation,
override retention and explicit host mode. Native screenshots:
layout-console-light.png and layout-grouped-dark.png.

The standalone docs/design-options preview also has the two selected layouts in
a toolbar selector; its identities remain sample data.

### Compact profile editor implementation

Replaced the old tall hero form with aligned OS/profile selectors, a generation
mode row and one action toolbar. The current identity stays above both layouts.
Generation explanations and reset/forget controls are expandable; all existing
IDs and action handlers remain connected to the real BrowserForge backend.
Search opens matching nested disclosures, deep links open their target, and the
sidebar offset follows the actual toolbar height when controls wrap. Removed
orphan tab label references for inactive and single-panel categories.

The navigation probe passes both layouts, saved themes, draft retention and
600/848/1280px width checks. The daily settings UI probe passes real network,
region, permission and container controls in grouped mode. Updated native
screenshots show the final compact editor in both colors/layouts.

### Shield popup font correction

The popup had retained its independent monospace stack on container/URL values,
seed tag and persona summary. Switched those selectors to the existing sans UI
stack and replaced the unsupported brand character with an inline SVG shield.
Mirrored only popup.css and popup.html into the built-in extension source used
by the development app. Native extension-page screenshots: popup-before.png and
popup-after.png. A disposable-profile browser probe confirmed the computed font
stack changed on all four affected fields; visually checked the after screenshot.
The before probe reproduced the missing brand glyph, but did not reproduce every
spacing artifact from the user's active profile. No fingerprint settings changed.

### One OS selector for previews and fresh generation

Operating system now controls both the BrowserForge preview list and fresh
sampling. Removed the separate generation-mode control. The profile dropdown's
first entry generates a fresh identity for the chosen OS; the dedicated generate
button names that OS too. Selecting a choice alone does not mutate the identity.
Explicit windows/macos/linux modes use the existing bounded conditional sampler,
retaining complete Bayesian tuples, and persist per container. Legacy mixed and
host modes remain supported for existing identities. Templates and v2 backup
validation accept the new modes, and the template editor can display them.

Validation: 40 focused unit tests passed. The live persona probe generated three
fresh identities per OS, verified platform/mode and distinct seeds, checked no
mutation on selection, and reopened the selected container to verify stability.
The navigation/layout probe also passed. Source files mirrored individually to
the development app; restart required for cached parent-process modules.

### Separate generation from preview application

Generate calls the fresh-sampling path directly. Apply selected profile is
available only after selecting a numbered preview; its placeholder no longer
implies that Apply will generate an arbitrary identity. Applying a preview uses
a fresh seed as documented, while retaining the selected profile's fields.
Live persona probe passes and now explicitly checks the OS remains selected
immediately after every generation and Apply stays disabled after generation.
Cross-container similarity comparison is not implemented by the consistency
inspector; that inspector compares configured and measured fields for one scope.

### Website appearance honors Firefox

Removed the generated document:prefersColorScheme light pin and the actor's
prefers-color-scheme override. Corrected the startup content-override default to
2 (Auto); Firefox's actual mapping is 0 Dark, 1 Light, 2 Auto. User appearance
choices remain authoritative. The settings panel's own color toggle is separate.
Media-query logic unit suite: 15 passed. Live probe_website_appearance.py checks
CSS and matchMedia agreement for Dark, Light and Auto on a local HTTP website.
Restart the development browser to reload the generator/actor/default config.

### Existing-profile startup cache regression

Reproduced in the user's running worktree app using its native UI: the current
Generate Windows button invoked an old cached module, returned macOS, and reset
the OS picker to All. A normal Firefox restart did not invalidate the persisted
startup cache. Disposable-profile probes passed because they never contained
those compiled modules.

Recovery: touched the development app's .purgecaches markers (Resources and
Resources/browser, plus dist/bin), then used about:profiles → Restart normally.
Firefox's nsAppRunner checks this marker to invalidate startup caches.
Verified in the same existing profile via actual native control clicks:
Generate kept Windows selected and changed the identity; applying the first
Windows preview produced 1366×768 and 8 cores as selected. The active Default
container was regenerated during this verification, with its final identity the
selected Windows preview. No cookies or site data were cleared.

For subsequent loose-module staging, refresh the .purgecaches markers before
restarting the development app. A hard page reload or normal restart alone is
insufficient when the build ID is unchanged. Prior notes saying simply restart
were incomplete.

### Identity action feedback

Generate and Apply now paint a busy label/spinner before synchronous sampling
(two animation frames), suppress duplicate actions and disable container/profile
controls during the operation. Success displays the new seed tag and a website
reload reminder; errors use the same live status region. The confirmation pulse
now targets the current identity strip. Reduced motion preserves textual feedback
without animation. Live persona probe updated to await busy completion and verify
success messages; all OS generation/application assertions passed. Refreshed the
user's open settings page without regenerating their identity.

### Surface depth refinement

Added theme-specific elevation shadows, stronger page/panel contrast, inset
inputs, raised selected tabs, a distinct container context surface and restrained
button highlights/pressed states. Kept compact geometry and both layouts. Native
light/dark screenshots inspected; navigation, drafts, layout/theme persistence
and 600/848/1280px checks passed. CSS-only change mirrored to the development app.
