#!/usr/bin/env python3
"""Measure a Mac runner without modifying its installed tools or storage."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile

GIB = 1024 ** 3


def command(argv):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=120)
        return {"exitCode": result.returncode,
                "output": (result.stdout + result.stderr).strip()}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"exitCode": -1, "output": str(error)}


def readiness(report):
    try:
        sdk = tuple(int(part) for part in report.get("sdkVersion", "").split("."))
    except ValueError:
        sdk = ()
    # Conservative local build budget, not a claim about GitHub's disk limit.
    source = (report.get("system") == "Darwin"
              and report.get("architecture") == "arm64"
              and report.get("freeBytes", 0) >= 128 * GIB
              and report.get("xcodeAvailable", False)
              and sdk >= (26, 5))
    return {"sourceBuild": bool(source),
            "metalRuntime": bool(source and report.get("metalAvailable", False)),
            "minimumFreeGiB": 128,
            "note": "Capacity preflight only; successful builds and browser tests remain required."}


def probe(root):
    disk = shutil.disk_usage(root)
    report = {"system": platform.system(), "architecture": platform.machine(),
              "cpuCount": os.cpu_count(), "totalBytes": disk.total,
              "freeBytes": disk.free, "xcodeAvailable": False,
              "sdkVersion": "", "metalAvailable": False}
    if report["system"] == "Darwin":
        report["memory"] = command(["sysctl", "-n", "hw.memsize"])
        report["disk"] = command(["diskutil", "info", str(root)])
        report["developerDirectory"] = command(["xcode-select", "-p"])
        report["xcode"] = command(["xcodebuild", "-version"])
        report["installedXcodes"] = sorted(str(p) for p in Path("/Applications").glob("Xcode*.app"))
        report["sdk"] = command(["xcrun", "--sdk", "macosx", "--show-sdk-version"])
        report["sdkVersion"] = report["sdk"]["output"] if report["sdk"]["exitCode"] == 0 else ""
        report["xcodeAvailable"] = report["xcode"]["exitCode"] == 0
        fixture = Path(__file__).resolve().parents[2] / "tests/engines/metal_runtime_check.mm"
        with tempfile.TemporaryDirectory(prefix="cloakfox-metal-") as directory:
            binary = str(Path(directory) / "metal-check")
            report["metalCompile"] = command(["xcrun", "clang++", str(fixture),
                                               "-framework", "Foundation", "-framework", "Metal", "-o", binary])
            if report["metalCompile"]["exitCode"] == 0:
                report["metalRun"] = command([binary])
                report["metalAvailable"] = report["metalRun"]["exitCode"] == 0
    report["readiness"] = readiness(report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = probe(Path.cwd())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
            summary.write("### Measured runner capabilities\n\n")
            summary.write(f"- Architecture: {report['architecture']}\n")
            summary.write(f"- Free storage: {report['freeBytes'] / GIB:.1f} GiB\n")
            summary.write(f"- Selected macOS SDK: {report['sdkVersion']}\n")
            summary.write(f"- Metal compute executed: {report['metalAvailable']}\n")
            summary.write(f"- Conservative source-build preflight: {report['readiness']['sourceBuild']}\n")
            summary.write("\nThis survey does not build Chromium or verify browser privacy.\n")


if __name__ == "__main__":
    main()
