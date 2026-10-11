# IP conflict management

Implemented in the Firefox 155 compatibility worktree. Open Connections & proxies → IP conflict management.

## Controls

- Automatic checks remain opt-in. Manual “Check all containers now” ignores website filters.
- Choose a warning page (default when enabled) or a notification.
- Global website rules can be overridden per container. Choose all websites or listed hostnames; excluded hostnames always win. Hostnames include subdomains, with boundary matching. Reset a container to global rules.
- The warning page identifies the destination, current container and conflicting containers. Recheck after changing route, continue for 30 seconds, permanently allow a container, or allow a specific IP. Failed rechecks stay Unknown and do not automatically continue.
- Manage persistent IP exceptions and per-container allowances.
- Local IP ownership records include first/last observation, access count and ten recent URLs. Delete individual/all records or reassign ownership. Recent measurements may still identify a real simultaneous collision after reassignment.

## Routing, history and limits

Checks use content-principal channels with the actual container origin attributes, not background fetch. ipify is primary; httpbin is fallback. Both obey the container proxy/block policy. Requests are anonymous, uncached, disallow redirects, time out after 10 seconds each and accept at most 4 KiB. No direct-route bypass is introduced.

Current observations expire after five minutes and invalidate on route changes. IP ownership history is stored locally in profile preferences, capped at 500 entries and 30 days. Expired entries are purged on startup and history access. URLs omit credentials, query strings and fragments. Private-window navigation is excluded. History is not added to persona backups.

Warnings occur after navigation and cannot prevent or undo the first connection. They compare endpoint-observed public IPs, not every destination or both address families. Historical ownership is evidence of prior use, not proof that a second container currently uses that address. Exceptions suppress warnings; they do not change networking.

Warning contexts use per-tab, expiring opaque tokens. Continue/recheck validates that the tab is still on that warning. Reloading the app expires outstanding warning contexts. The original destination is retained in memory and navigation continues in the same container.

## Validation

- `test_ip_conflicts.mjs`: address validation, expiry, host/subdomain rules, exclusion priority, rule validation, history retention/redaction/ownership, exceptions and temporary allowances.
- `test_network_policy.mjs`: existing routing and fail-closed regressions.
- `probe_ip_conflicts.py`: local TLS CONNECT fixtures verify separate container routing, notifications, the rendered warning page, conflicting and unknown rechecks, temporary continuation, original container retention, route invalidation and fallback lookup. No external requests.
- `probe_ip_conflict_settings.py`: live rules persistence, exception add/remove, history display/deletion, redaction and responsive widths 1280/848/600.

New warning resources are registered in jar.mn and linked into the development app. JS/CSS/resources only; no native engine rebuild required. Restart the worktree app to reload the service.
