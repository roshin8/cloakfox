"""Disposable-profile startup/restart check; run sequentially after rebuilding.

Requires CLOAKFOX_BIN and geckodriver. Does not contact malicious test URLs or
claim Safe Browsing list availability; reports provider key readiness separately.
"""
import json
import os
import shutil
import tempfile
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

PROTECTIVE = ["browser.safebrowsing.malware.enabled",
              "browser.safebrowsing.phishing.enabled", "dom.security.https_only_mode"]
CHOICES = {
    "browser.safebrowsing.malware.enabled": False,
    "browser.safebrowsing.phishing.enabled": False,
    "dom.security.https_only_mode": False,
    "browser.search.suggest.enabled": True,
    "browser.urlbar.suggest.searches": True,
    "browser.urlbar.suggest.history": False,
    "browser.newtabpage.enabled": False,
    "signon.rememberSignons": False,
    "browser.formfill.enable": False,
    "browser.tabs.warnOnClose": False,
    "layout.spellcheckDefault": 2,
    "ui.prefersReducedMotion": 1,
}
READ = """
const values = {};
for (const key of arguments[0]) {
  const type = Services.prefs.getPrefType(key);
  values[key] = type === 128 ? Services.prefs.getBoolPref(key) :
    type === 64 ? Services.prefs.getIntPref(key) : Services.prefs.getStringPref(key);
}
return values;
"""


def launch(profile, log, *, distro_addons=False):
    options = Options()
    options.binary_location = os.environ["CLOAKFOX_BIN"]
    options.add_argument("--headless")
    options.add_argument("-profile")
    options.add_argument(str(profile))
    # Firefox automation otherwise disables Safe Browsing itself.
    options.set_preference("remote.prefs.recommended", False)
    if distro_addons:
        # geckodriver writes these false even with remote.prefs.recommended=false.
        # Restore the verified production defaults to exercise distro startup.
        options.set_preference("extensions.installDistroAddons", True)
        options.set_preference("extensions.update.enabled", True)
    driver = webdriver.Firefox(options=options, service=Service(
        executable_path=os.environ.get("GECKODRIVER") or shutil.which("geckodriver"),
        service_args=["--allow-system-access"], log_output=str(log)))
    driver.set_context("chrome")
    return driver


def main():
    with tempfile.TemporaryDirectory(prefix="cloakfox-daily-defaults-") as temp:
        profile = Path(temp) / "profile"
        profile.mkdir()
        driver = launch(profile, Path(temp) / "first.log")
        try:
            values = driver.execute_script(READ, PROTECTIVE + [
                "browser.search.suggest.enabled", "browser.urlbar.suggest.searches"])
            assert all(values[key] is True for key in PROTECTIVE), values
            assert values["browser.search.suggest.enabled"] is False, values
            assert values["browser.urlbar.suggest.searches"] is False, values
            status = driver.execute_script("""
              const { SafeBrowsing } = ChromeUtils.importESModule(
                'resource://gre/modules/SafeBrowsing.sys.mjs');
              const win = Services.wm.getMostRecentWindow('navigator:browser');
              return {
                googleProviderKeyReady: SafeBrowsing.checkGoogleSafeBrowsingKey('google5'),
                customChromeStylesheetLoaded: Array.from(win.document.styleSheets)
                  .some(sheet => /(?:^|\\/)chrome\\.css(?:$|[?#])/.test(sheet.href || '')),
                extensionControlPresent: !!win.document.getElementById('unified-extensions-button'),
                bookmarkControlPresent: !!win.document.getElementById('star-button-box')
              };
            """)
            assert status["extensionControlPresent"], status
            assert status["bookmarkControlPresent"], status
            print(json.dumps({"fresh": values, "status": status}, indent=2))
            driver.execute_script("""
              for (const [key, value] of Object.entries(arguments[0])) {
                if (typeof value === 'boolean') Services.prefs.setBoolPref(key, value);
                else Services.prefs.setIntPref(key, value);
              }
              Services.prefs.setBoolPref('privacy.resistFingerprinting', true);
              Services.prefs.setBoolPref('privacy.userContext.enabled', false);
              const principal = Services.scriptSecurityManager.createContentPrincipal(
                Services.io.newURI('http://daily-defaults.example'), {});
              Services.perms.addFromPrincipal(principal, 'https-only-load-insecure',
                Services.perms.ALLOW_ACTION);
              Services.prefs.savePrefFile(null);
            """, CHOICES)
        finally:
            driver.quit()
        driver = launch(profile, Path(temp) / "second.log")
        try:
            values = driver.execute_script(READ, list(CHOICES))
            assert values == CHOICES, values
            invariants = driver.execute_script(READ, [
                "privacy.resistFingerprinting", "privacy.userContext.enabled"])
            assert invariants == {"privacy.resistFingerprinting": False,
                                  "privacy.userContext.enabled": True}, invariants
            assert driver.execute_script("""
              const principal = Services.scriptSecurityManager.createContentPrincipal(
                Services.io.newURI('http://daily-defaults.example'), {});
              return Services.perms.testPermissionFromPrincipal(
                principal, 'https-only-load-insecure') === Services.perms.ALLOW_ACTION;
            """), "HTTPS-Only site exception was lost"
            print("PASS: protective defaults, choices, invariants and HTTPS exception across restart")
        finally:
            driver.quit()


if __name__ == "__main__":
    main()
