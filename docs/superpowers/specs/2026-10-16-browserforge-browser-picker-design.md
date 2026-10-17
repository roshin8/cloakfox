# BrowserForge Browser Picker Design

## Intent

Replace raw User-Agent editing as the primary identity workflow with a Chameleon-style browser profile picker. A user chooses browser family, a reasonably recent version, operating system, and hardware family; Cloakfox generates and applies the complete compatible persona rather than asking the user to know UA syntax.

## Approved Interaction

- Browser families are Firefox, Chrome, Edge, Chromium, and Custom. Safari is visible but unavailable because Cloakfox has no WebKit engine.
- Version choices include the running engine major, the previous three major releases, and “Random recent version.” The current and previous two versions are high-confidence; the third previous version is labelled lower-confidence.
- Operating-system choices are Windows, macOS, and Linux, limited to combinations supported by the selected engine and BrowserForge data.
- Hardware choices come from the matching BrowserForge distribution.
- A generated preview shows the UA plus platform, CPU, screen, GPU, locale, and network-profile summary before application.
- “Generate and apply” changes the entire identity atomically. “Browse matching profiles” shows deterministic BrowserForge previews constrained by the same browser/version/OS/hardware selection.
- Raw UA editing remains in Advanced field overrides.

## BrowserForge Relationship

BrowserForge is the identity generator. The picker supplies constraints; BrowserForge samples the correlated screen, GPU, hardware, and related fields. Version selection must condition the BrowserForge UA root before dependent fields are sampled. Cloakfox-derived fields such as canonical fonts, platform, `oscpu`, `appVersion`, and network profile must be generated from the selected browser/OS tuple.

The currently bundled Bayesian network is a filtered desktop-Firefox dataset. Firefox choices therefore work from that network. Chrome, Edge, and Chromium choices must remain disabled until a matching Chromium engine and a compatible BrowserForge distribution/capability report are available. The picker must never manufacture a Chrome UA on Gecko or enable a browser family solely because a preference says so.

## Privacy Rules

- The recommended choice is the exact running engine version.
- Previous releases are offered because the user requested moderately old privacy identities, but the UI must display reduced-confidence language for versions whose engine behavior cannot be made exact.
- A browser family is applicable only when its engine backend reports support.
- Switching browser family may request an engine change, but UA selection alone never changes the engine silently.
- Applying a profile updates UA, HTTP UA, `appVersion`, platform, `oscpu`, vendor, UA Client Hints where native to that engine, BrowserForge-dependent fields, and network-profile selection as one operation.
- Existing cookies and site data remain. Existing pages and workers reload or recreate after application.
- Unsupported combinations stay visible with a short reason instead of disappearing.

## Visual Direction

Use the approved graphite-and-teal mockup: browser-family tiles first, then linked version/OS/hardware controls, then one compact generated-profile preview. Keep the established sidebar and light/dark system themes. The raw field table remains collapsed under Advanced overrides and does not compete with the main workflow.

## Failure States

- No matching BrowserForge sample: disable apply and explain which constraint has no match.
- Required engine unavailable: show “Engine unavailable” and a disabled apply action.
- Stale or malformed saved selection: fall back to Firefox/current/automatic constraints without applying anything.
- Generation or persistence failure: restore every prior preference and keep the current live identity.
- Engine switch failure: retain the existing engine and identity.

## Scope Boundary

This feature does not ship old engine binaries, add WebKit, or claim exact emulation of older browser behavior. It provides recent-version privacy profiles, honest confidence labels, and an extensible capability boundary for the Chromium backend.
