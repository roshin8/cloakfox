"""HTTP/2 wire shapes selected through the current container network adapter.

Firefox 158 exposes native Firefox and an opt-in measured Chrome 155 adapter.
Legacy global H2 preferences are metadata, and Safari has no supported adapter.
Use a trusted loopback TLS fixture; no external fingerprint service is contacted.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import ssl
import sys
import tempfile

import pytest
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "network"))
from h3_fixture import create_certificates
from wire_fixture import TLSFixture

ROOT = Path(__file__).resolve().parents[2]
CLOAKFOX_BIN = os.environ.get("CLOAKFOX_BIN")
UA = {
    "firefox": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:158.0) Gecko/20100101 Firefox/158.0",
    "chrome": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36",
    "safari": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
}


def _pinned_shapes():
    # Independent stock Firefox158 capture and retained Chrome155 reference.
    # Never derive expectations from Gecko
    # implementation constants or the browser under test.
    native = json.loads((ROOT / "docs/firefox-158-port/network-adapter-native-tls-h2.json").read_text())
    chrome = json.loads((ROOT / "docs/firefox-157-port/chrome-network-reference.json").read_text())
    assert native["stock"]["version"] == "158.0"
    assert chrome["version"] == "Google Chrome 155.0.8059.40"
    return {"firefox": native["stock"]["connections"][0], "chrome": chrome["h2"][0]}


def _shape(observation):
    return {"settings": [list(pair) for pair in observation["settings"][0]],
            "window_update": observation["windowUpdates"][0],
            "pseudo_order": observation["pseudoHeaders"][0]}


def _probe(bin_path, profile, log_dir, certificate, fixture, enabled=True):
    options = Options()
    options.binary_location = bin_path
    options.accept_insecure_certs = False
    options.add_argument("-headless")
    options.add_argument("-purgecaches")
    options.set_preference("network.dns.localDomains", "h2-profile.test")
    options.set_preference("network.trr.mode", 5)
    # Deliberately conflicting historical input must not override owner intent.
    options.set_preference("network.http.http2.fingerprint_profile", "safari")
    with tempfile.TemporaryDirectory(prefix="cloakfox-h2-profile-", dir="/tmp") as tmp:
        options.add_argument("-profile")
        options.add_argument(tmp)
        service = Service(service_args=["--allow-system-access"],
                          log_output=str(log_dir / f"gd-{profile}.log"))
        driver = webdriver.Firefox(options=options, service=service)
        try:
            driver.set_page_load_timeout(30)
            driver.set_context("chrome")
            selected = driver.execute_script("""
                const {writeNetworkProfile}=ChromeUtils.importESModule(
                    'resource:///modules/CloakfoxNetworkProfiles.sys.mjs');
                Services.prefs.setBoolPref('cloakfox.enabled',true);
                Services.prefs.setStringPref('cloakfox.s.cloak_cfg_0',
                    JSON.stringify({'navigator.userAgent':arguments[0]}));
                Services.prefs.setBoolPref('cloakfox.container.0.network_follow_identity',true);
                const selected=writeNetworkProfile(0);
                Cc['@mozilla.org/security/x509certdb;1'].getService(Ci.nsIX509CertDB)
                    .addCertFromBase64(arguments[1],'CT,,');
                return {...selected, atomicState:Services.prefs.getIntPref(
                    'cloakfox.container.0.network_state')};
            """, UA[profile], base64.b64encode(ssl.PEM_cert_to_DER_cert(certificate.read_text())).decode())
            expected = "chrome" if profile == "chrome" else "firefox"
            assert selected["family"] == expected, selected
            assert selected["profileId"] == (1 if profile == "chrome" else 0), selected
            assert selected["atomicState"] & 1 == selected["profileId"], selected
            assert selected["unsupported"] == (profile == "safari"), selected
            if not enabled:
                # Keep a valid Chrome selection after disabling. This tests the
                # native/socket gate even when stale adapter state is present.
                driver.execute_script("""
                    Services.prefs.setBoolPref('cloakfox.enabled',false);
                    Services.prefs.setIntPref('cloakfox.container.0.network_state',arguments[0]);
                """, selected["atomicState"])
            observed_state = driver.execute_script("""
                return {enabled:Services.prefs.getBoolPref('cloakfox.enabled'),
                        atomicState:Services.prefs.getIntPref('cloakfox.container.0.network_state')};
            """)
            assert observed_state["enabled"] == enabled, observed_state
            assert observed_state["atomicState"] == selected["atomicState"], observed_state
            driver.set_context("content")
            start = len(fixture.observed)
            driver.get(f"https://h2-profile.test:{fixture.server_address[1]}/profile")
            assert "local-wire-ok" in driver.page_source
            observations = [value for value in fixture.observed[start:]
                            if value.get("pseudoHeaders")]
            assert observations, fixture.observed[start:]
            wire = observations[0]
            assert wire["protocol"] == "h2" and wire["tlsVersion"] == "TLSv1.3", wire
            driver.set_context("chrome")
            after_request = driver.execute_script("""
                return {enabled:Services.prefs.getBoolPref('cloakfox.enabled'),
                        atomicState:Services.prefs.getIntPref('cloakfox.container.0.network_state')};
            """)
            assert after_request == observed_state, after_request
            driver.set_context("content")
            result = {"selection": selected, "wire": wire,
                      "stateAfterRequest": after_request,
                      "browserVersion": driver.capabilities["browserVersion"],
                      "observedState": observed_state,
                      "navigator": driver.execute_script("return [navigator.platform,navigator.oscpu,navigator.userAgent,navigator.hardwareConcurrency]") }
            (log_dir / f"{profile}.json").write_text(json.dumps(result, indent=2))
            return result
        finally:
            driver.quit()


@pytest.fixture(scope="session")
def probe_results():
    if not CLOAKFOX_BIN or not os.path.exists(CLOAKFOX_BIN):
        pytest.skip("CLOAKFOX_BIN env var not set or binary missing")
    log_dir = Path(os.environ.get("H2_REPORT_DIR", ROOT / "tests/fingerprint/reports/158-port/h2"))
    log_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cloakfox-h2-certs-", dir="/tmp") as tmp:
        ca, cert, key = create_certificates(Path(tmp), ["h2-profile.test"])
        fixture = TLSFixture(cert, key)
        try:
            return {profile: _probe(CLOAKFOX_BIN, profile, log_dir, ca, fixture)
                    for profile in ("firefox", "chrome", "safari")}
        finally:
            fixture.close()


@pytest.mark.parametrize("profile", ["firefox", "chrome"])
def test_h2_profile_shape(probe_results, profile):
    """Both supported adapters match independently captured SETTINGS/WU/HPACK."""
    assert _shape(probe_results[profile]["wire"]) == _shape(_pinned_shapes()[profile])


def test_h2_profiles_produce_distinct_fingerprints(probe_results):
    """Supported adapters have distinct structural fingerprints on the wire."""
    hashes = {profile: hashlib.sha256(json.dumps(_shape(probe_results[profile]["wire"]),
                                               sort_keys=True).encode()).hexdigest()
              for profile in ("firefox", "chrome")}
    assert len(set(hashes.values())) == 2, hashes


def test_unsupported_safari_retains_native_networking(probe_results):
    """Unsupported Safari intent reports status and preserves complete native H2."""
    safari = probe_results["safari"]
    assert safari["selection"]["unsupported"] is True
    assert safari["selection"]["family"] == "firefox"
    assert safari["selection"]["profileId"] == 0
    assert _shape(safari["wire"]) == _shape(_pinned_shapes()["firefox"])
    assert _shape(safari["wire"]) == _shape(probe_results["firefox"]["wire"])
