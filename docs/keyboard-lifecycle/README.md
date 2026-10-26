# Keyboard wrapper lifecycle repair

A same-origin iframe's EventTarget methods can be borrowed by the parent and retained after iframe removal. Previously the wrapper captured the removed frame's original methods and Window; non-key add/remove calls threw dead-wrapper errors, and keyboard listener callbacks failed before reaching page listeners.

The actor now resolves the live receiving realm's wrapper before touching captured source-frame objects. Registration and removal use the same recipient registry, normalizer, and per-container/site seed. No fingerprint protections, privacy defaults, identities, cookies, permissions, or saved user preferences are disabled or changed.

The local disposable-profile probe failed on the prior installed app and passes seven checks on the repaired installed app. It covers preexisting listener delivery, non-key methods, Window/element/standalone targets, invalid receivers, independent cadence normalization with inherited timestamp properties, cleanup, and retained-document navigation. All requests in this regression are loopback HTTP. Source equals the actor inside the installed browser archive, and the strict deep application signature and GPU integrity manifest were verified.

The original aa.com investigation found intermittent Akamai Access Denied responses. A protected session also loaded successfully before this repair, so the denial does not establish a deterministic single-setting cause. The server's public reference ID does not expose its decision rules. Keyboard API errors were independently reproduced locally; their causal role in the denial remains unproven. No compatibility exception or relaxed identity setting was added for aa.com.

Post-repair normal aa.com load: Akamai still returned Access Denied with Cloakfox enabled, and console capture contained zero CloakfoxKeyboardChild errors. Repairing the keyboard wrapper is therefore not sufficient to resolve the server rejection. The exact blocking setting remains unconfirmed.

The installed package includes Gecko's .purgecaches application marker to invalidate older startup caches on normal launch, without deleting user profile data.
