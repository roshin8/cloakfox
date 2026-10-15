"""Install pinned upstream test fixtures without package lifecycle scripts."""
import hashlib
import json
import subprocess
from pathlib import Path


def ensure_creep_fixture(creep, spec):
    """Mutate only a dedicated, clean fixture checkout; never a parent repo."""
    if not creep.exists():
        creep.mkdir(parents=True)
        subprocess.run(['git', 'init', '-q', str(creep)], check=True)
        subprocess.run(['git', '-C', str(creep), 'remote', 'add', 'origin', spec['repository']], check=True)
    if not (creep / '.git').is_dir() or (creep / '.git').is_symlink():
        raise RuntimeError('Existing fixture lacks its own Git directory; use a fresh fixture directory')
    def git(*args):
        return subprocess.check_output(['git', '-C', str(creep), *args], text=True).strip()
    if Path(git('rev-parse', '--show-toplevel')).resolve() != creep.resolve():
        raise RuntimeError('Fixture Git root does not match the fixture directory')
    if git('remote', 'get-url', 'origin') != spec['repository']:
        raise RuntimeError('Unexpected fixture origin; refusing to mutate checkout')
    if git('status', '--porcelain', '--untracked-files=normal'):
        raise RuntimeError('Fixture is modified; restore it or choose a fresh fixture directory')
    current = subprocess.run(['git', '-C', str(creep), 'rev-parse', 'HEAD'], capture_output=True, text=True)
    if current.returncode or current.stdout.strip() != spec['commit']:
        subprocess.run(['git', '-C', str(creep), 'fetch', '--depth', '1', 'origin', spec['commit']], check=True)
        subprocess.run(['git', '-C', str(creep), 'checkout', '--detach', 'FETCH_HEAD'], check=True)
    if hashlib.sha256((creep / spec['bundle']).read_bytes()).hexdigest() != spec['bundleSHA256']:
        raise RuntimeError('CreepJS bundle checksum mismatch')


def main():
    root = Path(__file__).resolve().parents[1]
    libraries = root / 'tests/fingerprint/libraries'
    manifest = json.loads((libraries / 'upstreams.json').read_text())
    ensure_creep_fixture(root / 'tests/fingerprint/reports/library-fixtures/creepjs', manifest['creepjs'])
    subprocess.run(['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], cwd=libraries, check=True)
    bundle = libraries / 'node_modules/@fingerprintjs/fingerprintjs' / manifest['fingerprintjs']['bundle']
    if hashlib.sha256(bundle.read_bytes()).hexdigest() != manifest['fingerprintjs']['bundleSHA256']:
        raise RuntimeError('FingerprintJS bundle checksum mismatch')
    print('Pinned CreepJS and FingerprintJS fixtures are ready.')


if __name__ == '__main__':
    main()
