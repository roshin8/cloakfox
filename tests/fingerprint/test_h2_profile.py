"""
H2 fingerprint profile E2E test (Selenium + geckodriver).

Why not Playwright: Playwright's Firefox driver speaks Juggler, which
requires a Juggler-patched Firefox binary (Playwright ships one). Cloakfox
is stock-patched Firefox, so Playwright cannot drive it. geckodriver speaks
Marionette, which every Firefox build supports by default.

Launches the built Cloakfox binary under each value of
`network.http.http2.fingerprint_profile` (firefox, chrome, safari),
visits tls.peet.ws/api/all, and asserts:

1. The three profiles produce three DIFFERENT akamai_fingerprint_hash values.
2. Each profile's SETTINGS frame, WINDOW_UPDATE value, and HPACK pseudo-header
   order match the contract documented in patches/http2-fingerprint-spoofing.patch.

Prerequisites:

    pip install pytest selenium
    brew install geckodriver   # or download from GitHub releases on Linux/Windows

Run:

    CLOAKFOX_BIN=/Applications/Cloakfox.app/Contents/MacOS/cloakfox \\
        pytest tests/fingerprint/test_h2_profile.py -v

Skips cleanly if CLOAKFOX_BIN is unset.
"""

import json
import os
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

CLOAKFOX_BIN = os.environ.get("CLOAKFOX_BIN")
PROBE_URL = "https://tls.peet.ws/api/all"

# Expected H2 signature per profile. These must line up with what
# patches/http2-fingerprint-spoofing.patch emits — a regression here
# means the patch didn't fire or cloakfox.cfg clobbered the pref.
PROFILE_EXPECTATIONS = {
    "firefox": {
        "settings_ids": {1, 2, 4, 5},           # HEADER_TABLE, PUSH, INITIAL_WINDOW, MAX_FRAME
        "window_update": None,                  # variable, session-dependent
        "pseudo_order": [":method", ":path", ":authority", ":scheme"],
    },
    "chrome": {
        "settings_ids": {1, 2, 3, 4, 6},        # + MAX_CONCURRENT, MAX_HEADER_LIST; no MAX_FRAME
        "settings_values": {3: 1000, 4: 6291456, 6: 262144},
        "window_update": 15663105,
        "pseudo_order": [":method", ":authority", ":scheme", ":path"],
    },
    "safari": {
        "settings_ids": {2, 3, 4},              # sparse
        "settings_values": {3: 100, 4: 2097152},
        "window_update": 10485760,
        "pseudo_order": [":method", ":scheme", ":path", ":authority"],
    },
}


def _probe(bin_path: str, profile: str, log_dir: Path) -> dict:
    """Launch Cloakfox with the given profile, return parsed peetwapp JSON."""
    opts = Options()
    opts.binary_location = bin_path
    opts.add_argument("--headless")
    opts.set_preference("network.http.http2.fingerprint_profile", profile)
    opts.set_preference("browser.shell.checkDefaultBrowser", False)
    opts.set_preference("browser.startup.page", 0)
    opts.set_preference("devtools.jsonview.enabled", False)  # want raw JSON, not viewer

    svc = Service(log_path=str(log_dir / f"gd-{profile}.log"))
    driver = webdriver.Firefox(options=opts, service=svc)
    try:
        driver.set_page_load_timeout(30)
        driver.get(PROBE_URL)
        body = driver.execute_script(
            "return document.body.innerText || document.body.textContent"
        )
        return json.loads(body.strip())
    finally:
        driver.quit()


def _parse_settings(frame: dict) -> dict:
    """Convert peetwapp SETTINGS frame ('MAX_HEADER_LIST_SIZE = 262144') to id->value dict."""
    SETTING_NAME_TO_ID = {
        "HEADER_TABLE_SIZE": 1, "ENABLE_PUSH": 2, "MAX_CONCURRENT_STREAMS": 3,
        "INITIAL_WINDOW_SIZE": 4, "MAX_FRAME_SIZE": 5, "MAX_HEADER_LIST_SIZE": 6,
    }
    out = {}
    for entry in frame.get("settings", []):
        name, _, value = entry.partition(" = ")
        sid = SETTING_NAME_TO_ID.get(name.strip())
        if sid is not None:
            out[sid] = int(value.strip())
    return out


def _assert_shape(profile: str, payload: dict) -> None:
    expect = PROFILE_EXPECTATIONS[profile]
    sent = payload.get("http2", {}).get("sent_frames", [])
    assert sent, f"[{profile}] peetwapp returned no sent_frames"

    settings_frame = next((f for f in sent if f.get("frame_type") == "SETTINGS"), None)
    assert settings_frame, f"[{profile}] no SETTINGS frame"
    settings = _parse_settings(settings_frame)
    assert set(settings.keys()) == expect["settings_ids"], (
        f"[{profile}] SETTINGS ids {set(settings.keys())}, expected {expect['settings_ids']}"
    )
    for sid, value in expect.get("settings_values", {}).items():
        assert settings.get(sid) == value, (
            f"[{profile}] SETTINGS[{sid}]={settings.get(sid)}, expected {value}"
        )

    window_frame = next((f for f in sent if f.get("frame_type") == "WINDOW_UPDATE"), None)
    if expect["window_update"] is not None:
        assert window_frame and window_frame.get("increment") == expect["window_update"], (
            f"[{profile}] WINDOW_UPDATE={window_frame.get('increment') if window_frame else 'none'}, "
            f"expected {expect['window_update']}"
        )

    headers_frame = next((f for f in sent if f.get("frame_type") == "HEADERS"), None)
    assert headers_frame, f"[{profile}] no HEADERS frame"
    pseudos = [h.split(":")[1] and ":" + h.split(":")[1].strip()
               for h in headers_frame.get("headers", []) if h.startswith(":")][:4]
    # peetwapp strings look like ":method: GET" — extract just ":method"
    pseudos = [h.split(":")[1].strip() and ":" + h.split(":")[1].strip()
               for h in headers_frame.get("headers", []) if h.startswith(":")][:4]
    # Simpler: take the first token before the second colon.
    pseudos = []
    for h in headers_frame.get("headers", []):
        if not h.startswith(":"):
            continue
        name = h.split(":", 2)
        if len(name) >= 2:
            pseudos.append(":" + name[1])
        if len(pseudos) == 4:
            break
    assert pseudos == expect["pseudo_order"], (
        f"[{profile}] HPACK pseudo order {pseudos}, expected {expect['pseudo_order']}"
    )


@pytest.fixture(scope="session")
def probe_results(tmp_path_factory) -> dict:
    """Run peetwapp probe once per profile per session; share across tests."""
    if not CLOAKFOX_BIN or not os.path.exists(CLOAKFOX_BIN):
        pytest.skip("CLOAKFOX_BIN env var not set or binary missing")
    log_dir = tmp_path_factory.mktemp("fingerprint-logs")
    return {p: _probe(CLOAKFOX_BIN, p, log_dir) for p in ["firefox", "chrome", "safari"]}


@pytest.mark.parametrize("profile", ["firefox", "chrome", "safari"])
def test_h2_profile_shape(probe_results: dict, profile: str) -> None:
    """Each profile emits the H2 signature documented in the patch."""
    _assert_shape(profile, probe_results[profile])


def test_h2_profiles_produce_distinct_fingerprints(probe_results: dict) -> None:
    """All three profiles must produce distinct akamai_fingerprint_hash values."""
    hashes = {}
    for profile, payload in probe_results.items():
        h = payload.get("http2", {}).get("akamai_fingerprint_hash") or payload.get(
            "akamai_fingerprint_hash"
        )
        assert h, f"[{profile}] no akamai_fingerprint_hash in response"
        hashes[profile] = h
    assert len(set(hashes.values())) == 3, (
        f"Profiles produced collapsing hashes: {hashes} — "
        "either the pref isn't being read or cloakfox.cfg is clobbering user prefs"
    )
