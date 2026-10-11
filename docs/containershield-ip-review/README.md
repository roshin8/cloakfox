# ContainerShield IP conflict review

Reviewed the supplied `/Users/zeus/Documents/containershield/dist/background/index.js.map`.
The accompanying ip-isolation.ts is its embedded original source.

- Checks top-frame committed navigations when enabled; skips about/extension pages.
- Queries ipify, falling back to httpbin; caches a result per container for five minutes.
- Stores public-IP ownership and warns if a different container uses that IP.
- Redirects to an extension warning page. Allows a 30-second bypass, persistent
  container exceptions, IP exceptions, and a fresh-IP recheck.
- Lookup uses plain background fetch: the container ID labels the cache but does
  not establish that the request travels through that container's route.
- Navigation is already committed before checking, so this is a warning after a
  connection, not a pre-connection isolation barrier.
- Failed lookup skips the warning; recheck returns conflict:false on lookup failure.

A Cloakfox implementation should measure through each actual container route,
report failed measurements as unknown, and distinguish shared-IP warnings from
claims that an initial connection was prevented. No IP conflict feature was
implemented as part of this review.
