#!/usr/bin/env python3
"""Reclaim build space exclusively on disposable GitHub-hosted Macs."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess


def require_hosted(env):
    if env.get('GITHUB_ACTIONS') != 'true' or env.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise RuntimeError('Cleanup is restricted to disposable GitHub-hosted Actions runners')


def unused_xcodes(applications, developer):
    selected = developer.resolve().parents[1]
    if selected.parent != applications.resolve() or not selected.name.startswith('Xcode') or selected.suffix != '.app':
        raise RuntimeError('Selected Xcode must be an application under Applications')
    return sorted(p for p in applications.glob('Xcode*.app')
                  if not p.is_symlink() and p.resolve() != selected)


def cleanup_targets(obsolete, developer, home, *, preserve_active=False):
    if preserve_active:
        return list(obsolete)
    # Preserve the selected compiler, toolchains and MacOSX.platform. Only mobile
    # targets and disposable simulator data are irrelevant to these desktop jobs.
    mobile = ('iPhoneOS.platform', 'iPhoneSimulator.platform', 'AppleTVOS.platform',
              'AppleTVSimulator.platform', 'WatchOS.platform', 'WatchSimulator.platform',
              'XROS.platform', 'XRSimulator.platform')
    candidates = list(obsolete) + [developer / 'Platforms' / name for name in mobile]
    candidates += [home / 'Library/Developer/CoreSimulator',
                   Path('/Library/Developer/CoreSimulator/Caches'),
                   Path('/Library/Developer/CoreSimulator/Images')]
    return candidates


def main():
    from runner_probe import probe
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--preserve-active-xcode', action='store_true', help='Retain selected Xcode platforms and CoreSimulator state')
    args = parser.parse_args()
    require_hosted(os.environ)
    if platform.system() != 'Darwin':
        raise RuntimeError('Only hosted macOS cleanup is supported')
    before = probe(Path.cwd())
    developer = Path(subprocess.check_output(['xcode-select', '-p'], text=True).strip())
    obsolete = unused_xcodes(Path('/Applications'), developer)
    candidates = cleanup_targets(obsolete, developer, Path.home(), preserve_active=args.preserve_active_xcode)
    removed = []
    for target in candidates:
        if target.exists() and not target.is_symlink():
            print('Reclaiming hosted runner path:', target, flush=True)
            subprocess.run(['sudo', 'rm', '-rf', '--', str(target)], check=True)
            removed.append(str(target))
    after = probe(Path.cwd())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'before': before, 'removed': removed, 'after': after}, indent=2) + '\n')
    print(json.dumps(after, indent=2))
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
            summary.write(f"## Source build capacity\n\nFree after cleanup: {after['freeBytes']/1024**3:.1f} GiB.\n\n")
            summary.write(f"SDK {after['sdkVersion']}; Metal compute passed: {after['metalAvailable']}.\n")
    if not after['readiness']['sourceBuild'] or not after['metalAvailable']:
        raise RuntimeError('Hosted runner lacks the 128 GiB budget, selected SDK, architecture or real Metal execution')


if __name__ == '__main__':
    main()
