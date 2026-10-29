# fpgen persona integration — Firefox 159

New containers prefer Scrapfly fpgen. In Settings → Identity generator, choose
**Persona source**, operating system and hardware, then **Generate and apply**.
BrowserForge remains selectable; its previews are explicitly BrowserForge.
Choosing controls stages a change until generation succeeds. Explicit provider
choices survive refresh and restart. Existing containers without a provider keep
their BrowserForge identity until deliberately regenerated.

Generation uses a pinned, bundled model and runs locally. The full 120-node model
archive is included with its Apache-2.0 license and provenance. An ancestor-closed
runtime projection samples supported identity fields from the observed conditional
distributions: browser/OS identity, screen/window traits, GPU labels and CPU count.
It is not a fixed list of pre-generated personas. The projection retains all source
values for its selected nodes; incomplete source combinations are documented and
excluded rather than invented.

The existing native mapper and privacy policies remain authoritative. Container
secrets, site-specific noise, font protection, letterboxing, permission checks,
WebRTC/proxy protection and executable GPU admission are unchanged. Model
permission grants, captured device identifiers, TLS settings and unimplemented
capabilities are never applied. Bundling the full model does not make every GPU
observation an executable backend profile. Browser/version claims still use the
existing engine-selection system; this change does not modify Chromium.

Provider and all generation filters are included in templates v2 and encrypted
backups v3. Legacy backups/templates retain BrowserForge semantics. Invalid
constraints/providers fail without replacing the previous identity. Explicit
BrowserForge generation retains the prior sampling path; golden full-output hashes
cover old legacy, host, preview and filtered cases.

## Evidence

- `runtime/validation.json`: actual headless Firefox **159.0-beta.1** with both
  providers, new/legacy owners, selected OS/hardware, failed generation rollback,
  document/worker/header consistency, protected geometry, storage isolation,
  per-container/per-site canvas separation and restart persistence.
- `regressions.json`: seven headless probes covering existing persona UI, host
  modes, templates, rendering controls, network identity, fonts and WebGL readback.
- `validation-summary.json`: unit/importer/inventory counts and Chromium input key.
- `acceptance-app.json`: staged resource hashes and six unchanged native/backend
  hashes. Uses a separate self-contained test app; no installed app or personal
  profile was modified. The current settings UI's concurrent Inspector dependency
  is included unchanged and identified separately in the staging record.
- `code-review.md`: independent review, corrected automatic Safari version issue,
  and acceptance-test review.
- `model-and-sampler.md`: model coverage, unsupported selections and reproduction.

The acceptance app is
`firefox-src/.tools159/acceptance-fpgen-personas/Cloakfox.app`. Source/resource-only
changes reuse the verified Firefox159 native binary. This work does not create a
new distributable DMG. Existing app/build/checkpoint directories are preserved.
