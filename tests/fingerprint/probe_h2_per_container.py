"""Verify supported H2 adapters stay scoped to two live containers.

One browser session loads the same trusted loopback origin from Firefox and
Chrome 155 containers. Production writeNetworkProfile commits each owner's
atomic state; ordered wire shapes match independently captured references.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import ssl
import tempfile

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait

from test_h2_profile import UA, _pinned_shapes, _shape
from h3_fixture import create_certificates
from wire_fixture import TLSFixture

CONTAINERS = {1: "firefox", 2: "chrome"}


def _wire_in_container(driver, ucid, address, fixture):
    before = set(driver.window_handles)
    driver.set_context("chrome")
    try:
        owner = driver.execute_script("""
          const tab=gBrowser.addTab('about:blank',{userContextId:arguments[0],
            triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});
          gBrowser.selectedTab=tab;
          return tab.linkedBrowser.browsingContext.originAttributes.userContextId;
        """, ucid)
        assert owner == ucid, (owner, ucid)
    finally:
        driver.set_context("content")
    WebDriverWait(driver, 15).until(lambda d: set(d.window_handles) - before)
    driver.switch_to.window((set(driver.window_handles) - before).pop())
    WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
    start = len(fixture.observed)
    # A content-initiated top-level navigation preserves the container owner.
    driver.execute_script("window.location.href=arguments[0]", address)
    WebDriverWait(driver, 30).until(lambda d: d.current_url == address and
                                  "local-wire-ok" in d.page_source)
    records = [entry for entry in fixture.observed[start:] if entry.get("pseudoHeaders")]
    assert records, fixture.observed[start:]
    wire = records[0]
    assert wire["protocol"] == "h2" and wire["tlsVersion"] == "TLSv1.3", wire
    return wire


def main():
    binary = os.environ["CLOAKFOX_BIN"]
    report_dir = Path(os.environ.get("REPORT_DIR", Path(__file__).parent / "reports/157-privacy-port/h2/per-container"))
    report_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cloakfox-h2-containers-", dir="/tmp") as tmp:
        root = Path(tmp)
        ca, cert, key = create_certificates(root, ["h2-container.test"])
        fixture = TLSFixture(cert, key)
        options = Options()
        options.binary_location = binary
        options.accept_insecure_certs = False
        options.add_argument("-headless")
        options.add_argument("-purgecaches")
        profile = root / "profile"
        profile.mkdir()
        options.add_argument("-profile")
        options.add_argument(str(profile))
        options.set_preference("privacy.userContext.enabled", True)
        options.set_preference("network.dns.localDomains", "h2-container.test")
        options.set_preference("network.trr.mode", 5)
        options.set_preference("network.http.http2.fingerprint_profile", "safari")
        driver = None
        results = {}
        try:
            driver = webdriver.Firefox(options=options, service=Service(
                service_args=["--allow-system-access"], log_output=str(report_dir / "geckodriver.log")))
            driver.set_context("chrome")
            selections = driver.execute_script("""
              const {writeNetworkProfile}=ChromeUtils.importESModule(
                'resource:///modules/CloakfoxNetworkProfiles.sys.mjs');
              Services.prefs.setBoolPref('cloakfox.enabled',true);
              const results={};
              for(const [ucid,ua] of Object.entries(arguments[0])) {
                Services.prefs.setStringPref('cloakfox.s.cloak_cfg_'+ucid,
                  JSON.stringify({'navigator.userAgent':ua}));
                Services.prefs.setBoolPref('cloakfox.container.'+ucid+'.network_follow_identity',true);
                const selected=writeNetworkProfile(Number(ucid));
                results[ucid]={...selected,atomicState:Services.prefs.getIntPref(
                  'cloakfox.container.'+ucid+'.network_state')};
              }
              Cc['@mozilla.org/security/x509certdb;1'].getService(Ci.nsIX509CertDB)
                .addCertFromBase64(arguments[1],'CT,,');
              return results;
            """, {str(ucid): UA[family] for ucid, family in CONTAINERS.items()},
                base64.b64encode(ssl.PEM_cert_to_DER_cert(ca.read_text())).decode())
            driver.set_context("content")
            references = _pinned_shapes()
            for ucid, family in CONTAINERS.items():
                selection = selections[str(ucid)]
                expected_id = 1 if family == "chrome" else 0
                assert selection["profileId"] == expected_id and selection["family"] == family, selection
                assert not selection["unsupported"] and selection["atomicState"] & 1 == expected_id, selection
                address = f"https://h2-container.test:{fixture.server_address[1]}/container/{ucid}"
                wire = _wire_in_container(driver, ucid, address, fixture)
                shape = _shape(wire)
                assert shape == _shape(references[family]), (ucid, family, shape)
                results[str(ucid)] = {"selection": selection, "wire": wire,
                    "fingerprint": hashlib.sha256(json.dumps(shape, sort_keys=True).encode()).hexdigest()}
            assert len({entry["fingerprint"] for entry in results.values()}) == len(CONTAINERS), results
            (report_dir / "results.json").write_text(json.dumps(results, indent=2))
            print("PASS: same-session Firefox/Chrome155 container wire shapes match pinned captures and remain distinct")
        finally:
            if driver: driver.quit()
            fixture.close()


if __name__ == "__main__":
    main()
