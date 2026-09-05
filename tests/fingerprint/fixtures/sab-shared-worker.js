"use strict";

/* SharedWorker support is optional, but its result is always explicit. */
self.onconnect = event => {
  const port = event.ports[0];
  port.postMessage({
    status: "ready",
    crossOriginIsolated: self.crossOriginIsolated,
    sabType: typeof SharedArrayBuffer,
    atomicsType: typeof Atomics,
  });
  port.onmessage = message => {
    try {
      const {buffer, iterations = 0} = message.data;
      if (typeof SharedArrayBuffer !== "function") {
        port.postMessage({status: "skipped", reason: "SharedArrayBuffer unavailable"});
        return;
      }
      const view = new Int32Array(buffer);
      for (let index = 0; index < iterations; index += 1) Atomics.add(view, 0, 1);
      port.postMessage({status: "ok", final: Atomics.load(view, 0)});
    } catch (error) {
      port.postMessage({status: "error", error: String(error)});
    }
  };
  port.start();
};
