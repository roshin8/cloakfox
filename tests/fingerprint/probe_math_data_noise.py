"""Check optional data-math noise in real page and worker realms.

Disposable profiles cover the shipped default, explicit off/on, and master
disabled with the option on. No current browser profile or call is changed.
"""
import json
import os
from pathlib import Path
import tempfile

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By

from probe_workers import _build_driver, loopback_probe




def observe(driver, address):
    driver.get(address)
    WebDriverWait(driver, 10).until(lambda d: d.title == "PROBE_DONE")
    return json.loads(driver.find_element(
        "css selector", "html").get_attribute("data-cfx-probe"))


def main():
    binary = os.environ["CLOAKFOX_BIN"]
    observations = {}
    # Same full identity and top-level site make cross-profile comparisons exact.
    identity_seed = bytes(range(32))
    with loopback_probe() as address:
        for label, option, enabled in [("default", None, True), ("off", False, True),
                                        ("on", True, True), ("master_off", True, False)]:
            with tempfile.TemporaryDirectory(prefix="cloakfox-data-math-") as tmp:
                driver = _build_driver(binary, str(Path(tmp) / "profile"),
                                       data_noise=option, enabled=enabled, allow_system_access=True,
                                       identity_seed=identity_seed)
                try:
                    observations[label] = observe(driver, address)
                    if label == "default":
                        for setting in [True, False]:
                            driver.get("about:cloakfox#sec-hardening")
                            checkbox = WebDriverWait(driver, 10).until(lambda d: d.find_element(
                                By.CSS_SELECTOR, 'input[data-pref="cloakfox.opt.math_data_noise"]'))
                            driver.execute_script('arguments[0].scrollIntoView({block:"center"})', checkbox)
                            WebDriverWait(driver, 10).until(lambda _: checkbox.is_displayed())
                            assert checkbox.is_selected() is not setting, "saved UI checkbox state"
                            checkbox.click()
                            assert checkbox.is_selected() is setting
                            observations["ui_on" if setting else "ui_off"] = observe(driver, address)
                finally:
                    driver.quit()

    report = Path(os.environ.get("REPORT_DIR", Path(__file__).parent / "reports/157-privacy-port/h2/math-data"))
    report.mkdir(parents=True, exist_ok=True)
    (report / "observations.json").write_text(json.dumps(observations, indent=2))

    native = observations["master_off"]
    for realm in ["main", "worker"]:
        for label in ["default", "off", "ui_off"]:
            assert observations[label][f"{realm}_data_math"] == native[f"{realm}_data_math"], (label, realm)
            assert observations[label][f"{realm}_tree_levels"] == [2, 3], (label, realm)
            assert observations[label][f"{realm}_pow_2_neg_52"] == 2.220446049250313e-16, (label, realm)
            assert observations[label][f"{realm}_sin_0_5"] != native[f"{realm}_sin_0_5"], "other math privacy remains active"
        noisy = observations["on"][f"{realm}_data_math"]
        assert all(a != b for a, b in zip(noisy, native[f"{realm}_data_math"])), ("on", realm)
        assert noisy == observations["ui_on"][f"{realm}_data_math"], ("UI on", realm)
        assert observations["on"][f"{realm}_pure"], ("pure", realm)
        assert observations["on"][f"{realm}_sqrt_4"] == 2, ("integer", realm)
    assert observations["on"]["main_data_math"] == observations["on"]["worker_data_math"], "page/worker policies must match"
    print("MATH DATA NOISE PASS — default/off/on/master-off and Settings UI on/off in pages and workers")


if __name__ == "__main__":
    main()
