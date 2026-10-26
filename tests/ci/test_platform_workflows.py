"""Guard platform scheduling and release dependency boundaries."""
import pathlib
import re
import unittest

WORKFLOWS = pathlib.Path(__file__).resolve().parents[2] / '.github/workflows'


def jobs(name):
    text = (WORKFLOWS / name).read_text()
    body = text.split('\njobs:\n', 1)[1]
    starts = list(re.finditer(r'^  ([\w-]+):\n', body, re.M))
    return {m[1]: body[m.end():starts[i + 1].start() if i + 1 < len(starts) else len(body)]
            for i, m in enumerate(starts)}


class PlatformWorkflows(unittest.TestCase):
    def test_macos_tag_release_requires_only_macos_and_shared_checks(self):
        graph = jobs('build-macos.yml')
        release = graph['release']
        needs = re.search(r'^    needs: \[(.*?)\]', release, re.M)[1]
        self.assertEqual(set(needs.replace(' ', '').split(',')), {
            'build-macos', 'fingerprint-tests', 'unit-tests', 'chromium', 'dual-engine-tests'})
        self.assertNotIn('build-linux', graph)
        self.assertNotIn('fingerprint-tests-linux', graph)
        self.assertIn('draft: true', release)
        self.assertIn('scripts/release_security.py', release)

    def test_renderer_installs_pinned_auxiliary_tools_after_clang(self):
        job = jobs('gecko-engine.yml')['canonical-gpu-macos']
        clang = 'python3 "$RUNNER_TEMP/canonical-build/angle/tools/clang/scripts/update.py"'
        self.assertIn(clang + ' --package objdump', job)
        self.assertLess(job.index(clang + '\n'), job.index(clang + ' --package objdump'))
        for tool in ('clang++', 'llvm-otool', 'llvm-nm', 'llvm-strip', 'llvm-install-name-tool'):
            self.assertIn(tool, job)
        self.assertIn('test -x', job)

    def test_deferred_platforms_cannot_run_on_push_or_pr(self):
        for platform in ('linux', 'windows'):
            with self.subTest(platform=platform):
                text = (WORKFLOWS / f'build-{platform}.yml').read_text()
                triggers = text.split('\non:', 1)[1].split('\npermissions:', 1)[0]
                self.assertIn('workflow_dispatch:', triggers)
                self.assertNotRegex(triggers, r'(?m)^  (push|pull_request|schedule):')

    def test_shared_checks_are_reusable_and_linux_has_own_runtime_dependency(self):
        self.assertIn('uses: ./.github/workflows/checks.yml', jobs('build-macos.yml')['unit-tests'])
        self.assertIn('workflow_call:', (WORKFLOWS / 'checks.yml').read_text())
        linux = jobs('build-linux.yml')
        self.assertIn('needs: build-linux', linux['fingerprint-tests-linux'])
        self.assertNotIn('chromium', linux)

    def test_shared_checks_use_macos_while_linux_is_deferred(self):
        shared = jobs('checks.yml')['unit-tests']
        self.assertIn('runs-on: macos-26', shared)
        self.assertNotIn('ubuntu-', shared)
        self.assertIn('brew install zstd', shared)

    def test_current_apps_rebuild_and_runtime_gates_survive_engine_reuse(self):
        chromium = jobs('chromium.yml')
        self.assertIn('uses: ./.github/workflows/chromium-engine.yml', chromium['engine'])
        self.assertIn('scripts/ci/chromium_clients.py', chromium['clients'])
        self.assertIn('needs: engine', chromium['clients'])
        self.assertIn('needs: clients', chromium['runtime'])
        self.assertNotIn('if:', chromium['clients'].split('    steps:', 1)[0])
        for probe in ('probe_fingerprint_libraries.py', 'run_engine_tests.py', 'probe_cef_isolation.py', 'probe_cef_transport.py'):
            self.assertIn(probe, chromium['runtime'])
        for workflow, job in [('chromium.yml','clients'), ('gecko-engine.yml','gecko-engine-complete')]:
            self.assertIn('merge-multiple: true', jobs(workflow)[job])
        self.assertIn("needs.native-build.result == 'success'", jobs('gecko-engine.yml')['gecko-engine-complete'])
        self.assertIn('GECKO_BUILD_SHA', jobs('build-macos.yml')['fingerprint-tests'])

    def test_macos_preserves_existing_active_run_concurrency(self):
        text = (WORKFLOWS / 'build-macos.yml').read_text()
        self.assertIn('group: browser-build-Build Cloakfox-${{ github.ref }}', text)
        self.assertIn('cancel-in-progress: false', text)


if __name__ == '__main__':
    unittest.main()
