# Firefox 155 local macOS toolchain diagnosis

The initial build failed in upstream `mozglue/misc/PerfStats.h` because
`std::atomic<double>` had no `fetch_add` member. This was a local standard-library
header mismatch, not a ported patch defect.

## Evidence

The configure log and generated compilation database selected:

```text
/usr/bin/clang++
-isysroot /Library/Developer/CommandLineTools/SDKs/MacOSX26.sdk
-mmacosx-version-min=11.0 -stdlib=libc++ -std=gnu++20
--target=arm64-apple-darwin
```

`/usr/bin/clang++ --version` reported Apple clang 21.0.0. However,
`obj-aarch64-apple-darwin/mozglue/misc/.deps/PerfStats.o.pp` showed that the
compiler actually loaded `<atomic>` and `__config` from:

```text
/Library/Developer/CommandLineTools/usr/include/c++/v1
```

Those headers report `_LIBCPP_VERSION 13000` and lack floating-point atomic
arithmetic. The SDK's headers report `_LIBCPP_VERSION 210106` and
`__cpp_lib_atomic_float 201711L`. Both configurations report
`__cplusplus 202002L`; changing the language-standard flag does not fix the
failure.

## Successful minimal checks

This exact read-only probe reproduces the failing selection and tests two
working alternatives. Run from any directory. Compilation uses standard input
and `-fsyntax-only`, so no test files are created.

```sh
python3 - <<'PY'
import subprocess

sdk = '/Library/Developer/CommandLineTools/SDKs/MacOSX26.sdk'
code = '''#include <atomic>
void probe() {
  std::atomic<double> x{0.0};
  x.fetch_add(1.0, std::memory_order_relaxed);
}
'''
base = [
    '-std=gnu++20', '-isysroot', sdk, '-mmacosx-version-min=11.0',
    '-stdlib=libc++', '--target=arm64-apple-darwin',
]
cases = [
    ('system default', '/usr/bin/clang++', []),
    ('system explicit SDK libc++', '/usr/bin/clang++',
     ['-nostdinc++', '-isystem', sdk + '/usr/include/c++/v1']),
    ('Mozilla clang19 default', '/Users/zeus/.mozbuild/clang/bin/clang++', []),
]
for name, compiler, extra in cases:
    result = subprocess.run(
        [compiler, *base, *extra, '-x', 'c++', '-fsyntax-only', '-'],
        input=code, text=True, capture_output=True,
    )
    print(name, 'exit', result.returncode)
    print(result.stderr)
    macros = subprocess.run(
        [compiler, *base, *extra, '-x', 'c++', '-dM', '-E', '-'],
        input='#include <atomic>\n', text=True, capture_output=True,
    )
    print('\n'.join(
        line for line in macros.stdout.splitlines()
        if line.startswith((
            '#define _LIBCPP_VERSION ', '#define __cplusplus ',
            '#define __cpp_lib_atomic_float ',
        ))
    ))
PY
```

Observed results:

| Selection | Result | libc++ version |
| --- | --- | --- |
| System clang, default include search | Fails: no `fetch_add` | 13000 |
| System clang, explicit SDK C++ headers | Passes | 210106 |
| Installed Mozilla clang 19.1.7, default include search | Passes | 210106 |

The installed Mozilla compiler is
`/Users/zeus/.mozbuild/clang/bin/clang++`, version 19.1.7. It selects the SDK C++
headers without extra include-path flags.

## Build configuration and required reconfigure

Use the existing Mozilla toolchain consistently in the local `mozconfig`:

```sh
export CC=/Users/zeus/.mozbuild/clang/bin/clang
export CXX=/Users/zeus/.mozbuild/clang/bin/clang++
export HOST_CC=/Users/zeus/.mozbuild/clang/bin/clang
export HOST_CXX=/Users/zeus/.mozbuild/clang/bin/clang++
```

Then rerun `./mach configure` before rebuilding. The earlier configure detected
libc++ 13 and generated `-D_LIBCPP_ENABLE_ASSERTIONS=1`. The SDK's libc++ rejects
that removed macro. Firefox's existing
`build/moz.configure/toolchain.configure` detects libc++ 19 or newer and selects
`-D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_EXTENSIVE` for this non-debug
build. Reconfiguration must update these generated flags; do not patch
`PerfStats.h` or hand-edit generated build files.

## Successful production PerfStats syntax check

This command was run from the compatibility worktree root. It reuses all
generated production flags, substitutes Mozilla clang 19, and models the
hardening flag that reconfiguration selects. It does not modify the compilation
database or any source/build file.

```sh
python3 - <<'PY'
import json
import shlex
import subprocess
from pathlib import Path

database = Path(
    'firefox-src/obj-aarch64-apple-darwin/clangd/compile_commands.json'
)
entries = json.loads(database.read_text())
entry = next(
    item for item in entries
    if item['file'].endswith('/mozglue/misc/PerfStats.cpp')
)
args = shlex.split(entry['command'])
args[0] = '/Users/zeus/.mozbuild/clang/bin/clang++'
args[args.index('-c')] = '-fsyntax-only'
output_index = args.index('-o')
del args[output_index:output_index + 2]
args = [
    arg.replace(
        '-D_LIBCPP_ENABLE_ASSERTIONS=1',
        '-D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_EXTENSIVE',
    )
    for arg in args
]
result = subprocess.run(
    args, cwd=entry['directory'], text=True, capture_output=True,
)
print('PerfStats production-flags syntax check:', result.returncode)
print(result.stderr)
raise SystemExit(result.returncode)
PY
```

Observed result: exit 0 with no diagnostics. Simply switching the compiler
while retaining the old generated assertions macro produced the expected
libc++ hardening error, confirming why reconfiguration is necessary.

These checks establish the cause and verify this translation unit. They do not
claim that a full Firefox build or runtime test has completed.

## Integrated build and CI follow-up

The full macOS build succeeded with Mozilla clang 19.1.7, SDK26 and isolated
cbindgen0.29.4 (`build-first-success.log`). The later native, actor, seed-startup,
and About dialog corrections were rebuilt successfully; the final `build.log`
records success with zero compiler warnings. All thirteen selected browser
probes and four HTTP/3 preference tests passed; see the main report for scope.

Firefox155 `build/moz.configure/toolchain.configure` requires clang19 or newer.
Both cbindgen pins in `.github/workflows/build.yml` now use0.29.4. Linux CI
installs LLVM19 and libclang19, and explicitly selects clang19 for target and
host C/C++ compilation. This prevents the older Ubuntu default compiler from
being selected after installing the newer version. Linux CI itself has not
been executed by this local macOS experiment.
