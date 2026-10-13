"""Reject unsafe launch options, replayed messages and invalid navigation."""
import os
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from probe_cef_isolation import Companion


class ProtocolSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        value = os.environ.get("CLOAKFOX_CHROMIUM_BIN")
        if not value:
            raise unittest.SkipTest("Set CLOAKFOX_CHROMIUM_BIN to a built companion")
        cls.binary = Path(value).resolve()

    def setUp(self):
        self.profile = tempfile.TemporaryDirectory(prefix="cloakfox-protocol-")
        self.app = Companion(self.binary, Path(self.profile.name).resolve())

    def tearDown(self):
        self.app.close()
        self.profile.cleanup()

    def test_replayed_request_cannot_open_another_browser(self):
        first = self.app.rpc("open", container="1", url="about:blank")
        self.assertTrue(first["ok"])
        replay = {"version": 1, "id": self.app.serial, "command": "open", "container": "2", "url": "about:blank"}
        self.app.process.stdin.write(__import__('json').dumps(replay) + "\n")
        self.app.process.stdin.flush()
        result = self.app.wait(lambda x: x.get("id") == self.app.serial)
        self.assertFalse(result["ok"], result)

    def test_invalid_urls_and_envelopes_are_rejected(self):
        for url in ("javascript:alert(1)", "file:///etc/passwd", "chrome://settings", "not a URL"):
            self.assertFalse(self.app.rpc("open", container="1", url=url)["ok"])
        self.app.serial += 1
        self.app.process.stdin.write(__import__('json').dumps({"version": 2, "id": self.app.serial, "command": "open"}) + "\n")
        self.app.process.stdin.flush()
        self.assertFalse(self.app.wait(lambda x: x.get("id") == self.app.serial)["ok"])

    def test_unsupported_privacy_settings_are_not_silently_accepted(self):
        response = self.app.rpc("open", container="1", url="about:blank", privacy={"enabled": True})
        self.assertFalse(response["ok"], response)

    def test_quit_while_profile_is_initializing_is_orderly(self):
        with tempfile.TemporaryDirectory(prefix="cloakfox-pending-open-") as root:
            requests = '\n'.join((
                '{"version":1,"id":1,"command":"open","container":"1","url":"about:blank"}',
                '{"version":1,"id":2,"command":"quit"}', ''
            ))
            result = subprocess.run([str(self.binary), "--profile-root=" + root, "--test-keychain"],
                input=requests, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            replies = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertTrue(next(value for value in replies if value.get("id") == 2)["ok"])

    def test_unsafe_engine_flags_cannot_disable_protections(self):
        for flag in ("--no-sandbox", "--disable-web-security", "--remote-debugging-port=9222", "--ignore-certificate-errors", "--user-agent=pretend"):
            with tempfile.TemporaryDirectory(prefix="cloakfox-flags-") as root:
                process = subprocess.run([str(self.binary), "--profile-root=" + root, flag],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=15, text=True)
                self.assertEqual(process.returncode, 2, (flag, process.stdout, process.stderr))
                self.assertIn("Unsupported launch option", process.stderr)
                self.assertNotIn('"event":"ready"', process.stdout)

    def test_probe_api_is_disabled_without_explicit_flag(self):
        with tempfile.TemporaryDirectory(prefix="cloakfox-no-probe-") as root:
            requests = '\n'.join((
                '{"version":1,"id":1,"command":"cdp","browser":1,"method":"Runtime.evaluate","params":{"expression":"1"}}',
                '{"version":1,"id":2,"command":"quit"}', ''
            ))
            process = subprocess.run([str(self.binary), "--profile-root=" + root, "--test-keychain"],
                input=requests, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, text=True)
            values = [__import__('json').loads(line) for line in process.stdout.splitlines()]
            self.assertFalse(values[0]["probeEnabled"])
            self.assertFalse(next(v for v in values if v.get("id") == 1)["ok"])
            self.assertEqual(process.returncode, 0, process.stderr)

    def test_renderer_crash_does_not_kill_companion_and_navigation_recovers(self):
        opened = self.app.rpc("open", container="1", url="about:blank")
        browser = opened["browser"]
        self.app.evaluate(browser, "document.readyState")
        self.app.serial += 1
        self.app.process.stdin.write(json.dumps({"version": 1, "id": self.app.serial,
            "command": "cdp", "browser": browser, "method": "Page.crash", "params": {}}) + "\n")
        self.app.process.stdin.flush()
        crash = self.app.wait(lambda x: x.get("event") == "crashed", allow_crash=True)
        self.assertEqual(crash["browser"], browser)
        self.assertIsNone(self.app.process.poll())
        response = self.app.rpc("navigate", browser=browser, url="about:blank")
        self.assertTrue(response["ok"], response)
        self.assertIn(self.app.evaluate(browser, "document.readyState"), ("loading", "interactive", "complete"))


if __name__ == "__main__":
    unittest.main()
