"""Unit test for probe_js_spoofers.evaluate_payload (finding #15).

The inline browser probe appends its result element in a `finally`, so a payload
is present even when the probe threw partway. The old code parsed that empty
`{}` as 0/0 heuristics and returned exit 0 — a false pass on a broken build.
evaluate_payload must return 2 (unjudgeable) for an incomplete/empty run.

    python tests/fingerprint/test_probe_js_spoofers_scoring.py   # exit 0 = pass
"""
import json
import os
import sys
from importlib import import_module

sys.path.insert(0, os.path.dirname(__file__))
probe = import_module("probe_js_spoofers")
evaluate_payload = probe.evaluate_payload


def main() -> int:
    fails = []

    def check(name, raw, expected):
        got = evaluate_payload(raw)
        if got != expected:
            fails.append(f"{name}: expected exit {expected}, got {got}")

    # The regression: probe threw before finishing -> only `{}` appended.
    check("empty payload (probe threw)", "{}", 2)
    # A partial payload with real signals but NO completion sentinel is still a
    # failed run — the probe didn't finish, so its verdicts are untrustworthy.
    check("partial, no sentinel",
          json.dumps({"userAgent": "Cloakfox/1.0", "platform": "Linux x86_64"}),
          2)
    # Completed run, everything spoofed (no UNSPOOFED markers matched) -> 0.
    check("complete, all spoofed",
          json.dumps({"__ok": True, "userAgent": "Mozilla/5.0 Firefox",
                      "platform": "Win32"}),
          0)
    # Completed run with a leaked native signal -> 1.
    check("complete, one unspoofed",
          json.dumps({"__ok": True, "userAgent": "Cloakfox/1.0",  # native UA leaked
                      "platform": "Win32"}),
          1)
    # Completed run but no heuristic keys at all -> unjudgeable -> 2.
    check("complete, zero heuristics",
          json.dumps({"__ok": True, "window.name": "", "navigator.gpu": "object"}),
          2)
    # Garbage payload -> 2.
    check("non-JSON payload", "not json at all", 2)
    check("JSON but not an object", json.dumps([1, 2, 3]), 2)

    if fails:
        print("FAIL — evaluate_payload scoring regressed:")
        for m in fails:
            print(f"  - {m}")
        return 1
    print("PASS — incomplete/empty/garbage payloads score as failure (2); "
          "complete runs score 0/1 correctly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
