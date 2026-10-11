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


## Conformance continuation review (2026-10-11)

One fresh read-only reviewer examined the new canonical conformance patch and
fixtures, then reviewed the repairs. This is separate from the historical
review above; the full-matching requirement remains open.

- Important: serialized Chrome handshake signature schemes differed from
  receive-side acceptance. A trusted P-521 server proved the old Chrome-shaped
  client accepted an unadvertised signature, while installed Chrome155 rejected
  it and native Cloakfox accepted it. One shared per-socket list now constrains
  both serialization and client peer-handshake signature validation. Existing
  certificate-chain and algorithm policy remains authoritative. Real repaired
  acceptance passes. This was a negotiation discrepancy, not a bypass of
  configured cryptographic policy.
- Minor: H3 ALPS tests used zero/default QPACK values. The fixture now withholds
  ordinary server SETTINGS and observes a real non-default encoder-capacity
  instruction of64 before releasing them. Accepted0RTT correctly uses cached
  ordinary settings4096, which superseded the original ALPS value.
- Minor: existing ordinary H2 SETTINGS allowed INITIAL_WINDOW_SIZE greater than
  2^31-1; the new ALPS consumer inherited that behavior. A real ALPS overflow
  was accepted before repair and is now rejected by the shared handler before
  mutating stream windows.

Follow-up review found no further Critical or Important issue in these repairs.
That verdict does not certify full Chrome equivalence or the remaining protocol
work. Mounted-package acceptance is recorded separately in the current evidence.
