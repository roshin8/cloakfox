# Native request Client Hints repair policy

The HTTP channel synthesizes the three default low entropy headers (`Sec-CH-UA`,
`Sec-CH-UA-Mobile`, `Sec-CH-UA-Platform`) from its actual final User-Agent.
This applies to the first request without extension warmup. Existing channel UA
selection uses its loadInfo origin attributes, including container zero; worker
requests and redirects retain their own channel identity. Native JS UAData and
request hints share product-token parsing, brand order, platform and mobile rules.

Eligibility requires an HTTPS or trustworthy loopback HTTP destination, a content
caller, a trustworthy initiator for subresources and the available document's
secure-context flag. Chrome/system callers, WebSocket channels, Firefox/Safari/
iOS identities, master-off mode and RFP do not synthesize hints. HTTP hostnames
resolved to loopback through a test DNS pref remain untrusted unless their actual
hostname/address satisfies Gecko's secure-context loopback rules.

Each explicit public header set or removal wins independently. Synthesized
headers are refreshed after asynchronous request observers and before transport,
so a caller UA override cannot leave stale default brands. Internal redirects
skip synthesized headers and evaluate their destination policy afresh; explicit
header changes remain caller-owned. Brands and platforms use fixed strings and
versions use complete numeric product tokens. Invalid CR/LF/NUL configuration UAs
fall back to a valid configured navigator UA or the native UA.

## Explicit Permissions-Policy denial and ownership

The baseline `ch-ua`, `ch-ua-mobile`, `ch-ua-platform` features are registered with
the native policy engine's `*` default. Modern empty-list declarations such as
`Permissions-Policy: ch-ua=(), ch-ua-mobile=(), ch-ua-platform=()` suppress their
respective synthesized request headers. Structured-field parsing retains denial
when a valid declaration carries parameters. Explicit empty-list denial works
even when Gecko's general header feature pref is off. The policy cannot suppress
the initial document request retroactively: that request precedes its response.

Native inherited policy combines ancestor denial and iframe `allow` restrictions.
A shared publisher records the resulting three denial bits after response-header
parsing and after the variant initializer used for initial empty documents.
Coverage includes HTTP documents, `srcdoc`, explicit `about:blank`, initial
source-less iframes, and blob documents. Initial empty documents initialized after
Embed also refresh an already-created Window ClientSource and its parent-process
IPC snapshot before their immediate fetches or worker creation.

The denial mask belongs to the owning PolicyContainer. Narrowing a child's mask
copies container metadata before writing it, preserving existing native CSP,
integrity, WAICT and connection-allowlist object sharing while leaving the parent
mask untouched. IPC serialization, container equality and cloning include the
mask. Persistent serialization is version 3; version 1/2 reads explicitly reset
it to zero. The request channel applies denial independently per default hint.
User-set request headers retain their established precedence.

Dedicated and nested workers inherit an immutable creation snapshot. Shared
workers inherit the first creator's client snapshot; later connections do not
replace the shared worker's existing policy with each caller's policy. Independent
service-worker activity retains its own client policy, rather than borrowing a
transient page's denial for unrelated activity. These ownership rules do not
constitute full per-request origin delegation.

## Deliberate limits

This repair does not implement HTTP high entropy hints, Accept-CH persistence,
Critical-CH retries or full Permissions-Policy origin allowlist delegation.
Servers requesting high entropy hints still receive only eligible default low
entropy hints; the native JS high entropy API can return additional persona-derived
values. This remaining HTTP/JS capability difference is explicit. A future
implementation needs origin-scoped opt-in, destination/delegation checks, bounded
persistence and coherent redirect/service-worker semantics. Native Gecko remains
distinguishable from Chromium when its identity metadata is coherent.

## Evidence and verification

`tests/fingerprint/runtimeprobe_client_hints_headers.py` uses a temporary profile
and fixture-owned loopback TLS endpoints. It checks actual server-received
headers, first-navigation JS/vendor parity, containers, redirects, subframes,
dedicated/service workers, localhost/untrusted HTTP, mobile identity, opt-outs,
user overrides and unsafe UA values. Policy cases cover complete and selective
denial, child-frame and nested-worker inheritance, all four non-HTTP/empty-frame
paths, parent isolation and a new allowed navigation after denial. The probe makes
no public request or camera/microphone grant.

The final development build passed **90/90 checks**. Raw evidence:

- [Final development results](../../tests/fingerprint/reports/158-fingerprint-repairs/final-development/runtimeprobe_client_hints_headers/client-hints.json)
- [Final development run log](../../tests/fingerprint/reports/158-fingerprint-repairs/final-development/runtimeprobe_client_hints_headers/run.log)

Installed pre-repair evidence is under
`tests/fingerprint/reports/158-fingerprint-repairs/hints-red` (18/37 failed) and
`hints-red-expanded` (23/47 failed). The expanded run proved that a configured UA
containing CRLF could create a separate request header, and NUL truncated the UA;
the repair validates the full byte length before selecting either configured UA.

A disposable installed Chrome 155 localhost comparison in
`tests/fingerprint/reports/158-fingerprint-repairs/hints-policy-chrome.json` shows
allowed window fetches carrying all three hints and explicitly denied window
fetches carrying none. Initial document requests still carry default hints before
the response policy is known. Chrome worker fetches carried no hints in either
case, so this comparison does not establish Chrome worker positive-hint parity.
The [UA Client Hints specification](https://wicg.github.io/ua-client-hints/) and
[Client Hints infrastructure](https://wicg.github.io/client-hints-infrastructure/)
define default low entropy delivery as policy controlled.

The installed replacement app has been signature-verified by the coordinator;
its broader local probes and public-site audit are separate from the completed
90-check development result and are still being collected at this document update.
