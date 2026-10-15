"""Master switch gates DOM and native H2 despite stale Chrome adapter state.

Use the production per-container adapter selector and trusted loopback TLS.
Independent stock Firefox157 / Chrome155 captures anchor exact wire assertions.
"""
import json
import os
from pathlib import Path
import tempfile

from test_h2_profile import _probe, _shape, _pinned_shapes
from h3_fixture import create_certificates
from wire_fixture import TLSFixture


def main(bin_path):
    report = Path(__file__).parent / "reports/157-privacy-port/killswitch"
    report.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cloakfox-killswitch-certs-") as tmp:
        ca, cert, key = create_certificates(Path(tmp), ["h2-profile.test"])
        fixture = TLSFixture(cert, key)
        try:
            results = [_probe(bin_path, "chrome", report, ca, fixture, enabled=value)
                       for value in (True, False, False)]
        finally:
            fixture.close()
    enabled, disabled, second_disabled = results
    shapes = _pinned_shapes()
    assert _shape(enabled["wire"]) == _shape(shapes["chrome"]), enabled
    for value in (disabled, second_disabled):
        assert value["observedState"]["enabled"] is False, value
        assert value["observedState"]["atomicState"] & 1 == 1, value
        assert _shape(value["wire"]) == _shape(shapes["firefox"]), value
    assert disabled["navigator"] == second_disabled["navigator"], results
    assert enabled["navigator"][2] != disabled["navigator"][2], results
    (report / "results.json").write_text(json.dumps(results, indent=2))
    print("PASS: master-off gates DOM and H2 with held stale Chrome state across two fresh profiles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(os.environ["CLOAKFOX_BIN"]))
