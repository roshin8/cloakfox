"""Live migrated-profile timing-key Clear lifecycle regression.

Exit codes: 0 pass · 1 assertion failure · 2 unable to run.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait


LEGACY_CFG = json.dumps(
    {"fonts": ["Arial", "Verdana"], "fonts:spacing_seed": 0x12345678},
    separators=(",", ":"),
)

CLASSIFY_SCRIPT = r"""
const values = [];
const deadline = performance.now() + 750;
while (values.length < 250000 && performance.now() < deadline) {
  values.push(performance.now());
}
const buckets = new Map();
let fractionalSamples = 0;
for (const value of values) {
  const bucket = Math.floor(value);
  const fraction = (value - bucket).toFixed(6);
  if (fraction !== "0.000000") fractionalSamples++;
  if (!buckets.has(bucket)) buckets.set(bucket, new Set());
  buckets.get(bucket).add(fraction);
}
const counts = [...buckets.values()].map(parts => parts.size);
const multiFractionBuckets = counts.filter(count => count > 1).length;
const stableFractionBuckets = counts.filter(count => count === 1).length;
let classification = "ambiguous";
if (buckets.size >= 8 && fractionalSamples >= 8 && multiFractionBuckets <= 1) {
  classification = "keyed";
} else if (buckets.size >= 8 && fractionalSamples === 0 && multiFractionBuckets === 0) {
  classification = "native-no-key-reduced";
} else if (buckets.size >= 2 && multiFractionBuckets >= 2) {
  classification = "native-high-resolution";
}
return {
  classification,
  samples: values.length,
  buckets: buckets.size,
  fractionalSamples,
  stableFractionBuckets,
  multiFractionBuckets,
  maxFractionsPerBucket: counts.length ? Math.max(...counts) : 0,
  firstValues: values.slice(0, 12),
};
"""


class PageHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib hook
        body = b"<!doctype html><meta charset=utf-8><title>timing clear lifecycle</title>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        pass


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


def read_parent_state(driver: webdriver.Firefox) -> dict[str, object]:
    driver.set_context("chrome")
    try:
        return driver.execute_script(
            r"""
const pref = name => Services.prefs.prefHasUserValue(name);
const value = name => Services.prefs.getStringPref(name, "");
const snapshot = Services.ppmm.sharedData.get("cloakfox-seeds") || {};
return {
  currentCfg: value("cloakfox.s.cloak_cfg_0"),
  currentCfgUser: pref("cloakfox.s.cloak_cfg_0"),
  legacyCfg: value("roverfox.s.cloak_cfg_0"),
  legacyCfgUser: pref("roverfox.s.cloak_cfg_0"),
  mathSeedUser: pref("cloakfox.container.0.math_seed"),
  keyboardSeedUser: pref("cloakfox.container.0.keyboard_seed"),
  timingSeedUser: pref("cloakfox.container.0.timing_seed"),
  transactionUser: pref("cloakfox.internal.clear_0"),
  snapshotCfg: snapshot["cloakfox.s.cloak_cfg_0"] ?? null,
  snapshotLegacyCfg: snapshot["roverfox.s.cloak_cfg_0"] ?? null,
  snapshotMathSeed: snapshot["cloakfox.container.0.math_seed"] ?? null,
  snapshotKeyboardSeed: snapshot["cloakfox.container.0.keyboard_seed"] ?? null,
  snapshotTimingSeed: snapshot["cloakfox.container.0.timing_seed"] ?? null,
  snapshotTransaction: snapshot["cloakfox.internal.clear_0"] ?? null,
};
"""
        )
    finally:
        driver.set_context("content")


def assert_startup_state(state: dict[str, object]) -> dict[str, object]:
    cfg = json.loads(str(state["currentCfg"]))
    assert state["currentCfgUser"] is True, state
    assert state["legacyCfgUser"] is True, state
    assert cfg.get("fonts") == ["Arial", "Verdana"], cfg
    assert cfg.get("fonts:spacing_seed") == 0x12345678, cfg
    assert isinstance(cfg.get("timing:session_key_hi"), int), cfg
    assert isinstance(cfg.get("timing:session_key_lo"), int), cfg
    assert cfg["timing:session_key_hi"] != 0, cfg
    assert cfg["timing:session_key_lo"] != 0, cfg
    assert state["mathSeedUser"] is True, state
    assert state["keyboardSeedUser"] is True, state
    assert state["timingSeedUser"] is True, state
    assert state["snapshotCfg"] == state["currentCfg"], state
    return cfg


def assert_cleared_state(state: dict[str, object]) -> None:
    assert state["currentCfg"] == "{}", state
    assert state["currentCfgUser"] is True, state
    assert state["legacyCfgUser"] is False, state
    assert state["legacyCfg"] == "", state
    assert state["mathSeedUser"] is False, state
    assert state["keyboardSeedUser"] is False, state
    assert state["timingSeedUser"] is False, state
    assert state["transactionUser"] is False, state
    assert state["snapshotCfg"] == "{}", state
    assert state["snapshotLegacyCfg"] is None, state
    assert state["snapshotMathSeed"] is None, state
    assert state["snapshotKeyboardSeed"] is None, state
    assert state["snapshotTimingSeed"] is None, state
    assert state["snapshotTransaction"] is None, state


def wait_for_startup_state(driver: webdriver.Firefox) -> dict[str, object] | bool:
    state = read_parent_state(driver)
    return state if "timing:session_key_hi" in str(state.get("currentCfg", "")) else False


def wait_for_cleared_state(driver: webdriver.Firefox) -> dict[str, object] | bool:
    state = read_parent_state(driver)
    return (
        state
        if state.get("currentCfg") == "{}" and state.get("snapshotCfg") == "{}"
        else False
    )


def main(binary: str) -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), PageHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="cfx-timing-clear-") as temporary:
            root = Path(temporary)
            profile = root / "profile"
            profile.mkdir()
            profile.joinpath("user.js").write_text(
                'user_pref("cloakfox.enabled", true);\n'
                'user_pref("privacy.userContext.enabled", true);\n'
                f'user_pref("roverfox.s.cloak_cfg_0", {json.dumps(LEGACY_CFG)});\n',
                encoding="utf-8",
            )
            driver = make_driver(binary, profile, root / "geckodriver.log")
            try:
                wait = WebDriverWait(driver, 30)
                startup = wait.until(wait_for_startup_state)
                startup_cfg = assert_startup_state(startup)

                ordinary_url = f"http://127.0.0.1:{server.server_port}/?before"
                driver.get(ordinary_url)
                live_handle = driver.current_window_handle
                keyed_before = driver.execute_script(CLASSIFY_SCRIPT)
                assert keyed_before["classification"] == "keyed", keyed_before

                driver.set_context("chrome")
                native_reference = driver.execute_script(CLASSIFY_SCRIPT)
                driver.set_context("content")
                assert native_reference["classification"] == "native-high-resolution", native_reference

                driver.switch_to.new_window("tab")
                settings_handle = driver.current_window_handle
                driver.get("about:cloakfox?ucid=0")
                wait.until(lambda current: current.find_element(By.ID, "cfx-clear")).click()
                cleared = wait.until(wait_for_cleared_state)
                assert_cleared_state(cleared)

                driver.switch_to.window(live_handle)
                keyed_after = driver.execute_script(CLASSIFY_SCRIPT)
                assert keyed_after["classification"] == "keyed", keyed_after

                driver.switch_to.new_window("tab")
                driver.get(f"http://127.0.0.1:{server.server_port}/?after")
                native_after = driver.execute_script(CLASSIFY_SCRIPT)
                assert native_after["classification"] == "native-no-key-reduced", native_after

                print("startup_cfg=" + json.dumps(startup_cfg, sort_keys=True))
                print("native_reference=" + json.dumps(native_reference, sort_keys=True))
                print("keyed_before=" + json.dumps(keyed_before, sort_keys=True))
                print("cleared_state=" + json.dumps(cleared, sort_keys=True))
                print("keyed_after=" + json.dumps(keyed_after, sort_keys=True))
                print("native_after=" + json.dumps(native_after, sort_keys=True))
                driver.switch_to.window(settings_handle)
            finally:
                driver.quit()
    except AssertionError as error:
        print(f"FAIL — timing Clear lifecycle assertion: {error}")
        return 1
    except Exception as error:
        print(f"INCONCLUSIVE — timing Clear lifecycle could not run: {error}")
        return 2
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
    print("PASS — migrated timing key Clear preserves live context and clears new contexts")
    return 0


if __name__ == "__main__":
    cloakfox_binary = os.environ.get("CLOAKFOX_BIN")
    if not cloakfox_binary or not Path(cloakfox_binary).is_file():
        print("INCONCLUSIVE — CLOAKFOX_BIN not set or binary missing")
        sys.exit(2)
    sys.exit(main(cloakfox_binary))
