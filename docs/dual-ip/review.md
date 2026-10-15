# Dual-family IP review

Independent reviewer: review_dual_ip. Reviewed the IP module, warning/settings UI, dual-family/warning/settings unit tests, live TLS fixture, and relevant native routing integration.

Found P2: aggregate settings conflicts were incorrectly attributed to the primary IPv4 address when only IPv6 overlapped. Fixed by returning exact per-family matches from fresh route-valid backend records, consuming them in Settings, and limiting old-schema fallback. Production-shaped tests demonstrated RED before the fix and GREEN afterward. Re-review found no further P1/P2;29focused tests independently passed.

Additional implementing-agent review fixed partial-unknown warning wording, rejection of an IP exception with no known matching address, and stale legacy alias revival when rich family fields explicitly say unknown.

Reviewed privacy behavior: exact container content principal and native proxy routing; anonymous/cache-bypassed/no-redirect channels; family validation; both-family route/cache invalidation; same-host historical comparison; missing conflicting-family recheck remains unknown; private-window and opt-in gates preserved. Independent reviewer did not launch a browser or edit files; installed verification is separate. No claim is made that a lookup service proves an arbitrary destination's egress address.
