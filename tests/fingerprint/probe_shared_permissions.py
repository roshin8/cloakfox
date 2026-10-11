"""Verify selective OA clearing preserves shared permissions in a disposable profile.

Set CLOAKFOX_BIN to a rebuilt browser containing the WithFlags IDL. No external
navigation and no real profile are used. Run sequentially with other live probes.
"""
import json
import os
import shutil
import tempfile
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service


def main():
    with tempfile.TemporaryDirectory(prefix="cloakfox-permission-clear-") as temp:
        options = Options()
        options.binary_location = os.environ["CLOAKFOX_BIN"]
        options.add_argument("--headless")
        driver = webdriver.Firefox(options=options, service=Service(
            executable_path=os.environ.get("GECKODRIVER") or shutil.which("geckodriver"),
            service_args=["--allow-system-access"], log_output=str(Path(temp) / "geckodriver.log")))
        try:
            driver.set_context("chrome")
            driver.set_script_timeout(45)
            result = driver.execute_async_script(r"""
              const done = arguments[0];
              (async () => {
                const c = Ci.nsIClearDataService;
                const excluded = c.CLEAR_SITE_PERMISSIONS | c.CLEAR_STORAGE_ACCESS |
                  c.CLEAR_STORAGE_PERMISSIONS | c.CLEAR_SHUTDOWN_EXCEPTIONS;
                const scopedDefault = (c.CLEAR_ALL & ~excluded) >>> 0;
                const clear = (id, flags) => new Promise((resolve, reject) => {
                  Services.clearData.deleteDataFromOriginAttributesPatternWithFlags(
                    { userContextId: id }, flags, { onDataDeleted: flags => flags ? reject(Error('Clear failed: ' + flags)) : resolve() });
                });
                const p = id => Services.scriptSecurityManager.createContentPrincipal(
                  Services.io.newURI('https://shared-permission.example'), { userContextId: id });
                const allow = Services.perms.ALLOW_ACTION, unknown = Services.perms.UNKNOWN_ACTION;
                const read = (id, type) => Services.perms.testPermissionFromPrincipal(p(id), type);
                Services.prefs.setBoolPref('permissions.isolateBy.userContext', false);
                Services.perms.addFromPrincipal(p(2), 'camera', allow);
                const storedBefore = Services.perms.getPermissionObject(p(2), 'camera', true).principal.originAttributes.userContextId;
                if (storedBefore !== 0) throw Error('Fixture did not create shared OA0 permission');
                await clear(0, scopedDefault);
                if (read(2, 'camera') !== allow || read(3, 'camera') !== allow) throw Error('Default clear removed shared camera permission');
                await clear(2, c.CLEAR_ALL);
                if (read(3, 'camera') !== allow) throw Error('Named clear removed shared camera permission');
                Services.prefs.setBoolPref('permissions.isolateBy.userContext', true);
                Services.perms.addFromPrincipal(p(2), 'microphone', allow);
                Services.perms.addFromPrincipal(p(3), 'microphone', allow);
                Services.perms.addFromPrincipal(p(2), 'cookie', allow);
                Services.perms.addFromPrincipal(p(2), 'https-only-load-insecure', allow);
                await clear(0, scopedDefault);
                if (read(2, 'cookie') !== allow || read(3, 'https-only-load-insecure') !== allow) throw Error('Default clear removed always-shared permissions');
                if (read(2, 'microphone') !== allow || read(3, 'microphone') !== allow) throw Error('Default clear removed named permission');
                await clear(2, c.CLEAR_ALL);
                if (read(2, 'microphone') !== unknown || read(3, 'microphone') !== allow) throw Error('Named clearing was not scoped');
                if (read(3, 'cookie') !== allow || read(3, 'https-only-load-insecure') !== allow) throw Error('Named clear removed always-shared permissions');
                return { sharedDefaultPreserved: true, sharedNamedPreserved: true,
                  alwaysSharedPreserved: true, isolatedTargetRemoved: true, isolatedControlPreserved: true };
              })().then(done, error => done({ error: error.message, stack: error.stack }));
            """)
            print(json.dumps(result, indent=2))
            assert result.get("sharedDefaultPreserved") and result.get("isolatedControlPreserved"), result
            print("PASS: shared and unrelated permissions retained; named isolated permissions cleared")
        finally:
            driver.quit()


if __name__ == "__main__":
    main()
