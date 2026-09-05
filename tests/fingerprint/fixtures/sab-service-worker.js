"use strict";

self.addEventListener("install", event => event.waitUntil(self.skipWaiting()));
self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));

/* ServiceWorker support is optional, but its result is always explicit. */
self.addEventListener("message", event => {
  const reply = event.ports[0] || event.source;
  try {
    if (!reply) throw new Error("ServiceWorker message has no reply port or client");
    const {mode, buffer, iterations = 0} = event.data;
    const capability = {
      crossOriginIsolated: self.crossOriginIsolated,
      sabType: typeof SharedArrayBuffer,
      atomicsType: typeof Atomics,
    };
    if (mode === "capability") {
      reply.postMessage({status: "capability", capability});
      return;
    }
    if (typeof SharedArrayBuffer !== "function") {
      reply.postMessage({
        status: "skipped",
        reason: "SharedArrayBuffer unavailable in ServiceWorker",
        capability,
      });
      return;
    }
    const view = new Int32Array(buffer);
    for (let index = 0; index < iterations; index += 1) Atomics.add(view, 0, 1);
    reply.postMessage({status: "ok", final: Atomics.load(view, 0)});
  } catch (error) {
    if (reply) reply.postMessage({status: "error", error: String(error)});
  }
});
