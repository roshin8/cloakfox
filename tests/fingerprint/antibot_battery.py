"""
Anti-bot site battery — launch Cloakfox under each HTTP-transport profile,
visit a suite of bot-detection sites, capture screenshots and extracted
verdicts, and produce a markdown report the user can skim.

This is NOT a pass/fail test. Anti-bot detectors return rich structured
output (trust scores, surface comparisons) that requires human judgment —
a "score 85%" on CreepJS could be good or bad depending on what surfaces
are being called out. The report surfaces the raw data so you can decide.

What gets captured per profile (firefox / chrome / safari):
  - bot.sannysoft.com — per-test table; we extract pass/fail marks
  - arh.antoinevastel.com/bots/areyouheadless — single-sentence verdict
  - browserleaks.com/javascript — fingerprint surface (navigator, etc.)
  - creepjs-api.web.app — trust score + details

Output lands in tests/fingerprint/reports/<timestamp>/ with:
  - REPORT.md                — human-readable summary
  - <site>.<profile>.png     — full-page screenshot per site per profile

Run:

    CLOAKFOX_BIN=/Applications/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/antibot_battery.py

The script does NOT run automatically in pytest — too slow and too
dependent on external sites. Use it as a manual validation tool before
cutting a release or investigating an anti-bot regression.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import time
from pathlib import Path
from typing import Callable

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service


SITES: list[tuple[str, str, Callable]] = [
    # (slug, url, verdict_extractor)
    ("sannysoft", "https://bot.sannysoft.com/", lambda d: _extract_sannysoft(d)),
    (
        "areyouheadless",
        "https://arh.antoinevastel.com/bots/areyouheadless",
        lambda d: _extract_text_of(d, "#res"),
    ),
    (
        "browserleaks-js",
        "https://browserleaks.com/javascript",
        lambda d: _extract_navigator_row(d),
    ),
    # CreepJS endpoint — may be heavy, accept partial data
    ("creepjs", "https://abrahamjuliot.github.io/creepjs/", lambda d: _extract_creepjs(d)),
]


def _build_driver(bin_path: str, h2_profile: str, h3_int: int, log_dir: Path) -> webdriver.Firefox:
    opts = Options()
    opts.binary_location = bin_path
    opts.add_argument("--headless")
    opts.add_argument("-remote-allow-system-access")
    opts.set_preference("network.http.http2.fingerprint_profile", h2_profile)
    opts.set_preference("network.http.http3.fingerprint_profile", h3_int)
    # Let the extension install its content scripts before first probe.
    opts.set_preference("devtools.jsonview.enabled", False)
    log_dir.mkdir(parents=True, exist_ok=True)
    svc = Service(log_path=str(log_dir / "geckodriver.log"))
    d = webdriver.Firefox(options=opts, service=svc)
    d.set_page_load_timeout(60)
    return d


def _extract_text_of(driver, selector: str) -> str:
    try:
        elts = driver.find_elements("css selector", selector)
        if not elts:
            return "<no element>"
        return elts[0].text.strip()[:400]
    except Exception as e:
        return f"<err: {e}>"


def _extract_sannysoft(driver) -> str:
    """sannysoft table has rows; grab pass/fail + signal name per row."""
    try:
        rows = driver.find_elements("css selector", "#fp2 tr, .result")
        lines = []
        for r in rows[:30]:
            t = r.text.strip().replace("\n", " | ")
            if t and len(t) < 200:
                lines.append(t)
        return "\n".join(lines) if lines else "<no rows>"
    except Exception as e:
        return f"<err: {e}>"


def _extract_navigator_row(driver) -> str:
    """Grab the key navigator values rendered by browserleaks."""
    try:
        grid = driver.find_element("id", "content").text
        # Return first ~60 lines
        return "\n".join(grid.splitlines()[:60])
    except Exception as e:
        return f"<err: {e}>"


def _extract_creepjs(driver) -> str:
    try:
        # Wait up to 20s for the dashboard; score usually appears as .unblurred-trust-score
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                s = driver.find_element(
                    "css selector", ".unblurred-trust-score, .trust-score"
                )
                if s.text.strip():
                    break
            except Exception:
                pass
            time.sleep(0.5)
        # Grab the summary area
        try:
            trust = driver.find_element(
                "css selector", ".unblurred-trust-score"
            ).text.strip()
        except Exception:
            trust = "?"
        try:
            fp = driver.find_element("css selector", ".fingerprint").text.strip()
        except Exception:
            fp = "?"
        return f"trust: {trust}\nfp: {fp[:200]}"
    except Exception as e:
        return f"<err: {e}>"


def _visit_site(
    driver: webdriver.Firefox,
    slug: str,
    url: str,
    extractor: Callable,
    screenshot_dir: Path,
    profile_name: str,
) -> dict:
    start = time.time()
    try:
        driver.get(url)
        time.sleep(5.0)  # allow fingerprinting tests time to run
        verdict = extractor(driver)
        png = screenshot_dir / f"{slug}.{profile_name}.png"
        try:
            driver.save_full_page_screenshot(str(png))  # Firefox-specific
        except Exception:
            driver.save_screenshot(str(png))
        elapsed = time.time() - start
        return {"ok": True, "verdict": verdict, "screenshot": png.name, "elapsed_s": round(elapsed, 1)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300], "elapsed_s": round(time.time() - start, 1)}


def run(bin_path: str, profiles: list[str], out_dir: Path) -> None:
    stamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    report_dir = out_dir / stamp
    report_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, dict[str, dict]] = {}
    for profile in profiles:
        h3_int = {"firefox": 0, "chrome": 1, "safari": 2}[profile]
        driver = _build_driver(bin_path, profile, h3_int, report_dir / profile)
        try:
            # Warm up so the extension sets up active profile
            driver.get("about:blank")
            time.sleep(2.0)

            results[profile] = {}
            for slug, url, extractor in SITES:
                print(f"[{profile}] {slug} …", flush=True)
                r = _visit_site(driver, slug, url, extractor, report_dir, profile)
                print(f"  {'OK' if r.get('ok') else 'FAIL'} in {r.get('elapsed_s','?')}s")
                results[profile][slug] = r
        finally:
            driver.quit()

    # Write markdown report
    md = [f"# Cloakfox anti-bot battery — {stamp}\n"]
    md.append(f"Binary: `{bin_path}`\n")
    md.append(f"Profiles tested: {', '.join(profiles)}\n")
    for slug, url, _ in SITES:
        md.append(f"\n## {slug}  ({url})\n")
        md.append("| profile | verdict | screenshot | elapsed |")
        md.append("|---|---|---|---:|")
        for profile in profiles:
            r = results[profile].get(slug, {})
            if r.get("ok"):
                short = (r["verdict"] or "").replace("\n", " / ").replace("|", "\\|")
                short = short[:200] + ("…" if len(short) > 200 else "")
                md.append(
                    f"| {profile} | {short} | ![{slug}.{profile}]({r['screenshot']}) | {r['elapsed_s']}s |"
                )
            else:
                md.append(f"| {profile} | **FAIL:** {r.get('error','?')} | — | {r.get('elapsed_s','?')}s |")

    md.append("\n---\n")
    md.append("## Full extraction (raw)\n")
    md.append("```json")
    md.append(json.dumps(results, indent=2))
    md.append("```")

    report_path = report_dir / "REPORT.md"
    report_path.write_text("\n".join(md))
    print(f"\nReport: {report_path}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--bin", default=os.environ.get("CLOAKFOX_BIN"))
    p.add_argument("--profiles", default="firefox,chrome,safari")
    p.add_argument("--out", default=str(Path(__file__).parent / "reports"))
    args = p.parse_args()
    if not args.bin or not os.path.exists(args.bin):
        p.error(
            "CLOAKFOX_BIN not set or binary missing. "
            "Set via env var or pass --bin /path/to/cloakfox"
        )
    run(args.bin, args.profiles.split(","), Path(args.out))


if __name__ == "__main__":
    main()
