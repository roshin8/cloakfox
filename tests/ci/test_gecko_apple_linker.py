"""Exercise actual configure linker probe against old/new Apple diagnostics."""
from pathlib import Path
import os
import textwrap
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]


class AppleLinkerDetection(unittest.TestCase):
    def probe(self, responses, kernel='Darwin', linker='ld64'):
        path = ROOT / 'firefox-src/build/moz.configure/toolchain.configure'
        if not path.exists():
            self.skipTest('Requires patched Firefox source')
        source = path.read_text()
        start = source.index('        def try_linker(linker):')
        end = source.index('\n        result = None', start)
        calls = []
        def command(*args, **kwargs):
            calls.append(args)
            return responses[len(calls) - 1]
        scope = dict(cmd_base=['clang'], version_check=['-Wl,--version'], toolchain_flags=[],
                     os=os, target=SimpleNamespace(kernel=kernel), namespace=SimpleNamespace,
                     is_valid_linker=lambda value: value in ('ld64','lld','bfd','gold'), get_cmd_output=command)
        exec(textwrap.dedent(source[start:end]), scope)
        return scope['try_linker'](linker), calls

    def test_old_logging_diagnostic_still_works_without_second_probe(self):
        result,calls=self.probe([(1,'','Logging ld64 options')])
        self.assertEqual(result.KIND,'ld64')
        self.assertEqual(len(calls),1)

    def test_new_apple_banner_is_identified_with_version_probe(self):
        result,calls=self.probe([(1,'','ld: unknown options: --version'),
            (1,'','@(#)PROGRAM:ld PROJECT:ld-27037.1\nBUILD today\nld: missing main')])
        self.assertIsNotNone(result)
        self.assertEqual(result.KIND,'ld64')
        self.assertIn('-Wl,-v',calls[1])
        self.assertEqual(result.LINKER_FLAG,['-fuse-ld=ld'])

    def test_unknown_output_and_failed_execution_are_not_authorized(self):
        for response in [(1,'','unknown linker'), (127,'','@(#)PROGRAM:ld PROJECT:ld-27037.1'),
                         (1,'','prefix @(#)PROGRAM:ld PROJECT:ld-27037.1'),
                         (1,'','@(#)PROGRAM:ld PROJECT:ld-..'),
                         (1,'','@(#)PROGRAM:ld PROJECT:ld-27037..1')]:
            with self.subTest(response=response):
                result,_=self.probe([(1,'','ld: unknown options: --version'),response])
                self.assertIsNone(result)

    def test_lld_and_non_darwin_failures_do_not_use_apple_fallback(self):
        for kernel,linker in [('Linux','ld64'),('Darwin','lld')]:
            result,calls=self.probe([(1,'','linker failed')],kernel=kernel,linker=linker)
            self.assertIsNone(result)
            self.assertEqual(len(calls),1)

    def test_darwin_lld_must_link_against_selected_sdk(self):
        result,calls=self.probe([(0,'LLD 22.1.3',''), (1,'','unknown SDK architecture')], linker='lld')
        self.assertIsNone(result)
        self.assertIn('-dynamiclib',calls[1])
        result,calls=self.probe([(0,'LLD 23.0',''), (0,'','')],linker='lld')
        self.assertEqual(result.KIND,'lld')
        self.assertEqual(len(calls),2)

    def test_non_darwin_lld_keeps_existing_version_probe(self):
        result,calls=self.probe([(0,'LLD 22.1.3','')],kernel='Linux',linker='lld')
        self.assertEqual(result.KIND,'lld')
        self.assertEqual(len(calls),1)
