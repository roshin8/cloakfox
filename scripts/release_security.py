#!/usr/bin/env python3
"""Fail-closed Firefox rebase gate; official feed only unless explicit offline fixture."""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
import urllib.request

FEED = 'https://product-details.mozilla.org/1.0/firefox.json'

def assess(version, releases, today, max_age=42):
    today = dt.date.fromisoformat(today)
    def parts(value):
        return tuple(map(int, value.split('.'))) + (0,) * (4 - len(value.split('.')))
    stable = {v: dt.date.fromisoformat(d) for v, d in releases.items()
              if re.fullmatch(r'\d+(?:\.\d+){1,3}', v)}
    released = stable.get(version)
    available = [v for v, d in stable.items() if d <= today]
    latest = max(available, key=parts) if available else None
    age = (today - released).days if released else None
    reasons = []
    if released is None or age < 0:
        reasons.append('Pinned engine has no released entry in the official feed; verify source provenance.')
    if latest != version:
        reasons.append(f'Rebase and rerun native/probe tests against latest stable Firefox {latest}.')
    if age is not None and age > max_age:
        reasons.append(f'Engine release is {age} days old (limit {max_age}); review upstream security releases.')
    return dict(ready=not reasons, engine=version, latest=latest, age_days=age,
                checked_on=today.isoformat(), source=FEED, actions=reasons)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version')
    p.add_argument('--fixture', type=Path, help='Offline test data; never use for release authorization')
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    try:
        version = args.version or re.search(r'^version=(\S+)', (Path(__file__).resolve().parents[1] / 'upstream.sh').read_text(), re.M)[1]
        if args.fixture:
            raw = args.fixture.read_bytes()
        else:
            with urllib.request.urlopen(FEED, timeout=30) as response:
                if response.url != FEED:
                    raise ValueError('Unexpected official-feed redirect')
                raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError('Oversized feed')
        data = json.loads(raw)
        # Product-details keys are product-version labels; use explicit version field.
        releases = {r.get('version', v.removeprefix('firefox-')): r['date'] for v, r in data['releases'].items() if r.get('category') in ('major', 'stability')}
        result = assess(version, releases, dt.date.today().isoformat())
    except (OSError, ValueError, KeyError, TypeError) as error:
        result = dict(ready=False, actions=[f'Cannot verify upstream freshness: {error}'])
    result['offline_fixture'] = bool(args.fixture)
    result['testOnly'] = bool(args.fixture)
    if args.fixture:
        result['assessed_ready'] = result['ready']
        result['ready'] = False
        result['actions'].append('Offline fixture assessment is test-only and cannot authorize a release.')
    text = json.dumps(result, indent=2) + '\n'
    print(text, end='')
    if args.output:
        args.output.write_text(text)
    # Test fixtures retain a useful assessment exit status; their receipt never
    # grants release readiness. Real-feed runs continue to gate on ready alone.
    return 0 if result.get('assessed_ready', result['ready']) else 1

if __name__ == '__main__':
    raise SystemExit(main())
