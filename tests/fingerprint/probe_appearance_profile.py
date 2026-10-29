#!/usr/bin/env python3
"""Native startup selection, with isolated profile databases in xpcshell."""
import os
from pathlib import Path
import subprocess
import sys


def main():
    if sys.platform != "darwin":
        print("INCONCLUSIVE — macOS appearance profile binding requires macOS")
        return 2
    configured = os.environ.get("CLOAKFOX_XPCSHELL")
    if configured:
        binary = Path(configured).resolve()
        assert binary.is_file(), f"Configured xpcshell does not exist: {binary}"
    else:
        browser = Path(os.environ.get("CLOAKFOX_BIN", "")).resolve()
        candidates = [browser.parent / "xpcshell"]
        candidates += [parent / "bin" / "xpcshell" for parent in list(browser.parents)[:4]]
        binary = next((path for path in candidates if path.is_file()), None)
        if binary is None:
            print("INCONCLUSIVE — set CLOAKFOX_XPCSHELL to run native startup profile cases")
            return 2
    case = Path(__file__).with_name("appearance_profile_case.js")
    # Standalone xpcshell is outside a macOS app bundle. Its socket sandbox
    # cannot derive an app path; these filesystem-only tests need no networking.
    env = {**os.environ, "MOZ_DISABLE_SOCKET_PROCESS": "1"}
    for mode in ("bound", "environment", "argument", "named", "manager", "invalid", "absent"):
        subprocess.run([str(binary), "-f", str(case)], check=True,
                       env={**env, "CLOAKFOX_PROFILE_CASE": mode}, timeout=30)
    return 0


if __name__ == "__main__":
    sys.exit(main())
