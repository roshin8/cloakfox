# Castle browser lab

A loopback-only page for manually comparing Cloakfox and Firefox against your
own Castle environment. It generates a fresh browser SDK request token for each
measurement, calls the Filter API for a `$registration` / `$attempted` event,
and displays Castle's exposed signals, scores, policy and response data.
No real account is created by a measurement.

## Start

Requires Node 22 or newer. From this directory:

```sh
npm install --ignore-scripts
cp .env.example .env
chmod 600 .env
```

In the [Castle dashboard](https://dashboard.castle.io/settings/environment/api-keys),
select or create a **sandbox** environment. Put that environment's publishable
key and API secret into `.env`. Both keys must be from the same environment.
Do not paste the secret into the page or commit it.

```dotenv
CASTLE_PUBLISHABLE_KEY=your_publishable_key
CASTLE_API_SECRET=your_api_secret
CASTLE_CLIENT_IP=your_actual_public_egress_ip
PORT=8765
```

`CASTLE_CLIENT_IP` is optional, but important for network testing. It must be the
actual public IP used by the browser, including its VPN/proxy if applicable.
The server cannot infer that from a localhost connection. With no override it
uses `127.0.0.1`, which sandbox environments accept, and prominently marks the
result as loopback: IP reputation, location and timezone comparisons are then
incomplete. Production environments reject private IPs.

```sh
npm start
```

Open <http://127.0.0.1:8765> in the browsers you want to compare. The server binds
only to IPv4 loopback. Keys are read on startup; restart after changing `.env`.

## Compare

1. Open the page manually in Firefox. Keep the same network and OS settings for
   the comparison. Give the run a label such as `Firefox baseline`.
2. Interact with the page normally before clicking **Measure this browser**.
   Castle initializes on page load to collect behavioral context.
3. Open the exact same URL in Cloakfox, in the container you want to evaluate.
   Label the run with the browser, container and settings you used.
4. Measure once, then compare the exposed signals and scores in **Compare runs**.
   **Refresh results** loads measurements made in the other browser.
5. Use **View** for the saved response or **JSON** to export it. Change one
   setting at a time if investigating a compatibility difference.

The optional email is sent to Castle for email intelligence. Leave it empty
for the initial browser comparison. Normal comparison runs share one sandbox;
repeated activity contributes to its history and can affect activity signals.
Automation is not used to drive live comparisons because it can itself affect
Castle's bot assessment.

## Interpretation and limits

- API scores range from 0 to 1; the table displays them as 0 to 100.
- The policy action depends on your Castle rules. An `allow` without a deny
  policy does not establish that the browser has no suspicious signals.
- Castle's sandbox uses the production detection models, but history, policies
  and traffic differ from Grasshopper. This cannot reproduce Grasshopper's
  exact decision or identify the cause of its past block.
- The browser SDK is pinned to the public npm release **2.8.5**, current when
  this harness was created. Castle's dashboard may supply a newer or different
  SDK; use its installation instructions when available. Results record the
  installed version and should not be assumed identical to a site's SDK.
- Mock request tokens are rejected. An API/transport error is an error, never
  a successful verdict. No signal values are fabricated by the application.
- Castle's response exposes diagnostic signals, not all raw collection inputs
  or proprietary model internals. An absent signal is not proof of absence.
- This is a development harness. Do not expose it through a tunnel or deploy it
  publicly. Use an owned HTTPS test site if you need production-origin behavior.

Saved reports live in `reports/` (gitignored) and include timestamps, labels,
SDK version, evaluated IP, browser user agent and Castle's response. The
submitted request token/email, inbound cookies and API secret are not saved.
Reports can still contain device identifiers and other sensitive metadata.
Remove files from `reports/` to delete local history; this does not delete
events already sent to Castle. `.env` and report files should remain private.

## Verify

```sh
npm test
```

The backend tests isolate the external Castle API using a controlled response;
they validate request construction, credential handling, token validation,
cross-origin protection, report persistence and error behavior. They do not
claim a real Castle evaluation. UI smoke checks can run without keys; live
browser measurements require the Castle account and sandbox credentials.

References: [Browser SDK](https://docs.castle.io/docs/sdk-browser),
[integration guide](https://docs.castle.io/docs/integration-guide),
[sandbox behavior](https://docs.castle.io/docs/sandbox-environments),
[signal reference](https://docs.castle.io/docs/signals-reference).
