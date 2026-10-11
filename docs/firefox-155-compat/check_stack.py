"""Apply the current stack to a fresh, disposable Firefox source tree.

Usage: python3 docs/firefox-155-compat/check_stack.py SOURCE VERSION [RUN_LABEL]
Continues after failures for an inventory; later failures may be cascading.
Never rerun against an already patched tree.
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'scripts'))
from _mixin import list_patches

source = Path(sys.argv[1]).resolve()
version = sys.argv[2]
output = Path(__file__).resolve().parent / (sys.argv[3] if len(sys.argv) > 3 else version)
output.mkdir(exist_ok=False)
copy = subprocess.run(
    ['bash', str(repo / 'scripts/copy-additions.sh'), version, 'beta.25', str(repo)],
    cwd=source, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
)
(output / 'copy-additions.log').write_text(copy.stdout)
if copy.returncode:
    raise SystemExit('copy-additions failed; see log')

results = []
for index, filename in enumerate(list_patches(str(repo / 'patches')), 1):
    patch = Path(filename)
    command = ['patch', '-p1', '--batch', '--forward', '-i', str(patch)]
    run = subprocess.run(command, cwd=source, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log = run.stdout
    (output / f'{index:02d}-{patch.name}.log').write_text(log)
    issues = [line for line in log.splitlines() if re.search(
        r'FAILED|malformed|ignored|Skipping|can.t find|saving rejects|Reversed|previously applied', line, re.I)]
    status = 'failed' if run.returncode or issues else (
        'applied-with-fuzz' if 'fuzz' in log else
        'applied-with-offset' if 'offset' in log else 'applied')
    result = {
        'order': index, 'patch': str(patch.relative_to(repo)),
        'sha256': hashlib.sha256(patch.read_bytes()).hexdigest(),
        'status': status, 'returncode': run.returncode,
        'failed_hunks': sum(int(n) for n in re.findall(
            r'(\d+) out of \d+ hunks? failed', log, re.I)),
        'ignored_hunks': sum(int(n) for n in re.findall(
            r'(\d+) out of \d+ hunks? ignored', log, re.I)),
        'fuzzy_hunks': len(re.findall(r'with fuzz \d+', log)),
        'issues': issues,
    }
    results.append(result)
    print(f'{index:02d} {status:20s} {patch.name}', flush=True)

(output / 'results.json').write_text(json.dumps({
    'version': version, 'source': str(source),
    'patch_command': 'patch -p1 --batch --forward -i PATCH',
    'results': results,
}, indent=2) + '\n')
failed = sum(r['status'] == 'failed' for r in results)
print(f'{version}: {len(results) - failed}/{len(results)} applied; {failed} failed')
raise SystemExit(bool(failed))
