"use strict";

self.addEventListener("install", event => event.waitUntil(self.skipWaiting()));
self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));

/* ServiceWorker support is optional, but its result is always explicit. */
self.addEventListener("message", event => {
  try {
    const {buffer, iterations = 0} = event.data;
    if (typeof SharedArrayBuffer !== "function") {
      event.source.postMessage({
        status: "skipped",
        reason: "SharedArrayBuffer unavailable in ServiceWorker",
      });
      return;
    }
    const view = new Int32Array(buffer);
    for (let index = 0; index < iterations; index += 1) Atomics.add(view, 0, 1);
    event.source.postMessage({status: "ok", final: Atomics.load(view, 0)});
  } catch (error) {
    event.source.postMessage({status: "error", error: String(error)});
  }
});
