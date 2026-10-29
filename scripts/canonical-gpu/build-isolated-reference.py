#!/usr/bin/env python3
"""Build an owned backend tree with two jobs and an own-process disk guard.

Source acquisition is deliberately separate. Never invoke this with a shared or
Chromium tree: the only permitted root is this worktree's .tools159 directory.
Logs and partial objects are preserved after every failure.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import signal
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
RESERVE = 2 * 1024**3

def build(angle: Path) -> None:
    owned = ROOT / '.tools159'
    angle = angle.resolve()
    if not angle.is_relative_to(owned.resolve()) or angle.is_symlink():
        raise ValueError('backend source must be an owned .tools159 tree')
    target = angle / 'out/Canonical'
    commands = [
        [str(angle / 'buildtools/mac/gn'), 'gen', str(target), '--root=' + str(angle)],
        ['ninja', '-C', str(target), '-j2', 'libEGL', 'libGLESv2'],
    ]
    for index, command in enumerate(commands):
        if shutil.disk_usage(owned).free < RESERVE:
            raise RuntimeError('less than 2 GiB free; retained all backend checkpoints')
        with (angle.parent / f'reference-build-{index}.log').open('a') as log:
            child = subprocess.Popen(['nice', '-n', '15', *command], cwd=angle,
                                     stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            while child.poll() is None:
                if shutil.disk_usage(owned).free < RESERVE:
                    # start_new_session makes this exactly our child group.
                    os.killpg(child.pid, signal.SIGTERM)
                    child.wait()
                    raise RuntimeError('own backend build stopped at 2 GiB reserve; objects retained')
                time.sleep(2)
            if child.returncode:
                raise subprocess.CalledProcessError(child.returncode, command)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('angle', type=Path)
    build(parser.parse_args().angle)
