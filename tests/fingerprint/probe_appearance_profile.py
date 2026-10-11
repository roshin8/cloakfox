#!/usr/bin/env python3
"""Native startup selection, with isolated profile databases in xpcshell."""
import os
from pathlib import Path
import subprocess


def main():
    assert os.uname().sysname == "Darwin"
    binary = Path(os.environ["CLOAKFOX_XPCSHELL"]).resolve()
    case = Path(__file__).with_name("appearance_profile_case.js")
    # Standalone xpcshell is outside a macOS app bundle. Its socket sandbox
    # cannot derive an app path; these filesystem-only tests need no networking.
    env = {**os.environ, "MOZ_DISABLE_SOCKET_PROCESS": "1"}
    for mode in ("bound", "environment", "argument", "named", "manager", "invalid", "absent"):
        subprocess.run([str(binary), "-f", str(case)], check=True,
                       env={**env, "CLOAKFOX_PROFILE_CASE": mode}, timeout=30)


if __name__ == "__main__":
    main()
