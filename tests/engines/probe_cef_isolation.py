"""Owned loopback probe. Cross-container persistence or an engine crash fails it."""
import argparse
import ctypes
import http.server
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time


class Companion:
    def __init__(self, binary, root, quic_port=None):
        self.log = tempfile.TemporaryFile(mode="w+")
        arguments = [str(binary), "--profile-root=" + str(root), "--enable-probe", "--test-keychain"]
        if quic_port is not None:
            arguments.append("--test-quic-port=" + str(quic_port))
        self.process = subprocess.Popen(
            arguments,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
            text=True, bufsize=1,
        )
        self.messages = queue.Queue()
        self.serial = 0
        def reader():
            for line in self.process.stdout:
                try:
                    self.messages.put(json.loads(line))
                except json.JSONDecodeError:
                    self.messages.put({"event": "bad-output", "line": line})
            self.messages.put({"event": "eof"})
        threading.Thread(target=reader, daemon=True).start()
        try:
            self.ready = self.wait(lambda x: x.get("event") == "ready")
        except BaseException:
            self.process.terminate()
            self.process.wait(timeout=10)
            self.process.stdin.close()
            self.process.stdout.close()
            self.log.close()
            raise

    def wait(self, match, timeout=30, allow_crash=False):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                value = self.messages.get(timeout=min(1, end-time.monotonic()))
            except queue.Empty:
                continue
            if value.get("event") in ("eof", "bad-output") or (value.get("event") == "crashed" and not allow_crash):
                self.log.seek(0)
                raise AssertionError(str(value) + "\n" + self.log.read()[-4000:])
            if match(value):
                return value
        raise TimeoutError("Companion reply timed out")

    def rpc(self, command, **args):
        self.serial += 1
        request = {"version": 1, "id": self.serial, "command": command, **args}
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        return self.wait(lambda x: x.get("id") == self.serial)

    def open(self, container, url, private=False, configRevision=None):
        revision = {} if configRevision is None else {"configRevision": configRevision}
        response = self.rpc("open", container=container, url=url, private=private, **revision)
        assert response["ok"], response
        browser = response["browser"]
        end = time.monotonic() + 20
        while time.monotonic() < end:
            result = self.evaluate(browser, "document.readyState + ':' + location.href")
            if result == "complete:" + url:
                return browser
            time.sleep(.05)
        raise TimeoutError("Navigation did not complete: " + str(result))

    def evaluate(self, browser, expression):
        response = self.rpc("cdp", browser=browser, method="Runtime.evaluate",
                            params={"expression": expression, "awaitPromise": True,
                                    "returnByValue": True})
        assert response["ok"], response
        result = response["result"]
        assert "exceptionDetails" not in result, result
        return result["result"].get("value")

    def close(self):
        failure = None
        if self.process.poll() is None:
            try:
                self.rpc("quit")
                self.process.wait(timeout=20)
            except (BrokenPipeError, TimeoutError, AssertionError) as error:
                failure = error
                self.process.terminate()
                self.process.wait(timeout=10)
        self.process.stdin.close()
        self.process.stdout.close()
        self.log.seek(0)
        diagnostic = self.log.read()[-2000:]
        self.log.close()
        assert failure is None and self.process.returncode == 0, (failure, self.process.returncode, diagnostic)


def check_sandbox(process):
    """Actual macOS seatbelt policy, with the unsandboxed parent as control."""
    sandbox = ctypes.CDLL("/usr/lib/libsandbox.dylib")
    sandbox.sandbox_check.restype = ctypes.c_int
    sandbox.sandbox_check.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    path = os.fsencode(Path(__file__).resolve())
    filter_type = 1 | ctypes.c_int.in_dll(sandbox, "SANDBOX_CHECK_NO_REPORT").value
    # Use an existing writable file. sandbox_check denies nonexistent paths
    # even for an unsandboxed process, which is not an enforcement proof.
    assert sandbox.sandbox_check(process.pid, b"file-write-data", filter_type, ctypes.c_char_p(path)) == 0
    renderers = []
    for row in subprocess.check_output(["ps", "-axo", "pid,ppid,command"], text=True).splitlines():
        fields = row.strip().split(None, 2)
        if len(fields) == 3 and fields[1] == str(process.pid) and "--type=renderer " in fields[2]:
            pid = int(fields[0])
            assert sandbox.sandbox_check(pid, b"file-write-data", filter_type, ctypes.c_char_p(path)) == 1, (pid, "renderer sandbox not enforcing")
            renderers.append(pid)
    assert renderers, "No real renderer process observed"
    return {"rendererCount": len(renderers), "outsideProfileWriteDenied": True, "parentControlAllowed": True}


WRITE = """(async () => {
document.cookie='owner=A; Max-Age=3600; SameSite=Lax; Path=/';
localStorage.setItem('owner','A');
await new Promise((resolve,reject)=>{
  const request=indexedDB.open('probe',1);
  request.onupgradeneeded=()=>request.result.createObjectStore('values');
  request.onerror=()=>reject(request.error);
  request.onsuccess=()=>{const db=request.result;const tx=db.transaction('values','readwrite');
    tx.objectStore('values').put('A','owner');tx.oncomplete=()=>{db.close();resolve()};tx.onerror=()=>reject(tx.error)};
});
const cache=await caches.open('probe'); await cache.put('/owner',new Response('A'));
await navigator.serviceWorker.register('/sw.js');await navigator.serviceWorker.ready;
return true;
})()"""
READ = """(async () => {
let dbValue=null;
await new Promise((resolve,reject)=>{const request=indexedDB.open('probe',1);
 request.onupgradeneeded=()=>request.result.createObjectStore('values');
 request.onerror=()=>reject(request.error);request.onsuccess=()=>{const db=request.result;
 const tx=db.transaction('values');const read=tx.objectStore('values').get('owner');
 read.onsuccess=()=>dbValue=read.result??null;tx.oncomplete=()=>{db.close();resolve()};tx.onerror=()=>reject(tx.error)};});
const cache=await caches.open('probe');const response=await cache.match('/owner');
return {cookie:document.cookie,local:localStorage.getItem('owner'),db:dbValue,
 cache:response?await response.text():null,sw:(await navigator.serviceWorker.getRegistrations()).length};
})()"""
EMPTY = {"cookie": "", "local": None, "db": None, "cache": None, "sw": 0}
OWNED = {"cookie": "owner=A", "local": "A", "db": "A", "cache": "A", "sw": 1}


class Fixture(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = (b"self.addEventListener('install',()=>self.skipWaiting());"
                b"self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));"
                if self.path == "/sw.js" else b"<!doctype html><title>Cloakfox owned fixture</title><p>Container isolation fixture</p>")
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript" if self.path == "/sw.js" else "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def run(binary, root):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/"
    report = {"checks": [], "url": url}
    try:
        for phase in ("initial", "restart"):
            app = Companion(binary, root)
            try:
                report["backend"] = app.ready
                assert app.ready["engine"] == "chromium", app.ready
                assert not app.ready["privacyPatched"], "Binary-only prototype must report privacy unsupported"
                a = app.open("1", url)
                b = app.open("2", url)
                private = app.open("3", url, private=True)
                if phase == "initial":
                    assert app.evaluate(a, READ) == EMPTY
                    assert app.evaluate(a, WRITE) is True
                state = app.evaluate(a, READ)
                assert state == OWNED, (phase, "persistent A", state)
                state = app.evaluate(b, READ)
                assert state == EMPTY, (phase, "persistent B", state)
                state = app.evaluate(private, READ)
                assert state == EMPTY, (phase, "private", state)
                assert app.evaluate(private, WRITE) is True
                assert app.rpc("close", browser=private)["ok"]
                app.wait(lambda x: x.get("event") == "closed" and x.get("browser") == private)
                private = app.open("3", url, private=True)
                state = app.evaluate(private, READ)
                assert state == EMPTY, (phase, "private context survived last window close", state)
                report["checks"].append(phase + ": private storage cleared after last private window closes")
                report["checks"].append(phase + ": cookies/localStorage/IndexedDB/CacheStorage/service workers isolated")
                identity = app.evaluate(a, "({ua:navigator.userAgent,appVersion:navigator.appVersion,chrome:typeof chrome,firefox:typeof InstallTrigger,webgl:!!document.createElement('canvas').getContext('webgl2'),webgpu:!!navigator.gpu})")
                assert "Chrome/" in identity["ua"] and "Firefox/" not in identity["ua"], identity
                assert identity["firefox"] == "undefined", identity
                report["identity"] = identity
                graphics_browser = a
                if app.ready.get("webglPrivacyVersion", 0) > 0:
                    diagnostic = app.rpc("open", container="2147483646", url=url, privacy={"canvas":False})
                    assert diagnostic["ok"] and not diagnostic["canvasEnabled"], diagnostic
                    graphics_browser = app.open("2147483646", url)
                graphics = app.evaluate(graphics_browser, Path(__file__).with_name("webgl_render.js").read_text())
                assert graphics["pixel"] == [255, 0, 0, 255] and graphics["error"] == 0, graphics
                report["graphics"] = graphics
                report["checks"].append(phase + ": WebGL2 shaders compile and render the expected pixel")
                report["sandbox"] = check_sandbox(app.process)
                report["checks"].append(phase + ": actual macOS renderer sandbox enforced")
                media = app.evaluate(a, "navigator.mediaDevices.getUserMedia({audio:true,video:true}).then(()=> 'unexpected-allow',e=>e.name)")
                assert media == "NotAllowedError", media
                location = app.evaluate(a, "new Promise(resolve=>navigator.geolocation.getCurrentPosition(()=>resolve('unexpected-allow'),e=>resolve(e.code),{timeout:3000}))")
                assert location == 1, location
                report["checks"].append(phase + ": camera/microphone/location denied before hardware access")
                for container in ("../escape", "0", "01"):
                    response = app.rpc("open", container=container, url=url)
                    assert response["ok"] is False, response
                report["checks"].append(phase + ": malformed container IDs rejected")
            finally:
                app.close()
        assert not (root / "containers" / "3").exists(), "Private container must not create a persistent cache path"
        return report
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    assert args.binary.is_file(), f"Companion not built: {args.binary}"
    with tempfile.TemporaryDirectory(prefix="cloakfox-cef-probe-") as profile:
        report = run(args.binary.resolve(), Path(profile).resolve())
    output = json.dumps(report, indent=2)
    if args.report:
        args.report.write_text(output + "\n")
    print(output)
