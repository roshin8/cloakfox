#!/usr/bin/env python3

"""
Common functions used across the Cloakfox build system.
Not meant to be called directly.
"""

import contextlib
import fnmatch
import optparse
import os
import re
import sys
import time

start_time = time.time()


@contextlib.contextmanager
def temp_cd(path):
    """Temporarily change to a different working directory"""
    _old_cwd = os.getcwd()
    abs_path = os.path.abspath(path)
    assert os.path.exists(abs_path), f'{abs_path} does not exist.'
    os.chdir(abs_path)

    try:
        yield
    finally:
        os.chdir(_old_cwd)


def get_options():
    """Get options"""
    parser = optparse.OptionParser()
    parser.add_option('--mozconfig-only', dest='mozconfig_only', default=False, action="store_true")
    parser.add_option(
        '-P', '--no-settings-pane', dest='settings_pane', default=True, action="store_false"
    )
    return parser.parse_args()


def find_src_dir(root_dir='.', version=None, release=None):
    """Get the source directory"""
    if version and release:
        name = os.path.join(root_dir, f'cloakfox-{version}-{release}')
        if os.path.exists(name):
            return name
    # Also check for firefox-src (Cloakfox's source dir name)
    cloakfox_name = os.path.join(root_dir, 'firefox-src')
    if os.path.exists(cloakfox_name):
        return cloakfox_name
    folders = os.listdir(root_dir)
    for folder in folders:
        if os.path.isdir(folder) and folder.startswith('cloakfox-'):
            return os.path.join(root_dir, folder)
    raise FileNotFoundError('No source directory found')


def get_moz_target(target, arch):
    """Get moz_target from target and arch"""
    if target == "linux":
        return "aarch64-unknown-linux-gnu" if arch == "arm64" else f"{arch}-pc-linux-gnu"
    if target == "windows":
        return f"{arch}-pc-mingw32"
    if target == "macos":
        return "aarch64-apple-darwin" if arch == "arm64" else f"{arch}-apple-darwin"
    raise ValueError(f"Unsupported target: {target}")


def list_files(root_dir, suffix):
    """List files in a directory"""
    for root, _, files in os.walk(root_dir):
        for file in fnmatch.filter(files, suffix):
            full_path = os.path.join(root, file)
            relative_path = os.path.relpath(full_path, root_dir)
            yield os.path.join(root_dir, relative_path).replace('\\', '/')


def list_patches(root_dir='../patches', suffix='*.patch'):
    """List all patch files, respecting order.txt if it exists.

    If patches/order.txt exists, patches are applied in that order.
    Any patches not listed in order.txt are appended at the end (alphabetically).
    Lines starting with # are comments. Blank lines are ignored.
    """
    all_patches = {os.path.basename(p): p for p in list_files(root_dir, suffix)}
    order_file = os.path.join(root_dir, 'order.txt')

    if os.path.exists(order_file):
        ordered = []
        with open(order_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line in all_patches:
                    ordered.append(all_patches.pop(line))
        # Append any remaining patches not in order.txt (alphabetically)
        ordered.extend(sorted(all_patches.values(), key=os.path.basename))
        return ordered

    return sorted(all_patches.values(), key=os.path.basename)

def is_bootstrap_patch(name):
    return bool(re.match(r'\d+\-.*', os.path.basename(name)))


def script_exit(statuscode):
    """Exit the script"""
    if (time.time() - start_time) > 60:
        # print elapsed time
        elapsed = time.strftime("%H:%M:%S", time.gmtime(time.time() - start_time))
        print(f"\n\aElapsed time: {elapsed}")
        sys.stdout.flush()

    sys.exit(statuscode)


def run(cmd, exit_on_fail=True, do_print=True):
    """Run a command"""
    if not cmd:
        return
    if do_print:
        print(cmd)
        sys.stdout.flush()
    retval = os.system(cmd)
    if retval != 0 and exit_on_fail:
        print(f"fatal error: command '{cmd}' failed")
        sys.stdout.flush()
        script_exit(1)
    return retval


def patch(patchfile, reverse=False, silent=False):
    """Run a patch file"""
    if reverse:
        cmd = f"patch -p1 -R -i {patchfile}"
    else:
        cmd = f"patch -p1 -i {patchfile}"
    if silent:
        cmd += ' > /dev/null'
    else:
        print(f"\n*** -> {cmd}")
    sys.stdout.flush()
    run(cmd)


__all__ = [
    'get_moz_target',
    'list_patches',
    'patch',
    'run',
    'script_exit',
    'temp_cd',
    'get_options',
]


if __name__ == '__main__':
    print('This is a module, not meant to be called directly.')
    sys.exit(1)
