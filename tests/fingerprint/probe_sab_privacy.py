"""Diagnostic SAB clock recovery; no result constitutes a privacy PASS.

Run with --binary PATH --output FILE. Each policy gets a fresh profile. A
registered default preference is required to attribute a policy result; merely
setting an unknown preference never proves the mechanism exists. Stock Firefox
results are baselines, not evidence about the unbuilt Cloakfox branch.
"""
from __future__ import annotations

import argparse
import configparser
import json
import math
import statistics
import tempfile
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer

import probe_sharedarraybuffer_timing as fixture


def classify(samples: list[dict]) -> dict:
    """Fit one threshold on the first half; score untouched balanced second half."""
    if len(samples) < 8 or len(samples) % 4:
        raise ValueError("samples must contain at least eight balanced paired observations")
    split = len(samples) // 2
    train, test = samples[:split], samples[split:]
    for partition in (train, test):
        if sum(sample["label"] == 0 for sample in partition) != len(partition) // 2:
            raise ValueError("both partitions must balance low and high labels")
        if any(sample["label"] not in (0, 1) or sample["delta"] < 0 for sample in partition):
            raise ValueError("invalid observation")
    centers = [statistics.median(s["delta"] for s in train if s["label"] == label)
               for label in (0, 1)]
    threshold = sum(centers) / 2
    higher_is_high = centers[1] >= centers[0]
    predicted = [int(s["delta"] > threshold) if higher_is_high
                 else int(s["delta"] < threshold) for s in test]
    accuracy = sum(p == s["label"] for p, s in zip(predicted, test)) / len(test)
    # Descriptive only: adjacent observations can be correlated, so this
    # binomial interval is not a formal privacy guarantee or independence test.
    n, z = len(test), 1.96
    denominator = 1 + z * z / n
    midpoint = (accuracy + z * z / (2 * n)) / denominator
    radius = z * math.sqrt(accuracy * (1 - accuracy) / n + z * z / (4 * n * n)) / denominator
    return {"training_medians": centers, "threshold": threshold,
            "held_out_accuracy": accuracy, "held_out_count": len(test),
            "descriptive_wilson_95": [midpoint - radius, midpoint + radius],
            "nonzero_fraction": sum(s["delta"] > 0 for s in samples) / len(samples),
            "interpretation": "diagnostic only; chance classification does not establish privacy"}


def run(binary: str, port: int, policy: str, count: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="cfx-sab-privacy-") as temporary:
        root = Path(temporary)
        profile = root / "profile"
        profile.mkdir()
        # Use the established profile bootstrap, but create it through Selenium
        # options so this diagnostic never touches an existing user profile.
        options = fixture.Options()
        options.binary_location = binary
        for arg in ("--headless", "-profile", str(profile), "-no-remote"):
            options.add_argument(arg)
        prefs = {"cloakfox.enabled": True,
                 "cloakfox.s.cloak_cfg_0": fixture.TIMING_CONFIG_JSON,
                 "cloakfox.sab_worker_timing_masking": policy == "jitter",
                 "dom.workers.serialized-sab-access": policy == "serialized"}
        for name, value in prefs.items():
            options.set_preference(name, value)
        driver = fixture.webdriver.Firefox(options=options, service=fixture.Service(
            service_args=["--allow-system-access"], log_output=str(root / "driver.log")))
        try:
            driver.set_context("chrome")
            provenance = driver.execute_script("""
              const p = Services.prefs, defaults = p.getDefaultBranch("");
              const names = ["cloakfox.sab_worker_timing_masking", "dom.workers.serialized-sab-access"];
              return {version: Services.appinfo.version, buildID: Services.appinfo.appBuildID,
                sourceRevision: Services.appinfo.sourceRevision || null,
                prefs: Object.fromEntries(names.map(n => {
                  // getPrefType consults the global type even on the default
                  // branch, so an unknown user pref is a false positive.
                  let registered = false;
                  try { defaults.getBoolPref(n); registered = true; } catch (_) {}
                  return [n, {registered, effective: p.getBoolPref(n, false)}];
                }))};
            """)
            driver.set_context("content")
            driver.set_page_load_timeout(30)
            driver.set_script_timeout(50)
            driver.get(f"http://127.0.0.1:{port}/")
            result = driver.execute_async_script("""
              const done = arguments[arguments.length - 1];
              window.runSABPrivacy(arguments[0]).then(done, e => done({status:"inconclusive",reason:String(e)}));
            """, count)
            mechanism = {"jitter": "cloakfox.sab_worker_timing_masking",
                         "serialized": "dom.workers.serialized-sab-access"}.get(policy)
            known = not mechanism or provenance["prefs"][mechanism]["registered"]
            ini = configparser.ConfigParser(interpolation=None)
            ini.read(Path(binary).parent.parent / "Resources" / "application.ini")
            provenance["installed_application_ini"] = dict(ini["App"]) if "App" in ini else None
            report = {"binary": str(Path(binary).resolve()), "policy": policy,
                      "provenance": provenance, "mechanism_registered": known,
                      "result": result}
            if result["status"] == "measured":
                report["analysis"] = {realm: classify(result[realm]) for realm in ("worker", "main")}
                if policy == "native":
                    report["positive_control"] = {
                        realm: "workload signal observed" if analysis["descriptive_wilson_95"][0] > .5
                        else "inconclusive sensitivity; do not infer protection from a policy's zero result"
                        for realm, analysis in report["analysis"].items()}
            if not known:
                report["attribution"] = "inconclusive: requested mechanism is absent; samples are baseline only"
            return report
        finally:
            driver.quit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--policies", nargs="+", choices=("native", "jitter", "serialized"),
                        default=["native", "serialized", "jitter"])
    args = parser.parse_args()
    if args.samples < 8 or args.samples % 4:
        parser.error("--samples must be at least 8 and divisible by 4")
    fixture.PAGE = '<!doctype html><meta charset="utf-8"><script src="/fixtures/sab-privacy-worker.js"></script>'
    fixture.CONTENT_TYPES["/fixtures/sab-privacy-worker.js"] = "application/javascript"
    server = ThreadingHTTPServer(("127.0.0.1", 0), fixture.FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        reports = []
        for policy in args.policies:
            try:
                report = run(args.binary, server.server_port, policy, args.samples)
            except Exception as error:
                report = {"binary": args.binary, "policy": policy,
                          "status": "inconclusive", "reason": str(error)}
            reports.append(report)
            print(json.dumps({k: v for k, v in report.items() if k != "result"}), flush=True)
        Path(args.output).write_text(json.dumps(reports, indent=2) + "\n")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
