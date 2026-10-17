"""Run daily-driver probes sequentially in disposable browser profiles.

CLOAKFOX_BIN must name the built browser; run with a Python containing Selenium.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

PROBES = ['daily_defaults', 'persona_version', 'browser_profile_picker', 'bundled_blocker', 'network_policy',
          'native_webrtc_policy', 'identity_forget', 'shared_permissions',
          'site_isolation', 'container_workflows', 'daily_settings_ui', 'settings_navigation', 'upstream_hardening', 'regions', 'privacy_inspector', 'proxy_manager', 'bundled_containers', 'ip_conflicts', 'ip_conflict_settings', 'templates', 'worker_lifecycle', 'permissions_workspaces', 'dns_network', 'tracking_protection', 'network_transports', 'host_personas', 'network_quic']

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--only', choices=PROBES, action='append')
    args = parser.parse_args()
    if not os.environ.get('CLOAKFOX_BIN'):
        parser.error('Set CLOAKFOX_BIN to the built browser executable')
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    for name in args.only or PROBES:
        start = time.monotonic()
        with (args.output / f'probe-{name}.log').open('w') as output:
            run = subprocess.run([sys.executable, str(Path(__file__).with_name(f'probe_{name}.py'))],
                                 stdout=output, stderr=subprocess.STDOUT)
        result = {'probe': name, 'exit': run.returncode, 'seconds': round(time.monotonic()-start, 1)}
        results.append(result)
        print(json.dumps(result), flush=True)
    (args.output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    return int(any(result['exit'] for result in results))

if __name__ == '__main__':
    sys.exit(main())
