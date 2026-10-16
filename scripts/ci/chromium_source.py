#!/usr/bin/env python3
"""Pinned Chromium/CEF source pipeline for fresh macOS arm64 CI workspaces."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request

REPO = Path(__file__).resolve().parents[2]
ENGINE = REPO / 'engines/chromium'
GIB = 1024**3


def digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def verify_archive(path, lock):
    if path.stat().st_size != lock['archiveSize'] or digest(path) != lock['archiveSha256']:
        raise ValueError('Pinned Chromium source archive size/SHA256 mismatch')


def extract_source(archive, destination):
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive, 'r:xz') as bundle:
        def members():
            prefix = None
            for member in bundle:
                if prefix is None:
                    prefix = member.name.split('/')[0]
                if member.name.rstrip('/') == prefix:
                    continue
                if not member.name.startswith(prefix + '/'):
                    raise ValueError('Unexpected source archive root')
                member.name = member.name[len(prefix) + 1:]
                if member.islnk() and member.linkname.startswith(prefix + '/'):
                    member.linkname = member.linkname[len(prefix) + 1:]
                yield member
        bundle.extractall(destination, members=members(), filter='data')


def verify_chain(source, locks):
    expected = {}
    for lock in locks:
        for entry in lock['inputs']:
            expected[entry['path']] = entry['afterSha256']
    for name, sha in expected.items():
        path = source / name
        if not path.resolve().is_relative_to(source.resolve()) or not path.is_file() or digest(path) != sha:
            raise ValueError('Native patch chain hash mismatch: ' + name)


def refresh_sdk(source, out, sdk):
    transfers = ast.literal_eval((source / 'cef/tools/distrib/transfer.cfg').read_text())
    mapped = {item['target']: (source / 'cef' / item['source']).resolve() for item in transfers}
    for area in ('include', 'libcef_dll'):
        for dest in sorted((sdk / area).rglob('*')):
            if not dest.is_file() or dest.name in ('CMakeLists.txt', 'README-TRANSFER.txt', 'TRANSFER-README.txt'):
                continue
            relative = dest.relative_to(sdk)
            generated = out / 'gen/cef' / relative
            origin = mapped.get(relative.as_posix())
            if origin is None:
                origin = generated if generated.is_file() else source / 'cef' / relative
            if not origin.resolve().is_relative_to(source.resolve()) or not origin.is_file():
                raise RuntimeError('Missing/invalid source SDK input: ' + str(relative))
            shutil.copyfile(origin, dest)
    for name, origin in mapped.items():
        dest = sdk / name
        if not origin.is_relative_to(source.resolve()) or not dest.resolve().is_relative_to(sdk.resolve()):
            raise RuntimeError('SDK transfer path escapes roots')
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, dest)


class Pipeline:
    def __init__(self, root):
        self.root = root
        self.logs = root / 'evidence'
        self.logs.mkdir(parents=True, exist_ok=True)
        self.env = dict(os.environ)

    def run(self, name, command, cwd=None):
        print('STAGE', name, flush=True)
        status = {'stage': name, 'state': 'running', 'started': time.time(),
                  'freeBytes': shutil.disk_usage(self.root).free}
        (self.logs / 'stage.json').write_text(json.dumps(status, indent=2))
        with (self.logs / (name + '.log')).open('a') as output:
            process = subprocess.Popen([str(item) for item in command], cwd=cwd or REPO,
                                       env=self.env, stdout=output, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL, start_new_session=True)
            minimum_free = status['freeBytes']
            while process.poll() is None:
                minimum_free = min(minimum_free, shutil.disk_usage(self.root).free)
                if minimum_free < 10 * GIB:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                    raise RuntimeError('Stopped owned CI stage before exhausting the 10 GiB storage reserve')
                time.sleep(5)
            status.update(state='passed' if process.returncode == 0 else 'failed',
                          exitCode=process.returncode, finished=time.time(), minimumFreeBytes=minimum_free,
                          freeBytes=shutil.disk_usage(self.root).free)
            (self.logs / 'stage.json').write_text(json.dumps(status, indent=2))
            with (self.logs / 'capacity-stages.jsonl').open('a') as capacity:
                capacity.write(json.dumps(status) + '\n')
            print((self.logs / (name + '.log')).read_text(errors='replace')[-6000:], flush=True)
            if process.returncode:
                raise RuntimeError(f'{name} failed: {process.returncode}')

    def checkout(self, name, url, revision):
        target = self.root / name
        self.run(name + '-clone', ['git', 'clone', url, target])
        self.run(name + '-pin', ['git', 'checkout', '--detach', revision], target)
        if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=target, text=True).strip() != revision:
            raise RuntimeError('Repository pin mismatch: ' + name)
        return target

    def prepare(self):
        lock = json.loads((ENGINE / 'source-lock.json').read_text())
        binary_lock = json.loads((ENGINE / 'cef-lock.json').read_text())
        if lock['chromiumVersion'] != binary_lock['chromiumVersion']:
            raise RuntimeError('Source and SDK template versions differ')
        depot = self.checkout('depot_tools', lock['depotToolsRepository'], lock['depotToolsCommit'])
        self.env.update(PATH=str(depot) + os.pathsep + os.environ['PATH'],
                        DEPOT_TOOLS_UPDATE='0', GIT_CEILING_DIRECTORIES=str(self.root),
                        CIPD_CACHE_DIR=str(self.root / 'cipd-cache'),
                        VPYTHON_VIRTUALENV_ROOT=str(self.root / 'vpython-cache'),
                        GN_OUT_CONFIGS='Release_GN_arm64')
        archive = self.root / 'chromium.tar.xz'
        print('Downloading pinned Chromium source archive', flush=True)
        urllib.request.urlretrieve(lock['archiveUrl'], archive)
        verify_archive(archive, lock)
        workspace = self.root / 'chromium'
        workspace.mkdir()
        source = workspace / 'src'
        extract_source(archive, source)
        archive.unlink()  # Verified extracted archive, not a compiler/source cache.
        cef_checkout = self.checkout('cef-checkout', lock['cefRepository'], lock['cefCommit'])
        cef_checkout.rename(source / 'cef')
        version = dict(line.split('=', 1) for line in (source / 'chrome/VERSION').read_text().splitlines())
        if '.'.join(version[key] for key in ('MAJOR', 'MINOR', 'BUILD', 'PATCH')) != lock['chromiumVersion']:
            raise RuntimeError('Extracted Chromium version mismatch')
        for name, cwd in [('tarball_gclient.patch', depot), ('tarball_deps.patch', source)]:
            patch = source / 'cef/patch/patches' / name
            self.run(name + '-check', ['git', 'apply', '--check', patch], cwd)
            self.run(name, ['git', 'apply', patch], cwd)
        solution = {'name': 'src', 'url': 'https://chromium.googlesource.com/chromium/src.git@' + lock['chromiumVersion'],
                    'managed': False, 'custom_vars': {'source_tarball': True, 'checkout_pgo_profiles': False},
                    'custom_deps': {}, 'deps_file': 'DEPS', 'safesync_url': ''}
        (workspace / '.gclient').write_text('solutions = ' + repr([solution]) + '\n')
        self.run('dependencies', [depot / 'gclient', 'sync', '--nohooks', '--no-history', '--jobs=4'], workspace)
        self.run('cef-patches', [sys.executable, source / 'cef/tools/patcher.py'], source / 'cef')
        runtime = json.loads((ENGINE / 'cef-runtime-patches.json').read_text())
        for entry in runtime['inputs']:
            if digest(source / entry['path']) != entry['cefPatchedSha256']:
                raise RuntimeError('Unexpected CEF RNG repair input: ' + entry['path'])
        self.run('rng-repair-check', ['git', 'apply', '--check', ENGINE / runtime['patch']], source)
        self.run('rng-repair', ['git', 'apply', ENGINE / runtime['patch']], source)
        for entry in runtime['inputs']:
            if digest(source / entry['path']) != entry['fixedSha256']:
                raise RuntimeError('RNG repair output mismatch')
        patches = [('canvas', 'canvas'), ('worker_gpu', 'worker-gpu'), ('webgpu_pixel', 'webgpu-pixel')]
        if (ENGINE / 'identity-patch-lock.json').is_file():
            patches.append(('identity', 'identity'))
        locks = []
        for script, name in patches:
            self.run(name + '-patch', [sys.executable, ENGINE / ('apply_' + script + '_patch.py'), '--source-root', source])
            locks.append(json.loads((ENGINE / (name + '-patch-lock.json')).read_text()))
        verify_chain(source, locks)
        self.run('hooks', [depot / 'gclient', 'runhooks'], workspace)
        self.run('cef-version', [sys.executable, source / 'cef/tools/version_manager.py', '-u', '--fast-check'], source / 'cef')
        out = source / 'out/Release_GN_arm64'
        out.mkdir(parents=True, exist_ok=True)
        spec = importlib.util.spec_from_file_location('cef_gn_args', source / 'cef/tools/gn_args.py')
        gn = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gn)
        args = dict(is_official_build=False, is_component_build=False, symbol_level=0,
                    blink_symbol_level=0, v8_symbol_level=0, use_system_xcode=True,
                    use_remoteexec=False, use_siso=False, use_thin_lto=False,
                    enable_precompiled_headers=False, angle_precompile_internal_metal_shaders=False,
                    concurrent_links=1)
        if shutil.which('ccache'):
            args['cc_wrapper'] = shutil.which('ccache')
        # Runtime Metal stays enabled and tested, matching the verified local path.
        config = gn.GetAllPlatformConfigs(args)['Release_GN_arm64']
        (out / 'args.gn').write_text(gn.GetConfigFileContents(config) + '\n')
        self.run('gn', [source / 'buildtools/mac/gn', 'gen', out, '--root=' + str(source)], source)
        (self.logs / 'args.gn').write_text((out / 'args.gn').read_text())
        receipt = {**lock, 'gitSha': os.environ.get('GITHUB_SHA'),
                   'patchLocks': {name + '-patch-lock.json': digest(ENGINE / (name + '-patch-lock.json')) for _, name in patches},
                   'freeBytesBeforeCompile': shutil.disk_usage(self.root).free}
        (self.logs / 'source-provenance.json').write_text(json.dumps(receipt, indent=2) + '\n')
        return source, out, locks

    def build(self, jobs):
        source, out, locks = self.prepare()
        self.run('framework', [source / 'third_party/ninja/ninja', '-C', out, 'cef_framework', '-j' + str(jobs)], source)
        verify_chain(source, locks)
        self.run('sdk-template', [sys.executable, ENGINE / 'fetch_cef.py', '--cache-dir', self.root / 'sdk-template'])
        template_lock = json.loads((ENGINE / 'cef-lock.json').read_text())
        template = self.root / 'sdk-template' / template_lock['archive'].removesuffix('.tar.bz2')
        sdk = self.root / 'source-sdk'
        framework = 'Chromium Embedded Framework.framework'
        native = out / framework / 'Versions/A'
        shutil.copytree(template, sdk, ignore=shutil.ignore_patterns('Release', 'Debug', 'tests', 'cefclient.app', 'cefsimple.app'))
        shutil.copytree(native, sdk / 'Release' / framework, symlinks=True)
        refresh_sdk(source, out, sdk)
        for label, which_sdk in [('patched', sdk), ('baseline', template)]:
            build = self.root / (label + '-client')
            self.run(label + '-configure', ['cmake', '-S', ENGINE, '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release', '-DCEF_ROOT=' + str(which_sdk)])
            self.run(label + '-compile', ['cmake', '--build', build, '--parallel', str(jobs)])
            self.run(label + '-cpp-tests', ['ctest', '--test-dir', build, '--output-on-failure'])
        source_hash = digest(native / 'Chromium Embedded Framework')
        sdk_hash = digest(sdk / 'Release' / framework / 'Chromium Embedded Framework')
        embedded = self.root / 'patched-client/Release/CloakfoxChromium.app/Contents/Frameworks' / framework / 'Versions/A/Chromium Embedded Framework'
        embedded_hash = digest(embedded)
        if len({source_hash, sdk_hash, embedded_hash}) != 1:
            raise RuntimeError('Source/SDK/embedded framework hashes differ')
        receipt_path = self.logs / 'source-provenance.json'
        receipt = json.loads(receipt_path.read_text())
        receipt.update(sourceFrameworkSha256=source_hash, sdkFrameworkSha256=sdk_hash,
                       embeddedFrameworkSha256=embedded_hash, freeBytesAfterBuild=shutil.disk_usage(self.root).free)
        receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
        package = self.root / 'chromium-apps.tar.gz'
        self.run('package', ['tar', '-czf', package, '-C', self.root,
                            'patched-client/Release/CloakfoxChromium.app',
                            'baseline-client/Release/CloakfoxChromium.app'])
        (self.logs / 'chromium-apps.sha256').write_text(digest(package) + '  chromium-apps.tar.gz\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 8:
        parser.error('jobs must be 1–8')
    args.root.mkdir(parents=True, exist_ok=False)
    Pipeline(args.root.resolve()).build(args.jobs)


if __name__ == '__main__':
    main()
