"""Validate complete shipped patches, including no-newline file boundaries.

Section-only replay can report success while an unterminated checksum line
swallows the following file header. Validate the whole stream before building.
"""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from _mixin import list_patches

HEADER = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')


def validate_patch(text):
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        match = HEADER.match(lines[index])
        if not match:
            index += 1
            continue
        old = int(match[2]) if match[2] is not None else 1
        new = int(match[4]) if match[4] is not None else 1
        index += 1
        while old or new:
            if index >= len(lines):
                raise ValueError('Unterminated hunk at end of patch')
            line = lines[index]
            if line.startswith('--- a/') and index + 1 < len(lines) and lines[index + 1].startswith('+++ b/'):
                raise ValueError('File header inside unfinished hunk')
            if line == r'\ No newline at end of file':
                index += 1
                continue
            if line.startswith(' '):
                old -= 1
                new -= 1
            elif line.startswith('-'):
                old -= 1
            elif line.startswith('+'):
                new -= 1
            else:
                raise ValueError('Missing unified diff line prefix')
            if old < 0 or new < 0:
                raise ValueError('Hunk line counts do not match patch')
            index += 1


class PatchSyntax(unittest.TestCase):
    def test_complete_shipped_patch_streams(self):
        for path in list_patches(str(ROOT / 'patches')):
            with self.subTest(patch=Path(path).name):
                validate_patch(Path(path).read_text())

    def test_unterminated_checksum_before_next_file_is_rejected(self):
        malformed = '--- a/checksum\n+++ b/checksum\n@@ -1 +1 @@\n-old+new\n--- a/next\n+++ b/next\n@@ -1 +1 @@\n-x\n+y\n'
        with self.assertRaises(ValueError):
            validate_patch(malformed)

    def test_explicit_no_newline_metadata_preserves_next_header(self):
        valid = '--- a/checksum\n+++ b/checksum\n@@ -1 +1 @@\n-old\n\\ No newline at end of file\n+new\n\\ No newline at end of file\n--- a/next\n+++ b/next\n@@ -1 +1 @@\n-x\n+y\n'
        validate_patch(valid)
