"""Verify the custom About dialog loads and displays the built app version."""
import os
import shutil
import tempfile
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service


def main():
    opts = Options()
    opts.binary_location = os.environ["CLOAKFOX_BIN"]
    opts.add_argument("--headless")
    with tempfile.TemporaryDirectory() as temp:
        driver = webdriver.Firefox(options=opts, service=Service(
            executable_path=os.environ.get("GECKODRIVER") or shutil.which("geckodriver"),
            service_args=["--allow-system-access"],
            log_output=str(Path(temp) / "geckodriver.log")))
        try:
            driver.set_context("chrome")
            driver.set_script_timeout(20)
            result = driver.execute_async_script(r"""
              const done = arguments[0];
              const dialog = window.openDialog(
                'chrome://browser/content/aboutDialog.xhtml', '', 'chrome,dialog=no');
              const timeout = setTimeout(() => {dialog.close(); done({error:'load timeout'});}, 10000);
              dialog.addEventListener('load', () => setTimeout(() => {
                clearTimeout(timeout);
                const { AppConstants } = ChromeUtils.importESModule(
                  'resource://gre/modules/AppConstants.sys.mjs');
                const result = {name: Services.appinfo.name, expected: AppConstants.MOZ_APP_VERSION_DISPLAY,
                  displayed: dialog.document.getElementById('versionNumber')?.textContent};
                result.errors = Services.console.getMessageArray().map(m => m.message)
                  .filter(m => /chrome:\/\/browser\/content\/aboutDialog\./.test(m));
                dialog.document.getElementById('closeAboutDialog')?.dispatchEvent(
                  new dialog.Event('command'));
                setTimeout(() => {
                  result.closeCommandWorked = dialog.closed;
                  if (!dialog.closed) dialog.close();
                  done(result);
                }, 100);
              }, 100), {once:true});
            """)
            print(result)
            assert result.get("name") == "Cloakfox", result
            assert result.get("displayed") == result.get("expected"), result
            assert result.get("closeCommandWorked"), result
            assert not result.get("errors"), result
        finally:
            driver.quit()
    print("PASS — About dialog loads and displays the actual Cloakfox version")


if __name__ == "__main__":
    main()
