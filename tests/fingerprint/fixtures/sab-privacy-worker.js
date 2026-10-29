"use strict";

// No wall clock participates in the observer's measurements or classification.
function workload(iterations) {
  let value = 0x12345678;
  for (let i = 0; i < iterations; ++i) {
    value = Math.imul(value ^ (value >>> 13), 1664525) + 1013904223 | 0;
  }
  return value;
}

async function observe(buffer, count) {
  const view = new Int32Array(buffer);
  const samples = [];
  let random = 0x125a372b;
  // Balanced, independently shuffled pairs in both training and held-out halves.
  for (let pair = -10; pair < count / 2; ++pair) {
    random ^= random << 13; random ^= random >>> 17; random ^= random << 5;
    const first = random & 1;
    for (const label of [first, first ^ 1]) {
      await new Promise(resolve => setTimeout(resolve, 1));
      const before = Atomics.load(view, 0);
      const checksum = workload(label ? 20000 : 2000);
      const after = Atomics.load(view, 0);
      if (pair >= 0) samples.push({label, delta: (after - before) >>> 0, checksum});
    }
  }
  return samples;
}

if (typeof document === "undefined") {
  self.onmessage = async ({data}) => {
    try {
      if (data.mode === "counter") {
        const view = new Int32Array(data.buffer);
        const tick = () => {
          // Yield between finite batches so serialized worker execution progresses.
          for (let i = 0; i < 65536; ++i) Atomics.add(view, 0, 1);
          setTimeout(tick, 0);
        };
        tick();
        self.postMessage({ready: true});
      } else {
        self.postMessage({samples: await observe(data.buffer, data.count)});
      }
    } catch (error) {
      self.postMessage({error: String(error)});
    }
  };
} else {
  window.runSABPrivacy = async count => {
    if (!crossOriginIsolated || typeof SharedArrayBuffer !== "function") {
      return {status: "inconclusive", reason: "isolated SharedArrayBuffer unavailable"};
    }
    const workers = [];
    const receive = worker => new Promise((resolve, reject) => {
      const timer = setTimeout(() => finish(new Error("worker timeout")), 20000);
      const finish = (error, value) => {
        clearTimeout(timer);
        worker.onmessage = worker.onerror = null;
        error ? reject(error) : resolve(value);
      };
      worker.onmessage = event => finish(event.data.error ? new Error(event.data.error) : null, event.data);
      worker.onerror = event => finish(new Error(event.message));
    });
    try {
      const buffer = new SharedArrayBuffer(4);
      const counter = new Worker("/fixtures/sab-privacy-worker.js");
      workers.push(counter);
      const ready = receive(counter);
      counter.postMessage({mode: "counter", buffer});
      await ready;
      const observer = new Worker("/fixtures/sab-privacy-worker.js");
      workers.push(observer);
      const observed = receive(observer);
      observer.postMessage({mode: "observe", buffer, count});
      const workerSamples = (await observed).samples;
      const mainSamples = await observe(buffer, count);
      return {status: "measured", worker: workerSamples, main: mainSamples,
        finalCounter: Atomics.load(new Int32Array(buffer), 0),
        iterations: {low: 2000, high: 20000}};
    } finally {
      for (const worker of workers) worker.terminate();
    }
  };
}
