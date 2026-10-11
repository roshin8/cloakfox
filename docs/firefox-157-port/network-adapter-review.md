# Network adapter review and repair

One fresh, read-only gpt-6-astra whole-change review covered `845c12c0e4..62bc4fdc05`. It found no Critical or Minor issues and four Important issues. Its verdict was **not ready to merge**. No second reviewer was dispatched.

## Single repair pass

1. HTTPS/MASQUE wildcard conversion reread live owner prefs instead of preserving the captured profile. The actual production `CreateWildCard` body is compiled by `test_native_network_snapshot.py`; captured profile/generation, conservative state and TLS flags fail on the old function and pass after repair. This targeted test substitutes Gecko ownership facilities; it does not perform a delayed live HTTPS/MASQUE proxy race.
2. Switch-back reused prior connection generations. Registry atomic-state tests and real TCP pool tests reproduced that behavior. Identity/profile changes now advance a captured generation encoded by the Gecko adapter. Pool/coalescing/TCP/QUIC peer metadata is partitioned. Real QUIC tests require fresh switch-back handshakes and separate cache lookup keys. Generation exhaustion never wraps; it returns explicit unsupported/native status and leaves other owners reconcilable.
3. Edge/Opera/other branded Chromium UAs were treated as Chrome. Catalog-family regressions fail before the classifier change and pass afterward. Only measured desktop Chrome/Chromium major 155 is accepted.
4. Full network matching is incomplete. This remains an **Important open requirement**, with the checkbox explicitly experimental, default off, full TODO unchecked and no completed-matching/merge-ready claim. The user did not explicitly approve reduced scope. ALPS, trust-anchor behavior, signature/extension/GREASE semantics, QUIC packet behavior and complete protocol acceptance require further work.

Reviewer recommendations: certificate rejection is now checked with the Chrome adapter active. Real resumed/0-RTT exchanges and full coalescing/proxy races remain validation gaps. The final repaired package must pass runtime checks before its artifact metadata is updated.

## Rulings I made, in order

- Implement an explicitly experimental Gecko adapter as an intermediate step toward full matching. Cost: sites can still distinguish Gecko and full Chrome matching remains unmet.
- Keep engine-independent intent and adapter-owned metadata/commit callbacks. Cost if wrong: future Chromium integration requires contract migration.
- Keep WebTransport native until its required negotiated capabilities are implemented. Cost: those connections expose native Firefox transport signals.
- Retain intermediate branch work while marking full matching an Important open requirement. Cost: the authorized full-matching deliverable is unfinished; this work is not certified merge-ready for that scope.
- Actual Chromium integration stays future work; this change prepares its boundary. Cost if wrong: integration requires additional adapter work.
- Gecko page/rendering APIs remain unchanged for this network change. Cost: a Chrome UA still differs from Gecko page behavior.
- Verify only local protocol fixtures. Cost: public challenge-site compatibility remains unknown.

Deferred minors: none.
