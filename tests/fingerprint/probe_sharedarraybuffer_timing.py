"""Cross-origin-isolated SharedArrayBuffer timing fingerprint probe.

The fixture Wasm was encoded once from the fixed Task 1 WAT using Firefox's
vendored ``wast::Wat::encode`` (wat2wasm is not available in this checkout).
Fixture SHA-256 (``shasum -a 256``):
    a708ba83e838f694edd1a942c52180a1c79bed837b13d7a72200d3c2460c8bd6

Exit codes: 0 pass · 1 assertion failure · 2 unable to run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import tempfile
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait


FIXTURES = Path(__file__).with_name("fixtures")
PAGE_PATH = "/fixtures/probe.html"
WASM_SHA256 = "a708ba83e838f694edd1a942c52180a1c79bed837b13d7a72200d3c2460c8bd6"
CORRECTNESS_ITERATIONS = 4_096
RATE_WARMUPS = 4
RATE_SAMPLES = 24
RATE_WINDOW_MS = 250
BENCHMARK_ITERATIONS = 5_000_000
PERFORMANCE_PAIRS = 20

# Acceptance bounds for the proposed masking policy, not universal statistical
# claims: the policy must change spread and center beyond ordinary disabled
# variation before it can be considered to cover this timing signal.
DISTRIBUTION_MAD_MULTIPLIER = 1.25
DISTRIBUTION_MEDIAN_MAD_MULTIPLIER = 1.0
PERFORMANCE_MAX_SLOWDOWN = 0.05

# Pin a valid default-container config before browser startup. Worker timing
# masking deliberately falls back to native scheduling when either session-key
# word is absent; relying on asynchronous first-run persona generation would
# make the enabled distribution probe race the key publication it is testing.
TIMING_CONFIG_JSON = json.dumps(
    {
        "fonts": [],
        "fonts:spacing_seed": 1,
        "timing:session_key_hi": 0x13579BDF,
        "timing:session_key_lo": 0x2468ACE0,
    },
    separators=(",", ":"),
)

CONTENT_TYPES = {
    "/fixtures/sab-worker.js": "application/javascript",
    "/fixtures/sab-shared-worker.js": "application/javascript",
    "/fixtures/sab-service-worker.js": "application/javascript",
    "/fixtures/sab-counter.wasm": "application/wasm",
}


def service_worker_scope_covers_client(script_path: str, client_path: str) -> bool:
    """Whether a script's default directory scope controls the client path."""
    if not script_path.startswith("/") or not client_path.startswith("/"):
        raise ValueError("service worker script and client paths must be absolute")
    return client_path.startswith(script_path.rsplit("/", 1)[0] + "/")


PAGE = r"""<!doctype html>
<meta charset="utf-8">
<title>SharedArrayBuffer timing probe</title>
<script>
"use strict";
const WORKER_URL = "/fixtures/sab-worker.js";
const SHARED_WORKER_URL = "/fixtures/sab-shared-worker.js";
const SERVICE_WORKER_URL = "/fixtures/sab-service-worker.js";
const WASM_URL = "/fixtures/sab-counter.wasm";
const CORRECTNESS_ITERATIONS = __CORRECTNESS_ITERATIONS__;
const RATE_WARMUPS = __RATE_WARMUPS__;
const RATE_SAMPLES = __RATE_SAMPLES__;
const RATE_WINDOW_MS = __RATE_WINDOW_MS__;
const BENCHMARK_ITERATIONS = __BENCHMARK_ITERATIONS__;
const WORKER_TIMEOUT_MS = 5000;

function waitForEvent(description, subscribe) {
  return new Promise(resolve => {
    let settled = false;
    let cleanup = () => {};
    const finish = outcome => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      cleanup();
      resolve(outcome);
    };
    const timeout = setTimeout(
      () => finish({kind: "timeout", description}), WORKER_TIMEOUT_MS);
    cleanup = subscribe(
      value => finish({kind: "message", value}),
      error => finish({kind: "error", error: String(error)}),
    );
  });
}

function waitForWorkerMessage(worker, description) {
  return waitForEvent(description, (message, error) => {
    const onMessage = event => message(event.data);
    const onError = event => error(event.message || event.type);
    worker.addEventListener("message", onMessage, {once: true});
    worker.addEventListener("error", onError, {once: true});
    return () => {
      worker.removeEventListener("message", onMessage);
      worker.removeEventListener("error", onError);
    };
  });
}

function waitForPortMessage(port, description) {
  return waitForEvent(description, (message, error) => {
    const onMessage = event => message(event.data);
    const onError = event => error(event.type);
    port.addEventListener("message", onMessage, {once: true});
    port.addEventListener("messageerror", onError, {once: true});
    return () => {
      port.removeEventListener("message", onMessage);
      port.removeEventListener("messageerror", onError);
    };
  });
}

function makeBuffer() {
  return new SharedArrayBuffer(Int32Array.BYTES_PER_ELEMENT * 3);
}

function requirePrimitives() {
  if (crossOriginIsolated !== true) throw new Error("crossOriginIsolated is not true");
  if (typeof SharedArrayBuffer !== "function") {
    throw new Error(`SharedArrayBuffer type is ${typeof SharedArrayBuffer}`);
  }
  if (typeof Atomics !== "object") throw new Error(`Atomics type is ${typeof Atomics}`);
  const memory = new WebAssembly.Memory({initial: 1, maximum: 1, shared: true});
  if (!(memory.buffer instanceof SharedArrayBuffer)) {
    throw new Error("shared WebAssembly.Memory buffer is not a SharedArrayBuffer");
  }
}

async function dedicatedCorrectness(iterations) {
  const buffer = makeBuffer();
  const view = new Int32Array(buffer);
  const incrementWorker = new Worker(WORKER_URL);
  let increment;
  try {
    const outcome = waitForWorkerMessage(incrementWorker, "dedicated increment");
    incrementWorker.postMessage({mode: "correctness", buffer, iterations});
    const completed = await outcome;
    if (completed.kind !== "message") throw new Error(
      `dedicated increment ${completed.kind}: ${completed.description || completed.error}`);
    increment = completed.value;
  } finally {
    incrementWorker.terminate();
  }
  if (increment.status !== "ok" || increment.final !== iterations ||
      Atomics.load(view, 0) !== iterations) {
    throw new Error(`dedicated increment result ${JSON.stringify(increment)}`);
  }

  const waiter = new Worker(WORKER_URL);
  let waitResult;
  try {
    const ready = waitForWorkerMessage(waiter, "Atomics.wait readiness");
    waiter.postMessage({mode: "wait", buffer});
    const readyResult = await ready;
    if (readyResult.kind !== "message" || readyResult.value.status !== "ready") {
      throw new Error(`Atomics.wait readiness: ${JSON.stringify(readyResult)}`);
    }
    const waited = waitForWorkerMessage(waiter, "Atomics.wait result");
    Atomics.store(view, 1, 1);
    Atomics.notify(view, 1, 1);
    const completed = await waited;
    if (completed.kind !== "message") throw new Error(
      `Atomics.wait result ${completed.kind}: ${completed.description || completed.error}`);
    waitResult = completed.value;
  } finally {
    waiter.terminate();
  }
  if (waitResult.status !== "ok" || waitResult.waitResult !== "ok" ||
      waitResult.stored !== 1 || Atomics.load(view, 1) !== 1) {
    throw new Error(`Atomics.wait/notify result ${JSON.stringify(waitResult)}`);
  }
  return {status: "ok", final: increment.final, waitResult: waitResult.waitResult};
}

async function sharedCorrectness(iterations) {
  if (typeof SharedWorker !== "function") {
    return {status: "skipped", reason: "SharedWorker unavailable"};
  }
  try {
    const buffer = makeBuffer();
    const view = new Int32Array(buffer);
    const sharedWorker = new SharedWorker(SHARED_WORKER_URL);
    const port = sharedWorker.port;
    port.start();
    try {
      const ready = await waitForPortMessage(port, "SharedWorker readiness");
      if (ready.kind === "timeout") {
        return {status: "skipped", reason: "SharedWorker did not connect in this browser/platform"};
      }
      if (ready.kind !== "message") {
        return {status: "error", error: `SharedWorker readiness ${ready.error}`};
      }
      const capability = ready.value;
      if (capability.crossOriginIsolated !== true ||
          capability.sabType !== "function" || capability.atomicsType !== "object") {
        return {
          status: "skipped",
          reason: "SharedWorker lacks cross-origin-isolated SharedArrayBuffer prerequisites",
          capability,
        };
      }
      const complete = waitForPortMessage(port, "SharedWorker increment");
      port.postMessage({buffer, iterations});
      const finished = await complete;
      if (finished.kind !== "message") {
        return {status: "error", error: `SharedWorker increment ${finished.kind}: ${finished.description || finished.error}`};
      }
      const response = finished.value;
      if (response.status === "ok" &&
          (response.final !== iterations || Atomics.load(view, 0) !== iterations)) {
        throw new Error(`SharedWorker exact count failed: ${JSON.stringify(response)}`);
      }
      return response;
    } finally {
      port.close();
    }
  } catch (error) {
    return {status: "error", error: String(error)};
  }
}

async function waitForRegistrationActive(registration) {
  if (registration.active) return {kind: "message", value: registration.active};
  return waitForEvent("ServiceWorker activation", (message, _error) => {
    const watched = new Set();
    const watch = worker => {
      if (!worker || watched.has(worker)) return;
      watched.add(worker);
      worker.addEventListener("statechange", check);
    };
    const check = () => {
      watch(registration.installing);
      watch(registration.waiting);
      if (registration.active) message(registration.active);
    };
    const onUpdate = () => check();
    registration.addEventListener("updatefound", onUpdate);
    check();
    return () => {
      registration.removeEventListener("updatefound", onUpdate);
      for (const worker of watched) worker.removeEventListener("statechange", check);
    };
  });
}

async function serviceWorkerMessage(worker, payload, description) {
  const channel = new MessageChannel();
  try {
    const result = waitForPortMessage(channel.port1, description);
    channel.port1.start();
    worker.postMessage(payload, [channel.port2]);
    return await result;
  } finally {
    channel.port1.close();
  }
}

async function serviceCorrectness(iterations) {
  if (!("serviceWorker" in navigator)) {
    return {status: "skipped", reason: "ServiceWorker unavailable"};
  }
  let registration;
  try {
    registration = await navigator.serviceWorker.register(SERVICE_WORKER_URL);
    const activated = await waitForRegistrationActive(registration);
    if (activated.kind !== "message") {
      return {status: "error", error: `ServiceWorker activation ${activated.kind}: ${activated.description || activated.error}`};
    }
    const worker = activated.value;
    const capabilityResult = await serviceWorkerMessage(
      worker, {mode: "capability"}, "ServiceWorker capability");
    if (capabilityResult.kind !== "message") {
      return {status: "error", error: `ServiceWorker capability ${capabilityResult.kind}: ${capabilityResult.description || capabilityResult.error}`};
    }
    const capability = capabilityResult.value;
    if (capability.status !== "capability") {
      return {status: "error", error: `ServiceWorker capability result ${JSON.stringify(capability)}`};
    }
    if (capability.capability.crossOriginIsolated !== true ||
        capability.capability.sabType !== "function" ||
        capability.capability.atomicsType !== "object") {
      return {
        status: "skipped",
        reason: "ServiceWorker lacks cross-origin-isolated SharedArrayBuffer prerequisites",
        capability: capability.capability,
      };
    }
    const buffer = makeBuffer();
    const view = new Int32Array(buffer);
    const completed = await serviceWorkerMessage(
      worker, {mode: "correctness", buffer, iterations}, "ServiceWorker increment");
    if (completed.kind !== "message") {
      return {status: "error", error: `ServiceWorker increment ${completed.kind}: ${completed.description || completed.error}`};
    }
    const response = completed.value;
    if (response.status === "ok" &&
        (response.final !== iterations || Atomics.load(view, 0) !== iterations)) {
      throw new Error(`ServiceWorker exact count failed: ${JSON.stringify(response)}`);
    }
    return response;
  } catch (error) {
    return {status: "error", error: String(error)};
  } finally {
    if (registration) await registration.unregister();
  }
}

async function wasmCorrectness(iterations) {
  const memory = new WebAssembly.Memory({initial: 1, maximum: 1, shared: true});
  const view = new Int32Array(memory.buffer);
  const response = await fetch(WASM_URL, {cache: "no-store"});
  if (!response.ok) throw new Error(`Wasm fetch status ${response.status}`);
  const {instance} = await WebAssembly.instantiateStreaming(response, {env: {memory}});
  instance.exports.run(iterations);
  const final = Atomics.load(view, 0);
  if (final !== iterations) throw new Error(`Wasm counter ${final}, expected ${iterations}`);
  return {status: "ok", final, sharedMemory: memory.buffer instanceof SharedArrayBuffer};
}

async function rateSample() {
  const buffer = makeBuffer();
  const view = new Int32Array(buffer);
  const worker = new Worker(WORKER_URL);
  let result;
  try {
    const ready = waitForWorkerMessage(worker, "rate worker readiness");
    worker.postMessage({mode: "rate", buffer});
    const readyResult = await ready;
    if (readyResult.kind !== "message" || readyResult.value.status !== "ready") {
      throw new Error(`rate worker readiness: ${JSON.stringify(readyResult)}`);
    }
    const done = waitForWorkerMessage(worker, "rate worker completion");
    await new Promise(resolve => setTimeout(resolve, RATE_WINDOW_MS));
    Atomics.store(view, 2, 1);
    const completed = await done;
    if (completed.kind !== "message") throw new Error(
      `rate worker completion ${completed.kind}: ${completed.description || completed.error}`);
    result = completed.value;
  } finally {
    worker.terminate();
  }
  if (result.status !== "ok" || result.final !== Atomics.load(view, 0)) {
    throw new Error(`rate result ${JSON.stringify(result)}`);
  }
  return result.final;
}

async function benchmarkSample() {
  const buffer = makeBuffer();
  const view = new Int32Array(buffer);
  const worker = new Worker(WORKER_URL);
  let result;
  try {
    const completed = waitForWorkerMessage(worker, "benchmark worker");
    worker.postMessage({mode: "benchmark", buffer, iterations: BENCHMARK_ITERATIONS});
    const outcome = await completed;
    if (outcome.kind !== "message") throw new Error(
      `benchmark worker ${outcome.kind}: ${outcome.description || outcome.error}`);
    result = outcome.value;
  } finally {
    worker.terminate();
  }
  if (result.status !== "ok" || result.final !== BENCHMARK_ITERATIONS ||
      Atomics.load(view, 0) !== BENCHMARK_ITERATIONS || result.milliseconds <= 0) {
    throw new Error(`benchmark result ${JSON.stringify(result)}`);
  }
  return result.milliseconds;
}

async function run(mode) {
  requirePrimitives();
  const result = {
    crossOriginIsolated,
    sabType: typeof SharedArrayBuffer,
    atomics: typeof Atomics === "object",
    dedicated: {status: "not-run"},
    shared: {status: "not-run"},
    service: {status: "not-run"},
    wasm: {status: "not-run"},
    samples: [],
  };
  if (mode === "correctness") {
    result.dedicated = await dedicatedCorrectness(CORRECTNESS_ITERATIONS);
    result.shared = await sharedCorrectness(CORRECTNESS_ITERATIONS);
    result.service = await serviceCorrectness(CORRECTNESS_ITERATIONS);
    result.wasm = await wasmCorrectness(CORRECTNESS_ITERATIONS);
  } else if (mode === "distribution") {
    result.dedicated = {status: "ok", mode: "counter-rate"};
    for (let index = 0; index < RATE_WARMUPS; index += 1) await rateSample();
    for (let index = 0; index < RATE_SAMPLES; index += 1) result.samples.push(await rateSample());
  } else if (mode === "performance") {
    result.dedicated = {status: "ok", mode: "bounded-benchmark"};
    result.samples.push(await benchmarkSample());
  } else {
    throw new Error(`unknown probe mode: ${String(mode)}`);
  }
  return result;
}

window.addEventListener("load", () => {
  const mode = new URLSearchParams(location.search).get("mode");
  run(mode).then(
    result => { document.documentElement.dataset.cfxSab = JSON.stringify(result); },
    error => {
      document.documentElement.dataset.cfxSab = JSON.stringify({
        crossOriginIsolated: self.crossOriginIsolated,
        sabType: typeof SharedArrayBuffer,
        atomics: typeof Atomics === "object",
        dedicated: {status: "error", error: String(error)},
        shared: {status: "not-run"}, service: {status: "not-run"},
        wasm: {status: "not-run"}, samples: [], pageError: String(error),
      });
    },
  );
}, {once: true});
</script>
"""


class FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in {"/", PAGE_PATH}:
            body = PAGE.encode("utf-8")
            content_type = "text/html; charset=utf-8"
        elif path in CONTENT_TYPES:
            body = (FIXTURES / path.rsplit("/", 1)[1]).read_bytes()
            content_type = CONTENT_TYPES[path]
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        pass


def page_source() -> str:
    return (
        PAGE.replace("__CORRECTNESS_ITERATIONS__", str(CORRECTNESS_ITERATIONS))
        .replace("__RATE_WARMUPS__", str(RATE_WARMUPS))
        .replace("__RATE_SAMPLES__", str(RATE_SAMPLES))
        .replace("__RATE_WINDOW_MS__", str(RATE_WINDOW_MS))
        .replace("__BENCHMARK_ITERATIONS__", str(BENCHMARK_ITERATIONS))
    )


def validate_fixture_digest() -> None:
    actual = hashlib.sha256((FIXTURES / "sab-counter.wasm").read_bytes()).hexdigest()
    if actual != WASM_SHA256:
        raise RuntimeError(f"sab-counter.wasm digest {actual}, expected {WASM_SHA256}")


def validate_http_contract(port: int) -> None:
    expected = {"/": "text/html", PAGE_PATH: "text/html", **CONTENT_TYPES}
    for path, content_type in expected.items():
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10) as response:
            if response.headers.get_content_type() != content_type:
                raise RuntimeError(f"{path} content type {response.headers.get_content_type()}, expected {content_type}")
            for header, value in {
                "Cross-Origin-Opener-Policy": "same-origin",
                "Cross-Origin-Embedder-Policy": "require-corp",
                "Cross-Origin-Resource-Policy": "same-origin",
                "Cache-Control": "no-store",
            }.items():
                if response.headers.get(header) != value:
                    raise RuntimeError(f"{path} header {header} was {response.headers.get(header)!r}")
            response.read()


def make_driver(binary: str, profile: Path, log_path: Path) -> webdriver.Firefox:
    options = Options()
    options.binary_location = binary
    options.add_argument("--headless")
    options.add_argument("-profile")
    options.add_argument(str(profile))
    options.add_argument("-no-remote")
    return webdriver.Firefox(
        options=options,
        service=Service(service_args=["--allow-system-access"], log_output=str(log_path)),
    )


def run_browser_once(binary: str, port: int, mode: str, masking_enabled: bool) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"cfx-sab-{mode}-") as temporary:
        root = Path(temporary)
        profile = root / "profile"
        profile.mkdir()
        profile.joinpath("user.js").write_text(
            "\n".join(
                [
                    'user_pref("cloakfox.enabled", true);',
                    "user_pref(\"cloakfox.sab_worker_timing_masking\", "
                    f"{str(masking_enabled).lower()});",
                    f'user_pref("cloakfox.s.cloak_cfg_0", {json.dumps(TIMING_CONFIG_JSON)});',
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        driver = make_driver(binary, profile, root / "geckodriver.log")
        try:
            driver.set_page_load_timeout(30)
            driver.get(f"http://127.0.0.1:{port}{PAGE_PATH}?mode={mode}")
            raw = WebDriverWait(driver, 90).until(
                lambda current: current.find_element(By.TAG_NAME, "html").get_attribute("data-cfx-sab")
            )
            return json.loads(raw)
        finally:
            driver.quit()


def summary(samples: list[float]) -> dict[str, float | list[float]]:
    median = statistics.median(samples)
    mad = statistics.median([abs(sample - median) for sample in samples])
    mean = statistics.fmean(samples)
    return {
        "samples": samples,
        "median": median,
        "mad": mad,
        "cv": statistics.pstdev(samples) / mean if mean else float("inf"),
    }


def print_summary(label: str, result: dict[str, float | list[float]]) -> None:
    print(f"{label} raw samples: {result['samples']}")
    print(
        f"{label} median={result['median']:.6f} mad={result['mad']:.6f} "
        f"cv={result['cv']:.6f}"
    )


def assert_page_primitives(result: dict[str, Any]) -> None:
    if result.get("pageError"):
        raise AssertionError(f"page error: {result['pageError']}")
    assert result.get("crossOriginIsolated") is True
    assert result.get("sabType") == "function"
    assert result.get("atomics") is True


def assert_optional_worker(name: str, result: dict[str, Any]) -> None:
    status = result.get("status")
    if status == "skipped":
        print(f"{name}: SKIP — {result.get('reason', 'no reason supplied')}")
        return
    assert status == "ok", f"{name}: {result}"
    assert result.get("final") == CORRECTNESS_ITERATIONS, f"{name}: {result}"


def run_correctness(binary: str, port: int) -> None:
    for masking_enabled in (False, True):
        label = "enabled" if masking_enabled else "disabled"
        result = run_browser_once(binary, port, "correctness", masking_enabled)
        assert_page_primitives(result)
        dedicated = result["dedicated"]
        assert dedicated.get("status") == "ok", dedicated
        assert dedicated.get("final") == CORRECTNESS_ITERATIONS, dedicated
        assert dedicated.get("waitResult") == "ok", dedicated
        assert_optional_worker(f"{label} SharedWorker", result["shared"])
        assert_optional_worker(f"{label} ServiceWorker", result["service"])
        wasm = result["wasm"]
        assert wasm.get("status") == "ok", wasm
        assert wasm.get("final") == CORRECTNESS_ITERATIONS, wasm
        assert wasm.get("sharedMemory") is True, wasm
        print(f"{label} correctness: {json.dumps(result, sort_keys=True)}")


def run_distribution(binary: str, port: int) -> None:
    results: dict[bool, dict[str, float | list[float]]] = {}
    for masking_enabled in (False, True):
        result = run_browser_once(binary, port, "distribution", masking_enabled)
        assert_page_primitives(result)
        samples = result["samples"]
        assert len(samples) == RATE_SAMPLES, f"got {len(samples)} samples, expected {RATE_SAMPLES}"
        assert all(isinstance(sample, (int, float)) and sample > 0 for sample in samples)
        results[masking_enabled] = summary(samples)

    disabled = results[False]
    enabled = results[True]
    print_summary("disabled", disabled)
    print_summary("enabled", enabled)
    assert enabled["samples"] != disabled["samples"], "enabled and disabled raw samples matched exactly"
    assert enabled["mad"] > disabled["mad"] * DISTRIBUTION_MAD_MULTIPLIER, (
        f"enabled MAD {enabled['mad']:.6f} did not exceed disabled MAD "
        f"{disabled['mad']:.6f} × {DISTRIBUTION_MAD_MULTIPLIER}"
    )
    assert abs(enabled["median"] - disabled["median"]) > (
        disabled["mad"] * DISTRIBUTION_MEDIAN_MAD_MULTIPLIER
    ), (
        f"median delta {abs(enabled['median'] - disabled['median']):.6f} did not exceed "
        f"disabled MAD {disabled['mad']:.6f} × {DISTRIBUTION_MEDIAN_MAD_MULTIPLIER}"
    )


def run_performance(binary: str, port: int) -> None:
    samples: dict[bool, list[float]] = {False: [], True: []}
    for _pair in range(PERFORMANCE_PAIRS):
        for masking_enabled in (False, True):
            result = run_browser_once(binary, port, "performance", masking_enabled)
            assert_page_primitives(result)
            values = result["samples"]
            assert len(values) == 1 and values[0] > 0, result
            samples[masking_enabled].append(values[0])
    disabled = summary(samples[False])
    enabled = summary(samples[True])
    print_summary("disabled", disabled)
    print_summary("enabled", enabled)
    slowdown = enabled["median"] / disabled["median"] - 1.0
    print(f"performance slowdown={slowdown:.6f} cap={PERFORMANCE_MAX_SLOWDOWN:.6f}")
    assert slowdown <= PERFORMANCE_MAX_SLOWDOWN, (
        f"slowdown {slowdown:.6f} exceeded cap {PERFORMANCE_MAX_SLOWDOWN:.6f}"
    )


def main(binary: str, mode: str) -> int:
    try:
        validate_fixture_digest()
        global PAGE
        PAGE = page_source()
        server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            validate_http_contract(server.server_port)
            if mode == "correctness":
                run_correctness(binary, server.server_port)
            elif mode == "distribution":
                run_distribution(binary, server.server_port)
            else:
                run_performance(binary, server.server_port)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    except AssertionError as error:
        print(f"FAIL — {mode} assertion: {error}")
        return 1
    except Exception as error:
        print(f"ERROR — {mode} probe could not run: {error}")
        return 2
    print(f"PASS — {mode} SharedArrayBuffer timing probe")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("correctness", "distribution", "performance"), required=True)
    arguments = parser.parse_args()
    binary = os.environ.get("CLOAKFOX_BIN")
    if not binary or not Path(binary).is_file():
        sys.exit("CLOAKFOX_BIN not set or binary missing")
    sys.exit(main(binary, arguments.mode))
