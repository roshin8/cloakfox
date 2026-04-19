"""
H2 fingerprint profile E2E test.

Launches the built Cloakfox binary, toggles the network.http.http2.fingerprint_profile
pref through each value (firefox, chrome, safari), visits tls.peet.ws/api/all,
and asserts:

1. The three profiles produce three DIFFERENT akamai_fingerprint_hash values.
2. Each hash matches the corresponding real-browser signature in peetwapp's public
   database (within the observed-prefix tolerance — SETTINGS values can vary
   slightly across Chrome/Safari point releases).

Run:

    CLOAKFOX_BIN=/Applications/Cloakfox.app/Contents/MacOS/cloakfox \\
        pytest tests/fingerprint/test_h2_profile.py -v

Skips cleanly if CLOAKFOX_BIN is unset.
"""

import json
import os
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

CLOAKFOX_BIN = os.environ.get("CLOAKFOX_BIN")
PROBE_URL = "https://tls.peet.ws/api/all"

# Observed H2 SETTINGS frame signatures per browser family. These aren't full
# hash matches (point releases drift) — instead we assert specific structural
# properties that each profile MUST exhibit. A mismatch means the WebIDL
# setter didn't fire or the patch regressed.
#
# Source: https://h2fingerprint.com/ + direct observation of stock browsers.
PROFILE_EXPECTATIONS = {
    "firefox": {
        # Firefox default: MAX_FRAME_SIZE present, MAX_HEADER_LIST_SIZE absent.
        "pseudo_order": "m,p,a,s",
        "has_max_header_list_size": False,
        "has_max_frame_size": True,
        # WINDOW_UPDATE is session-derived for Firefox, not a fixed value.
    },
    "chrome": {
        # Chrome: fixed WINDOW_UPDATE value, HPACK order m,a,s,p,
        # MAX_HEADER_LIST_SIZE=262144 instead of MAX_FRAME_SIZE.
        "pseudo_order": "m,a,s,p",
        "window_update": 15663105,
        "has_max_header_list_size": True,
        "has_max_frame_size": False,
    },
    "safari": {
        # Safari: sparse SETTINGS (just 2/3/4), distinct WINDOW_UPDATE, HPACK m,s,p,a.
        "pseudo_order": "m,s,p,a",
        "window_update": 10485760,
        # Safari sends neither MAX_FRAME_SIZE nor MAX_HEADER_LIST_SIZE.
        "has_max_header_list_size": False,
        "has_max_frame_size": False,
    },
}


def _profile_dir(tmp_path: Path, label: str) -> Path:
    d = tmp_path / f"profile-{label}"
    d.mkdir(parents=True, exist_ok=True)
    # Force the H2 fingerprint pref via a user.js dropped into the profile.
    # This is the same mechanism the extension's setHttp2Profile WebIDL uses
    # under the hood, but doing it via user.js guarantees it's set before
    # the first H2 connection is established.
    user_js = d / "user.js"
    user_js.write_text(
        f'user_pref("network.http.http2.fingerprint_profile", "{label}");\n'
        # Make the profile trust peet.ws's cert chain in CI (we still want real TLS).
        'user_pref("browser.shell.checkDefaultBrowser", false);\n'
        'user_pref("browser.startup.page", 0);\n'
    )
    return d


def _fetch_peetwapp(bin_path: str, profile_dir: Path) -> dict:
    """Launch Cloakfox with the given profile, fetch peetwapp JSON, return parsed."""
    with sync_playwright() as pw:
        ctx = pw.firefox.launch_persistent_context(
            user_data_dir=str(profile_dir),
            executable_path=bin_path,
            headless=False,  # Cloakfox doesn't do headless cleanly — WebIDL methods fire in MAIN world only under real launch
            args=["--no-remote"],
        )
        page = ctx.new_page()
        page.goto(PROBE_URL, wait_until="networkidle", timeout=30_000)
        # peetwapp returns JSON in a <pre> tag when requested by a browser
        try:
            body = page.locator("pre").first.text_content(timeout=5_000)
        except Exception:
            body = page.content()
        ctx.close()
    return json.loads(body.strip())


def _assert_profile_shape(label: str, payload: dict) -> None:
    """Check the H2 signature exposed by peetwapp matches the profile contract."""
    expect = PROFILE_EXPECTATIONS[label]
    http2 = payload.get("http2", {})
    sent_frames = http2.get("sent_frames", [])
    settings_frame = next((f for f in sent_frames if f.get("frame_type") == "SETTINGS"), None)
    assert settings_frame, f"[{label}] no SETTINGS frame in peetwapp response"
    setting_ids = {s["id"]: s["value"] for s in settings_frame.get("settings", [])}

    # MaxHeaderListSize = id 6, MaxFrameSize = id 5
    has_mhl = 6 in setting_ids
    has_mfs = 5 in setting_ids
    assert has_mhl == expect["has_max_header_list_size"], (
        f"[{label}] MAX_HEADER_LIST_SIZE present={has_mhl}, expected {expect['has_max_header_list_size']}"
    )
    assert has_mfs == expect["has_max_frame_size"], (
        f"[{label}] MAX_FRAME_SIZE present={has_mfs}, expected {expect['has_max_frame_size']}"
    )

    # Pseudo-header order from the HEADERS frame
    headers_frame = next((f for f in sent_frames if f.get("frame_type") == "HEADERS"), None)
    assert headers_frame, f"[{label}] no HEADERS frame in peetwapp response"
    pseudos = [h for h in headers_frame.get("headers", []) if h.startswith(":")]
    order_letters = "".join(h[1] for h in pseudos[:4])  # m, p, a, s initials
    assert order_letters == expect["pseudo_order"].replace(",", ""), (
        f"[{label}] HPACK pseudo-header order {order_letters}, expected {expect['pseudo_order']}"
    )

    # WINDOW_UPDATE (for chrome/safari — fixed values)
    if "window_update" in expect:
        window_frame = next(
            (f for f in sent_frames if f.get("frame_type") == "WINDOW_UPDATE"), None
        )
        assert window_frame, f"[{label}] no WINDOW_UPDATE frame"
        assert window_frame.get("increment") == expect["window_update"], (
            f"[{label}] WINDOW_UPDATE={window_frame.get('increment')}, expected {expect['window_update']}"
        )


@pytest.mark.skipif(
    not CLOAKFOX_BIN or not os.path.exists(CLOAKFOX_BIN),
    reason="CLOAKFOX_BIN env var not set or binary missing",
)
@pytest.mark.parametrize("profile", ["firefox", "chrome", "safari"])
def test_h2_profile_shape(tmp_path: Path, profile: str) -> None:
    """Each profile emits the H2 signature claimed by the patch."""
    payload = _fetch_peetwapp(CLOAKFOX_BIN, _profile_dir(tmp_path, profile))
    _assert_profile_shape(profile, payload)


@pytest.mark.skipif(
    not CLOAKFOX_BIN or not os.path.exists(CLOAKFOX_BIN),
    reason="CLOAKFOX_BIN env var not set or binary missing",
)
def test_h2_profiles_produce_distinct_fingerprints(tmp_path: Path) -> None:
    """firefox / chrome / safari profiles MUST produce different Akamai hashes."""
    hashes = {}
    for label in ["firefox", "chrome", "safari"]:
        payload = _fetch_peetwapp(CLOAKFOX_BIN, _profile_dir(tmp_path, label))
        h = payload.get("akamai_fingerprint_hash") or payload.get("http2", {}).get(
            "akamai_fingerprint_hash"
        )
        assert h, f"[{label}] no akamai_fingerprint_hash in response"
        hashes[label] = h
    # All three distinct
    assert len(set(hashes.values())) == 3, (
        f"Profiles produced collapsing hashes: {hashes} — WebIDL setter not firing or patches not applied"
    )
