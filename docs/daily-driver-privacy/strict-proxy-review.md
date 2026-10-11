# Independent strict proxy guard review — 2026-09-07

Reviewed patches/cloakfox-strict-proxy-guard.patch against Firefox 155 nsProtocolProxyService.cpp and nsHttpChannel.cpp, and the privileged CloakfoxNetworkPolicy filter. No code edits, build or browser execution.

**No blocking finding in the reviewed guard.** Placement after Gecko's proxy bypass handling closes the observed localhost hole: required container mode rejects absent proxy info or a different container isolation key. Explicit blocked mode, unknown nonzero integer modes, and malformed typed prefs fail closed; absent prefs retain normal networking. Container ID comes from channel origin attributes rather than ambient selected-tab state. The system-principal background exemption matches the JS policy's intended scope.

Calling channel.Cancel before OnProxyAvailable is essential. nsHttpChannel::OnProxyAvailable (line 8764) explicitly treats a proxy-resolution error as nonfatal and normally proceeds DIRECT. This patch cancels the actual channel and passes the error/null proxy to the callback, preserving the canceled request rather than merely returning a failed lookup. Existing completion paths converge on this callback helper after filtering. Callback invocation remains single-shot.

The JS filter creates container-keyed proxy info with no failover proxy, zero failover timeout, remote SOCKS DNS and forced tunneling flags. The native guard checks that provenance marker after bypass processing. Required-proxy settings changes block first while publishing the new configuration.

Scope: this guard protects channel proxy selection, not raw WebRTC sockets, privileged system-background requests, existing connections, or an already selected proxy endpoint during a policy change. The marker identifies the container, not a policy epoch or exact host/port; it should not be described as revoking all in-flight connections on endpoint changes. RTC enforcement is under separate native review. These boundaries do not invalidate the localhost fail-closed fix.

Recommended runtime regression evidence from root: strict mode to localhost cannot fall back direct; rejected/unavailable proxy cannot fall back direct; valid required proxy succeeds; missing and mismatched isolation keys fail; normal mode succeeds; block and malformed modes fail; a background request remains in its documented scope. No compilation result is claimed by this read-only review.
