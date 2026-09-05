"use strict";

/* SharedArrayBuffer timing fixture. Every bounded mode reports its exact count. */
self.onmessage = event => {
  const {mode, buffer, iterations = 0} = event.data;
  const view = new Int32Array(buffer);

  if (mode === "correctness") {
    for (let index = 0; index < iterations; index += 1) Atomics.add(view, 0, 1);
    postMessage({status: "ok", final: Atomics.load(view, 0)});
    return;
  }

  if (mode === "wait") {
    postMessage({status: "ready"});
    const waitResult = Atomics.wait(view, 1, 0, 5000);
    postMessage({status: "ok", waitResult, stored: Atomics.load(view, 1)});
    return;
  }

  if (mode === "rate") {
    postMessage({status: "ready"});
    while (Atomics.load(view, 2) === 0) Atomics.add(view, 0, 1);
    postMessage({status: "ok", final: Atomics.load(view, 0)});
    return;
  }

  if (mode === "benchmark") {
    const start = performance.now();
    for (let index = 0; index < iterations; index += 1) Atomics.add(view, 0, 1);
    postMessage({
      status: "ok",
      final: Atomics.load(view, 0),
      milliseconds: performance.now() - start,
    });
    return;
  }

  postMessage({status: "error", error: `unknown mode: ${String(mode)}`});
};
