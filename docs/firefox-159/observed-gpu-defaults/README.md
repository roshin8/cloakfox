# Observed GPU compatibility default and explanation

Baseline: `a56fe09c03`. The selected-container control now explains what recorded
GPU capabilities mean, the privacy protections retained, the supported profiles,
reload requirements and source coverage. Its expandable source section lists all
three admitted Windows profiles and links the pinned online release.

The default is on **within compatible reference mode** when canonical rendering
and container GPU profiles are already enabled. No prerequisite is enabled
implicitly. An explicit saved off choice wins. Automatic defaults are recomputed
per owner and persona rather than written as saved overrides, including at
restart. Unsupported observed candidates retain the existing reference mode;
explicit invalid requests still reject. Other container identities are unchanged.

[Complete bundled catalog](catalog.md): 106 records and 118 context reports.
[Online source](https://github.com/scrapfly/fingerprint-generator/releases/tag/model-2/2026).
This snapshot is not an exhaustive database of GPU/driver/browser combinations.
Enabling the setting performs no external source lookup or hardware upload.

Validation: 395 JavaScript tests passed with no skips. The actual headless
Firefox159 settings probe passed all checks in `validation.json`, covering default
activation, explanation/source text, automatic restart, explicit off, per-owner
isolation, invalid Apple activation and dependency recovery. Independent code
review found no actionable issues. Native XUL/backend files are unchanged from
the previously accepted build; updated UI/module hashes are recorded in
`acceptance-app.json`. Prior app/checkpoints, installed apps and Chromium build
inputs/processes were left untouched.
