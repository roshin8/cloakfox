"""
Sec-CH-UA header emission test.

The header-spoofer.ts webRequest listener injects Sec-CH-UA,
Sec-CH-UA-Mobile, and Sec-CH-UA-Platform headers on every request
when the container's active profile carries Chromium `brands` data
(Firefox/Safari UA profiles don't set brands, so no CH headers are
sent for them — that's the coherent behavior).

Known cold-start behavior: the FIRST navigation in a session can't
have CH headers because the inject script hasn't posted the active
profile to background yet, so webRequest has nothing to read from
storage.local. From the second navigation onward the profile is
cached and CH headers fire. The test warms up before asserting.

Run:

    CLOAKFOX_BIN=/Applications/Cloakfox.app/Contents/MacOS/cloakfox \\
        pytest tests/fingerprint/test_sec_ch_ua.py -v
"""

import json
import os
import time

import pytest
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

CLOAKFOX_BIN = os.environ.get("CLOAKFOX_BIN")


def _build_driver(log_dir: str):
    opts = Options()
    opts.binary_location = CLOAKFOX_BIN
    opts.add_argument("--headless")
    opts.set_preference("devtools.jsonview.enabled", False)
    os.makedirs(log_dir, exist_ok=True)
    svc = Service(log_path=f"{log_dir}/geckodriver.log")
    return webdriver.Firefox(options=opts, service=svc)


def _fetch_headers(driver, url="https://httpbin.org/headers") -> dict:
    driver.get(url)
    time.sleep(1.0)
    body = driver.execute_script("return document.body.innerText")
    return json.loads(body.strip())["headers"]


def _warmup(driver) -> None:
    """First navigation in a session primes the activeProfile storage."""
    driver.get("https://httpbin.org/headers")
    time.sleep(2.5)  # give inject → content → background → storage roundtrip time


@pytest.mark.skipif(
    not CLOAKFOX_BIN or not os.path.exists(CLOAKFOX_BIN),
    reason="CLOAKFOX_BIN env var not set or binary missing",
)
def test_sec_ch_ua_present_with_chromium_profile(tmp_path):
    """When the extension assigns a Chromium profile, Sec-CH-UA* are injected."""
    driver = _build_driver(str(tmp_path))
    try:
        _warmup(driver)
        headers = _fetch_headers(driver)
        ua = headers.get("User-Agent", "")
        is_chromium = "Chrome/" in ua and "Firefox/" not in ua
        if not is_chromium:
            pytest.skip(
                f"Extension assigned a non-Chromium profile (UA={ua!r}); "
                "Sec-CH-UA injection only applies to Chromium UAs. Retry to "
                "hit a Chromium profile, or force one via settings."
            )
        assert "Sec-Ch-Ua" in headers, (
            f"Chromium UA but no Sec-CH-UA header. Headers: {list(headers.keys())}"
        )
        assert "Sec-Ch-Ua-Mobile" in headers, "missing Sec-CH-UA-Mobile"
        assert "Sec-Ch-Ua-Platform" in headers, "missing Sec-CH-UA-Platform"
        # Sec-CH-UA value format: "Brand";v="version", "Brand2";v="v2"
        sec_ua = headers["Sec-Ch-Ua"]
        assert '";v="' in sec_ua, (
            f"Sec-CH-UA format unexpected: {sec_ua!r}"
        )
    finally:
        driver.quit()


@pytest.mark.skipif(
    not CLOAKFOX_BIN or not os.path.exists(CLOAKFOX_BIN),
    reason="CLOAKFOX_BIN env var not set or binary missing",
)
def test_sec_ch_ua_absent_with_firefox_or_safari_profile(tmp_path):
    """Non-Chromium profiles must NOT send Sec-CH-UA — otherwise the UA lies."""
    driver = _build_driver(str(tmp_path))
    try:
        _warmup(driver)
        headers = _fetch_headers(driver)
        ua = headers.get("User-Agent", "")
        is_chromium = "Chrome/" in ua and "Firefox/" not in ua
        if is_chromium:
            pytest.skip(
                f"Extension assigned a Chromium profile (UA={ua!r}); "
                "this test needs a Firefox or Safari profile. Retry."
            )
        for h in ("Sec-Ch-Ua", "Sec-Ch-Ua-Mobile", "Sec-Ch-Ua-Platform"):
            assert h not in headers, (
                f"Non-Chromium UA ({ua!r}) but {h} present ({headers[h]!r}) — "
                "fingerprint mismatch"
            )
    finally:
        driver.quit()


@pytest.mark.skipif(
    not CLOAKFOX_BIN or not os.path.exists(CLOAKFOX_BIN),
    reason="CLOAKFOX_BIN env var not set or binary missing",
)
def test_user_agent_header_matches_spoofed_profile(tmp_path):
    """The HTTP User-Agent header reflects the extension's assigned UA
    (not the native Cloakfox UA) after warmup."""
    driver = _build_driver(str(tmp_path))
    try:
        _warmup(driver)
        headers = _fetch_headers(driver)
        ua = headers.get("User-Agent", "")
        assert "Cloakfox/" not in ua, (
            f"User-Agent leaked the native Cloakfox identifier: {ua!r} — "
            "header-spoofer didn't replace the UA"
        )
    finally:
        driver.quit()
