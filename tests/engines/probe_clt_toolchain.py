"""Isolated GN configuration + native compile probe; NOT a full CEF build.

The real pinned mac_sdk.gni is tested with minimal surrounding GN configuration.
Unrelated Chromium imports are explicit fixtures; sdk_info.py/find_sdk.py remain
unmodified pinned upstream files for the default-Xcode negative control.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).parents[2]


def run(command, cwd=None):
    result = subprocess.run([str(x) for x in command], cwd=cwd, capture_output=True,
                            text=True, timeout=45)
    return {'command': [str(x) for x in command], 'exitCode': result.returncode,
            'stdout': result.stdout, 'stderr': result.stderr}


def probe(gn, upstream):
    report = {'scope': 'isolated GN configuration and Cocoa/Metal compilation, not full Chromium/CEF',
              'gnVersion': run([gn, '--version'])['stdout'].strip(), 'checks': {}}
    with tempfile.TemporaryDirectory(prefix='cloakfox-clt-gn-') as temp:
        root = Path(temp)
        for path in ['build/config/mac/mac_sdk.gni', 'build/config/apple/sdk_info.py', 'build/mac/find_sdk.py']:
            destination = root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(upstream / path, destination)
        prepared = run([sys.executable, ROOT / 'engines/chromium/prepare_clt_build.py', '--source-root', root])
        assert prepared['exitCode'] == 0, prepared
        # Deliberately minimal imports: this measures the actual patched GN
        # branch, not the rest of Chromium's build graph or target dependencies.
        for path in ['build/config/chrome_build.gni', 'build/config/gclient_args.gni',
                     'build/toolchain/rbe.gni', 'build/toolchain/siso.gni',
                     'build/toolchain/toolchain.gni', 'build_overrides/build.gni']:
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('')
        (root / 'build/config/mac/mac_sdk_overrides.gni').write_text('declare_args() { mac_sdk_min = "15" }\n')
        (root / '.gn').write_text('buildconfig = "//BUILDCONFIG.gn"\nscript_executable = ' + json.dumps(sys.executable) + '\n')
        (root / 'BUILDCONFIG.gn').write_text('''declare_args() {
  use_system_xcode = true
  is_official_build = false
  is_chrome_branded = false
}
set_default_toolchain("//:host")
''')
        (root / 'BUILD.gn').write_text('''import("//build/config/mac/mac_sdk.gni")
write_file("$root_build_dir/discovered.txt", [mac_sdk_path, mac_bin_path, mac_sdk_version, xcode_build])
toolchain("host") {
  tool("stamp") { command = "touch {{output}}" }
}
group("smoke") {}
''')
        clt = run([gn, 'gen', 'out/clt', '--args=mac_use_command_line_tools=true'], root)
        report['checks']['cltGnGeneration'] = clt
        assert clt['exitCode'] == 0, clt
        sdk, binary, version, label = (root / 'out/clt/discovered.txt').read_text().splitlines()
        assert label.startswith('CLT-'), label
        report['discovered'] = {'sdk': sdk, 'binaryDirectory': binary, 'sdkVersion': version,
                                'toolsetBuild': label}
        denied = run([gn, 'gen', 'out/official', '--args=mac_use_command_line_tools=true is_official_build=true'], root)
        report['checks']['officialCltRejected'] = denied
        assert denied['exitCode'] != 0 and 'CLT mode is only supported' in denied['stdout'], denied
        too_old = run([gn, 'gen', 'out/sdk-too-old', '--args=mac_use_command_line_tools=true mac_sdk_min="999.0"'], root)
        report['checks']['insufficientSdkRejected'] = too_old
        override = run([gn, 'gen', 'out/override', '--args=mac_use_command_line_tools=true mac_sdk_path="/unsupported/custom.sdk"'], root)
        report['checks']['unsupportedSdkOverrideRejected'] = override
        assert override['exitCode'] != 0 and 'CLT mode does not support mac_sdk_path overrides' in override['stdout'], override
        assert too_old['exitCode'] != 0 and 'SDK is older than required minimum' in too_old['stdout'], too_old
        default = run([gn, 'gen', 'out/default'], root)
        report['checks']['defaultXcodeMode'] = default
        # On this CLT-only machine the unmodified path must still fail rather
        # than quietly opting into the experimental configuration.
        if subprocess.run(['xcodebuild', '-version'], capture_output=True).returncode:
            assert default['exitCode'] != 0 and 'xcodebuild' in default['stdout'], default
        source = root / 'smoke.mm'
        source.write_text('#import <Cocoa/Cocoa.h>\n#import <Metal/Metal.h>\n#include <cstdio>\nint main() { @autoreleasepool { if (![NSObject new]) return 1; std::puts(MTLCreateSystemDefaultDevice() ? "Cocoa+Metal OK; GPU available" : "Cocoa+Metal OK; no GPU"); } return 0; }\n')
        compiled = run([Path(binary) / 'clang++', '-isysroot', sdk, '-framework', 'Cocoa',
                        '-framework', 'Metal', source, '-o', root / 'smoke'])
        report['checks']['nativeCompileUsingGnPaths'] = compiled
        assert compiled['exitCode'] == 0, compiled
        executed = run([root / 'smoke'])
        report['checks']['nativeExecution'] = executed
        assert executed['exitCode'] == 0, executed
        report['resourceTools'] = {name: run(['xcrun', '--find', name])['exitCode'] == 0
                                   for name in ('ibtool', 'actool', 'metal', 'momc')}
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gn', type=Path, required=True)
    parser.add_argument('--upstream-root', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = probe(args.gn.resolve(strict=True), args.upstream_root.resolve(strict=True))
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: opt-in GN configuration and native Cocoa/Metal compilation; full CEF build unverified')
