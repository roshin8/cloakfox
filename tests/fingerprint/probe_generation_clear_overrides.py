"""Generate from settings with optional override clearing in an isolated profile.

Catches a missing checkbox, clearing while unchecked, stale generated values,
clearing another container, or clearing when applying a saved preview.
"""
import os
from pathlib import Path
import shutil
import tempfile

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait


def main():
    with tempfile.TemporaryDirectory(prefix="cloakfox-generation-clear-") as temp:
        options = Options()
        options.binary_location = os.environ["CLOAKFOX_BIN"]
        options.add_argument("--headless")
        options.add_argument("-purgecaches")
        options.add_argument("-profile")
        profile = Path(temp) / "profile"
        profile.mkdir()
        options.add_argument(str(profile))
        driver = webdriver.Firefox(options=options, service=Service(
            executable_path=os.environ.get("GECKODRIVER") or shutil.which("geckodriver"),
            service_args=["--allow-system-access"],
            log_output=str(Path(temp) / "gecko.log")))
        try:
            def chrome(script, *args):
                driver.set_context("chrome")
                try:
                    return driver.execute_script(script, *args)
                finally:
                    driver.set_context("content")

            def state():
                return chrome("""
                    const { readOverrides } = ChromeUtils.importESModule(
                      'resource:///modules/CloakfoxOverrides.sys.mjs');
                    return {
                      overrides: readOverrides(0), other: readOverrides(arguments[0]),
                      cfg: JSON.parse(Services.prefs.getStringPref('cloakfox.s.cloak_cfg_0')),
                      seed: Services.prefs.getStringPref('cloakfox.container.0.math_seed')
                    };
                """, other)

            def seed_overrides():
                chrome("""
                    const { setOverride } = ChromeUtils.importESModule(
                      'resource:///modules/CloakfoxOverrides.sys.mjs');
                    setOverride(0, 'navigator.hardwareConcurrency', 999);
                    setOverride(0, 'webGl:vendor', 'manual-test-vendor');
                    setOverride(arguments[0], 'navigator.hardwareConcurrency', 777);
                """, other)

            def load():
                driver.get("about:cloakfox")
                WebDriverWait(driver, 15).until(lambda d: d.execute_script(
                    "return !!document.getElementById('cfx-generate-new') && "
                    "document.getElementById('cfx-persona-choice').options.length > 1"))
                assert driver.execute_script("""
                    const box = document.getElementById('cfx-generation-clear-overrides');
                    return !!box && box.type === 'checkbox' && box.getClientRects().length > 0;
                """), "Clear-overrides checkbox is missing from the generation UI"

            def apply(button):
                driver.execute_script("document.getElementById(arguments[0]).click()", button)
                WebDriverWait(driver, 15).until(lambda d: d.execute_script(
                    "return !document.getElementById(arguments[0]).hasAttribute('aria-busy')", button))
                assert driver.execute_script(
                    "return document.querySelector('.profile-preview-label').textContent === 'Applied identity'"
                ), driver.execute_script("return document.getElementById('cfx-identity-status').textContent")

            other = chrome("""
                const { ContextualIdentityService } = ChromeUtils.importESModule(
                  'moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs');
                return ContextualIdentityService.create('Other test container', 'fingerprint', 'blue').userContextId;
            """)
            chrome("""
                ChromeUtils.importESModule('resource:///modules/CloakfoxPrivacyPolicy.sys.mjs')
                  .setPrivacyPolicy(0, {version: 1, preset: 'strict', exceptions: []});
            """)
            seed_overrides()
            driver.set_context("content")
            load()
            assert not driver.execute_script(
                "return document.getElementById('cfx-generation-clear-overrides').checked")
            before = state()
            apply("cfx-generate-new")
            kept = state()
            assert kept["seed"] != before["seed"]
            assert kept["overrides"] == before["overrides"]
            assert kept["cfg"]["navigator.hardwareConcurrency"] == 999
            assert kept["cfg"]["webGl:vendor"] == "manual-test-vendor"

            driver.execute_script("document.getElementById('cfx-generation-clear-overrides').click()")
            apply("cfx-generate-new")
            cleared = state()
            assert cleared["seed"] != kept["seed"]
            assert cleared["overrides"] == {}, cleared
            assert cleared["cfg"]["navigator.hardwareConcurrency"] != 999
            assert cleared["cfg"]["webGl:vendor"] != "manual-test-vendor"
            assert cleared["cfg"]["privacy:policy"]["preset"] == "strict"
            assert cleared["cfg"]["mediaDevices:enabled"] is False
            assert cleared["cfg"]["navigator:clipboard:disabled"] is True
            assert cleared["other"] == kept["other"], "Cleared another container's overrides"
            assert driver.execute_script("return document.getElementById('cfx-profile-preview-traits').textContent.includes('No manual overrides')")

            # The generation option must not change the selected-preview workflow.
            seed_overrides()
            driver.execute_script("""
                const choice = document.getElementById('cfx-persona-choice');
                choice.value = '0'; choice.dispatchEvent(new Event('change'));
            """)
            apply("cfx-regenerate")
            preview = state()
            assert preview["overrides"] == kept["overrides"]
            assert preview["cfg"]["navigator.hardwareConcurrency"] == 999
            assert preview["other"] == kept["other"]

            # Reopening settings returns to the safe unchecked default.
            load()
            assert not driver.execute_script(
                "return document.getElementById('cfx-generation-clear-overrides').checked")
            print("PASS: unchecked retention, checked clearing, fresh values, container isolation, preview retention and safe default")
        finally:
            driver.quit()


if __name__ == "__main__":
    main()
