"""Required Mac integration fixture, run after installing Ninja and Xcode tools."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f'scripts/ci/{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    checkpoint = load('chromium_checkpoint')
    host = load('chromium_host_identity')
    with tempfile.TemporaryDirectory(prefix='chromium-handoff-fixture-') as folder:
        base = Path(folder)
        sdk = base / 'sdk'
        sdk.mkdir()
        (sdk / 'header.h').write_text('fixture SDK')
        identity = {'identityVersion': 2, 'gitSha': 'fixture', 'hostBuildInputs': host.tree_identity(sdk)}
        root = base / 'workspace'
        root.mkdir()
        (root / 'source.c').write_text('int checkpoint_value(void) { return 42; }\n')
        (root / 'build.ninja').write_text('rule cc\n  command = clang -c source.c -o compiled.o\nbuild compiled.o: cc source.c\n')
        subprocess.run(['ninja', '-C', str(root)], check=True)
        obj = root / 'compiled.o'
        original, stamp = obj.read_bytes(), obj.stat().st_mtime_ns
        archive = base / 'checkpoint/workspace.tar.gz'
        checkpoint.save(root, archive, identity, provenance={'runnerImage': 'fixture-image-A'})
        shutil.rmtree(root)  # Only the fixture-owned temporary workspace.
        checkpoint.restore(root, archive, identity)
        result = subprocess.check_output(['ninja', '-C', str(root)], text=True)
        if 'no work to do' not in result or obj.read_bytes() != original or obj.stat().st_mtime_ns != stamp:
            raise RuntimeError('Checkpoint failed actual Ninja object reuse')
        print('PASS: real Ninja resumed identical objects and timestamps without recompilation; image is provenance')
        # Exercise real Mach-O LC_RPATH inheritance and LC_ID_DYLIB handling.
        native = base / 'python-runtime'
        native.mkdir()
        dependencies = base / 'external-libraries'
        dependencies.mkdir()
        (native / 'inner.c').write_text('int inner(void) { return 42; }\n')
        (native / 'outer.c').write_text('extern int inner(void); int outer(void) { return inner(); }\n')
        (native / 'main.c').write_text('extern int outer(void); int main(void) { return outer() != 42; }\n')
        inner, outer = dependencies / 'libinner.dylib', dependencies / 'libouter.dylib'
        subprocess.run(['clang', '-dynamiclib', str(native / 'inner.c'), '-Wl,-install_name,@rpath/libinner.dylib', '-o', str(inner)], check=True)
        subprocess.run(['clang', '-dynamiclib', str(native / 'outer.c'), '-L' + str(dependencies), '-linner',
                        '-Wl,-install_name,@rpath/libouter.dylib', '-o', str(outer)], check=True)
        executable = native / 'python3-fixture'
        subprocess.run(['clang', str(native / 'main.c'), '-L' + str(dependencies), '-louter',
                        '-Wl,-rpath,' + str(dependencies), '-o', str(executable)], check=True)
        before = host.python_dependencies(native, executable)
        if set(before) != {str(inner.resolve()), str(outer.resolve())}:
            raise RuntimeError('External Mach-O dependency closure is incomplete')
        with inner.open('ab') as stream:
            stream.write(b'changed linked library bytes')
        if host.python_dependencies(native, executable) == before:
            raise RuntimeError('Changed external Mach-O dependency was not detected')
        print('PASS: real Mach-O external dependency closure detects changed library bytes')


if __name__ == '__main__':
    main()
