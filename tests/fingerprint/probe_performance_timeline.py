"""Performance timeline presentation regression probe.

The page itself installs PerformanceObservers, reads getters, calls toJSON(),
and publishes snapshots. Selenium supplies only a trusted pointer interaction
and reads the page-main-world result from a data attribute.

Exit codes: 0 pass · 1 regressed · 2 couldn't run.

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \
        python tests/fingerprint/probe_performance_timeline.py
"""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait


EXPECTED_TYPES = {
    "event",
    "first-input",
    "largest-contentful-paint",
    "mark",
    "measure",
    "navigation",
    "paint",
    "resource",
}
FEATURE_GATED_TYPES = {"event", "first-input", "largest-contentful-paint"}
CORE_TYPES = EXPECTED_TYPES - FEATURE_GATED_TYPES
NATIVE_TYPES = {
    "event",
    "first-input",
    "largest-contentful-paint",
    "navigation",
    "paint",
    "resource",
}
NETWORK_PHASES = [
    "startTime",
    "redirectStart",
    "redirectEnd",
    "workerStart",
    "fetchStart",
    "domainLookupStart",
    "domainLookupEnd",
    "connectStart",
    "secureConnectionStart",
    "connectEnd",
    "requestStart",
    "responseStart",
    "responseEnd",
]
TIMESTAMP_KEYS = [
    "startTime",
    "processingStart",
    "processingEnd",
    "renderTime",
    "loadTime",
    "workerStart",
    "redirectStart",
    "redirectEnd",
    "fetchStart",
    "domainLookupStart",
    "domainLookupEnd",
    "connectStart",
    "connectEnd",
    "secureConnectionStart",
    "requestStart",
    "responseStart",
    "responseEnd",
    "unloadEventStart",
    "unloadEventEnd",
    "domInteractive",
    "domContentLoadedEventStart",
    "domContentLoadedEventEnd",
    "domComplete",
    "loadEventStart",
    "loadEventEnd",
]


PAGE = r"""<!doctype html>
<meta charset="utf-8">
<title>Cloakfox performance timeline probe</title>
<style>
  body { margin: 0; font: 20px sans-serif; }
  #probe-button { position: fixed; z-index: 2; top: 12px; left: 12px;
                  width: 180px; height: 56px; }
  #hero { display: block; width: 900px; height: 600px; margin-top: 80px;
          object-fit: cover; background: #17324d; }
</style>
<script>
(() => {
  const extraKeys = [
    "processingStart", "processingEnd", "renderTime", "loadTime",
    "workerStart", "redirectStart", "redirectEnd", "fetchStart",
    "domainLookupStart", "domainLookupEnd", "connectStart", "connectEnd",
    "secureConnectionStart", "requestStart", "responseStart", "responseEnd",
    "unloadEventStart", "unloadEventEnd", "domInteractive",
    "domContentLoadedEventStart", "domContentLoadedEventEnd", "domComplete",
    "loadEventStart", "loadEventEnd", "transferSize", "encodedBodySize",
    "decodedBodySize", "responseStatus"
  ];
  const observed = [];
  const observerErrors = {};
  const advertised = [...PerformanceObserver.supportedEntryTypes];

  function snapshot(entry) {
    const extra = {};
    for (const key of extraKeys) if (key in entry) extra[key] = entry[key];
    return {
      name: entry.name, type: entry.entryType,
      startTime: entry.startTime, duration: entry.duration,
      rereadStart: entry.startTime, json: entry.toJSON(), extra,
    };
  }

  for (const type of advertised) {
    try {
      const observer = new PerformanceObserver(list => {
        for (const entry of list.getEntries()) {
          observed.push(entry);
        }
      });
      const options = {type, buffered: true};
      if (type === "event") options.durationThreshold = 16;
      observer.observe(options);
    } catch (error) {
      observerErrors[type] = String(error);
    }
  }

  window.addEventListener("DOMContentLoaded", () => {
    const beforeDefaultMark = performance.now();
    const defaultMark = performance.mark("default-mark");
    const afterDefaultMark = performance.now();
    const explicitMark = performance.mark("explicit", {startTime: 123.25});
    const explicitMeasure = performance.measure(
      "explicit-measure", {start: 10.25, end: 20.75});
    performance.measure("default-measure", {start: "default-mark"});

    const image = document.querySelector("#hero");
    image.src = `/probe-image.svg?nonce=${Date.now()}`;
    const fetchDone = fetch(`/probe-resource.bin?nonce=${Date.now()}`)
      .then(response => response.arrayBuffer());
    const opaqueImage = new Image();
    const opaqueDone = new Promise(resolve => {
      opaqueImage.addEventListener("load", resolve, {once: true});
    });
    opaqueImage.src =
      `http://127.0.0.1:__CROSS_ORIGIN_PORT__/opaque.svg?nonce=${Date.now()}`;

    async function finish() {
      await new Promise(resolve => {
        if (image.complete) resolve();
        else image.addEventListener("load", resolve, {once: true});
      });
      await fetchDone;
      await opaqueDone;
      await new Promise(requestAnimationFrame);
      await new Promise(requestAnimationFrame);
      await new Promise(resolve => setTimeout(resolve, 250));

      // Navigation timing fields can mature after the buffered callback.
      // Snapshot the observer-delivered objects only after load is complete,
      // then reread them immediately to verify stable public presentation.
      const callbacks = observed.map(snapshot);
      const direct = observed.map(snapshot);
      const getEntries = performance.getEntries().map(snapshot);
      const getEntriesByType = Object.fromEntries(advertised.map(type => [
        type, performance.getEntriesByType(type).map(snapshot),
      ]));
      const getEntriesByName = getEntries.map(source => ({
        source,
        entries: performance.getEntriesByName(source.name, source.type)
          .map(snapshot),
      }));
      document.documentElement.dataset.cfxTimeline = JSON.stringify({
        advertised, observerErrors, callbacks, direct, getEntries,
        getEntriesByType, getEntriesByName,
        userTiming: {
          beforeDefaultMark,
          defaultMark: snapshot(defaultMark),
          afterDefaultMark,
          explicitMark: snapshot(explicitMark),
          explicitMeasure: snapshot(explicitMeasure),
        },
      });
    }

    document.querySelector("#probe-button").addEventListener(
      "pointerdown",
      () => {
        const deadline = performance.now() + 140;
        while (performance.now() < deadline) {}
        setTimeout(() => finish().catch(error => {
          document.documentElement.dataset.cfxTimeline = JSON.stringify({
            pageError: String(error), advertised, observerErrors,
          });
        }), 0);
      },
      {once: true},
    );
  });
})();
</script>
<button id="probe-button" type="button">Generate trusted event</button>
<img id="hero" width="900" height="600" alt="large timing probe image">
"""


IMAGE = b"""<svg xmlns="http://www.w3.org/2000/svg" width="900" height="600">
<rect width="900" height="600" fill="#315b7d"/>
<circle cx="450" cy="300" r="220" fill="#d6b35a"/>
</svg>"""


class ProbeHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith("/probe-image.svg"):
            body = IMAGE
            content_type = "image/svg+xml"
        elif self.path.startswith("/probe-resource.bin"):
            body = b"cloakfox-performance-resource"
            content_type = "application/octet-stream"
        else:
            body = PAGE.replace(
                "__CROSS_ORIGIN_PORT__", str(CROSS_ORIGIN_PORT)
            ).encode("utf-8")
            content_type = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Timing-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        pass


class OpaqueHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml")
        self.send_header("Content-Length", str(len(IMAGE)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(IMAGE)

    def log_message(self, _format: str, *_args: object) -> None:
        pass


CROSS_ORIGIN_PORT = 0


def run(bin_path: str) -> dict:
    global CROSS_ORIGIN_PORT
    opaque_server = ThreadingHTTPServer(("127.0.0.1", 0), OpaqueHandler)
    CROSS_ORIGIN_PORT = opaque_server.server_port
    opaque_thread = threading.Thread(
        target=opaque_server.serve_forever, daemon=True
    )
    opaque_thread.start()
    server = ThreadingHTTPServer(("127.0.0.1", 0), ProbeHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="cfx-timeline-") as temp_dir:
            profile = Path(temp_dir, "profile")
            profile.mkdir()
            Path(profile, "user.js").write_text(
                '\n'.join(
                    [
                        'user_pref("cloakfox.enabled", true);',
                        'user_pref("dom.enable_event_timing", true);',
                        'user_pref("dom.enable_largest_contentful_paint", true);',
                        'user_pref("dom.enable_performance_observer", true);',
                        'user_pref("dom.enable_resource_timing", true);',
                        'user_pref("dom.enable_performance_navigation_timing", true);',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            options = Options()
            options.binary_location = bin_path
            options.add_argument("--headless")
            options.add_argument("-profile")
            options.add_argument(str(profile))
            options.add_argument("-no-remote")
            driver = webdriver.Firefox(
                options=options,
                service=Service(
                    service_args=["--allow-system-access"],
                    log_output=str(Path(temp_dir, "geckodriver.log")),
                ),
            )
            try:
                driver.set_window_size(1280, 900)
                driver.set_page_load_timeout(30)
                # cloakfox.cfg intentionally disables resource timing for
                # ordinary browsing. This coverage probe explicitly enables
                # Firefox's eight-type matrix before the test page is loaded.
                driver.set_context("chrome")
                driver.execute_script(
                    'Services.prefs.setBoolPref("dom.enable_resource_timing", true);'
                )
                driver.set_context("content")
                driver.get(f"http://127.0.0.1:{server.server_port}/")
                button = driver.find_element(By.ID, "probe-button")
                ActionChains(driver).move_to_element(button).click().perform()
                raw = WebDriverWait(driver, 30).until(
                    lambda current: current.find_element(
                        By.TAG_NAME, "html"
                    ).get_attribute("data-cfx-timeline")
                )
                return json.loads(raw)
            finally:
                driver.quit()
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
        opaque_server.shutdown()
        opaque_server.server_close()
        opaque_thread.join(timeout=5)


def is_fractional(value: float) -> bool:
    return not math.isclose(value, round(value), rel_tol=0.0, abs_tol=1e-9)


def same_snapshot(left: dict, right: dict) -> bool:
    return left == right


def entry_key(entry: dict) -> tuple[str, str, float, float]:
    return (entry["type"], entry["name"], entry["startTime"], entry["duration"])


def validate(result: dict) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    skips: list[str] = []
    if "pageError" in result:
        return [f"page probe failed: {result['pageError']}"], skips

    advertised = set(result["advertised"])
    unexpected = advertised - EXPECTED_TYPES
    missing_core = CORE_TYPES - advertised
    if unexpected:
        failures.append(f"supportedEntryTypes added unexpected types: {sorted(unexpected)}")
    if missing_core:
        failures.append(f"supportedEntryTypes lost core types: {sorted(missing_core)}")
    for entry_type in sorted(FEATURE_GATED_TYPES - advertised):
        skips.append(f"{entry_type}: not advertised by this Firefox build")

    if result["observerErrors"]:
        failures.append(f"observer registration errors: {result['observerErrors']}")

    callbacks = result["callbacks"]
    direct = result["direct"]
    get_entries = result["getEntries"]
    if len(callbacks) != len(direct):
        failures.append("observer callback and direct reread counts differ")

    for index, (callback, reread) in enumerate(zip(callbacks, direct)):
        if not same_snapshot(callback, reread):
            failures.append(
                f"{callback['type']}:{callback['name']} changed between "
                f"observer callback and direct reread (index {index})"
            )

    observed_by_key: dict[tuple[str, str, float, float], list[dict]] = {}
    for entry in direct:
        observed_by_key.setdefault(entry_key(entry), []).append(entry)
    for entry in get_entries:
        matches = observed_by_key.get(entry_key(entry), [])
        if entry["type"] in advertised and not matches:
            failures.append(
                f"getEntries entry missing matching observer snapshot: "
                f"{entry['type']}:{entry['name']}"
            )
        elif matches and not any(same_snapshot(entry, match) for match in matches):
            failures.append(
                f"getEntries snapshot differs from observer snapshot: "
                f"{entry['type']}:{entry['name']}"
            )

    for entry_type, entries in result["getEntriesByType"].items():
        for entry in entries:
            matches = observed_by_key.get(entry_key(entry), [])
            if not any(same_snapshot(entry, match) for match in matches):
                failures.append(
                    f"getEntriesByType({entry_type}) snapshot differs from "
                    f"observer snapshot: {entry['name']}"
                )

    for group in result["getEntriesByName"]:
        source = group["source"]
        if not any(same_snapshot(source, entry) for entry in group["entries"]):
            failures.append(
                f"getEntriesByName snapshot missing source entry: "
                f"{source['type']}:{source['name']}"
            )

    entries_by_type: dict[str, list[dict]] = {}
    for entry in direct:
        entries_by_type.setdefault(entry["type"], []).append(entry)

        if entry["rereadStart"] != entry["startTime"]:
            failures.append(f"{entry['type']}:{entry['name']} startTime reread changed")
        serialized = entry["json"]
        expected_base = {
            "name": entry["name"],
            "entryType": entry["type"],
            "startTime": entry["startTime"],
            "duration": entry["duration"],
        }
        for key, expected in expected_base.items():
            if serialized.get(key) != expected:
                failures.append(
                    f"{entry['type']}:{entry['name']} toJSON {key} differs "
                    "from direct getter"
                )
        for key, expected in entry["extra"].items():
            if serialized.get(key) != expected:
                failures.append(
                    f"{entry['type']}:{entry['name']} toJSON {key} differs "
                    "from direct getter"
                )

        if not math.isfinite(entry["duration"]) or entry["duration"] < 0:
            failures.append(f"{entry['type']}:{entry['name']} has invalid duration")
        for key in TIMESTAMP_KEYS:
            value = entry["startTime"] if key == "startTime" else entry["extra"].get(key)
            if value is not None and (not math.isfinite(value) or value < 0):
                failures.append(
                    f"{entry['type']}:{entry['name']} has invalid {key}={value}"
                )

    for entry_type in sorted(advertised & EXPECTED_TYPES):
        if not entries_by_type.get(entry_type):
            failures.append(f"advertised type {entry_type} produced no entry")

    for entry_type in sorted(advertised & NATIVE_TYPES):
        values = []
        for entry in entries_by_type.get(entry_type, []):
            values.append(entry["startTime"])
            values.extend(entry["extra"].values())
            if entry["duration"]:
                values.append(entry["duration"])
        nonzero = [value for value in values if value]
        if nonzero and not any(is_fractional(value) for value in nonzero):
            failures.append(
                f"{entry_type} exposes only whole-millisecond native timestamps"
            )

    for entry_type in ("resource", "navigation"):
        for entry in entries_by_type.get(entry_type, []):
            phases = []
            for key in NETWORK_PHASES:
                value = (
                    entry["startTime"]
                    if key == "startTime"
                    else entry["extra"].get(key, 0)
                )
                if value != 0:
                    phases.append((key, value))
            for (left_key, left), (right_key, right) in zip(phases, phases[1:]):
                if right < left:
                    failures.append(
                        f"{entry_type}:{entry['name']} phase order decreased: "
                        f"{left_key}={left} > {right_key}={right}"
                    )
            endpoint = (
                entry["extra"].get("loadEventEnd")
                if entry_type == "navigation"
                else entry["extra"].get("responseEnd")
            )
            if endpoint is not None and not math.isclose(
                entry["duration"],
                endpoint - entry["startTime"],
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                failures.append(
                    f"{entry_type}:{entry['name']} duration is not its "
                    "presented endpoint difference"
                )

    opaque_entries = [
        entry
        for entry in entries_by_type.get("resource", [])
        if "/opaque.svg" in entry["name"]
    ]
    if not opaque_entries:
        failures.append("opaque cross-origin resource produced no timing entry")
    else:
        protected_keys = [
            "redirectStart",
            "redirectEnd",
            "domainLookupStart",
            "domainLookupEnd",
            "connectStart",
            "connectEnd",
            "secureConnectionStart",
            "requestStart",
            "responseStart",
            "transferSize",
            "encodedBodySize",
            "decodedBodySize",
            "responseStatus",
        ]
        for key in protected_keys:
            if opaque_entries[0]["extra"].get(key) != 0:
                failures.append(f"opaque cross-origin {key} did not stay zero")

    timing = result["userTiming"]
    explicit_mark = timing["explicitMark"]
    explicit_measure = timing["explicitMeasure"]
    if explicit_mark["startTime"] != 123.25:
        failures.append("explicit mark startTime changed from 123.25")
    if explicit_measure["startTime"] != 10.25:
        failures.append("explicit measure startTime changed from 10.25")
    if explicit_measure["duration"] != 10.5:
        failures.append("explicit measure duration changed from 10.5")

    default_mark = timing["defaultMark"]["startTime"]
    if not is_fractional(default_mark):
        failures.append("default mark does not use the native presented clock")

    return failures, skips


def main(bin_path: str) -> int:
    try:
        result = run(bin_path)
    except Exception as error:
        print(f"ERROR — performance timeline probe could not run: {error}")
        return 2

    failures, skips = validate(result)
    advertised = result.get("advertised", [])
    counts: dict[str, int] = {}
    for entry in result.get("direct", []):
        counts[entry["type"]] = counts.get(entry["type"], 0) + 1
    print(f"  advertised: {', '.join(advertised)}")
    print(
        "  observed: "
        + ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    )
    for skip in skips:
        print(f"  SKIP — {skip}")

    print()
    if failures:
        print("FAIL — performance timeline presentation regressed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(
        "PASS — all advertised performance entries are coherent and explicit "
        "User Timing values are exact"
    )
    return 0


if __name__ == "__main__":
    binary = os.environ.get("CLOAKFOX_BIN")
    if not binary or not os.path.exists(binary):
        sys.exit("CLOAKFOX_BIN not set or binary missing")
    sys.exit(main(binary))
