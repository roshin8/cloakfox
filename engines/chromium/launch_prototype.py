"""Launch disposable Chrome-style windows. This is not a privacy-patched browser."""
import argparse
import contextlib
import json
import re
from pathlib import Path
import subprocess
import tempfile
import threading


def main():
    parser = argparse.ArgumentParser(description='Cloakfox Chromium development prototype; test keychain, no fingerprint protections')
    parser.add_argument('--binary', type=Path,
        default=Path(__file__).parent / 'build/Release/CloakfoxChromium.app/Contents/MacOS/CloakfoxChromium')
    parser.add_argument('--container', action='append', default=[])
    parser.add_argument('--url', default='about:blank')
    parser.add_argument('--profile-root', type=Path, help='Optional dedicated prototype root; never use a Firefox/Chrome user profile')
    args = parser.parse_args()
    if not args.binary.is_file():
        parser.error('Build the companion first; see engines/chromium/README.md')
    for container in args.container:
        if not re.fullmatch(r'[1-9][0-9]{0,9}', container) or int(container) > 2147483647:
            parser.error('Container IDs must be canonical integers 1–2147483647')
    with contextlib.ExitStack() as cleanup:
        if args.profile_root:
            root = args.profile_root.absolute()
            root.mkdir(mode=0o700, parents=True, exist_ok=True)
        else:
            root = Path(cleanup.enter_context(tempfile.TemporaryDirectory(prefix='cloakfox-chromium-preview-'))).resolve()
        process = subprocess.Popen([str(args.binary.resolve()), '--profile-root=' + str(root), '--test-keychain'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        try:
            first = process.stdout.readline()
            if not first:
                raise SystemExit('Companion failed to start; inspect the native error above')
            ready = json.loads(first)
            if ready.get('event') != 'ready':
                raise SystemExit('Unexpected startup response: ' + first)
            protection = ('partial native canvas protection; privacy parity incomplete'
                          if ready.get('canvasReadbackVersion') == 1
                          else 'fingerprint protection not implemented')
            print('Development prototype: Chromium ' + ready['chromiumVersion'] + '; ' + protection + '.', flush=True)
            for request_id, container in enumerate(args.container or ['1'], start=1):
                process.stdin.write(json.dumps({'version': 1, 'id': request_id, 'command': 'open', 'container': container, 'url': args.url}) + '\n')
            process.stdin.flush()
            rejected = []
            def drain():
                quitting = False
                for line in process.stdout:
                    data = json.loads(line)
                    if data.get('ok') is False:
                        rejected.append(data)
                        print(data, flush=True)
                        if not quitting:
                            quitting = True
                            process.stdin.write(json.dumps({'version': 1, 'id': len(args.container or ['1']) + 1, 'command': 'quit'}) + '\n')
                            process.stdin.flush()
            reader = threading.Thread(target=drain, daemon=True)
            reader.start()
            process.wait()
            reader.join(timeout=2)
            if rejected or process.returncode:
                raise SystemExit(f'Companion exited with code {process.returncode}; rejected requests: {len(rejected)}')
        except KeyboardInterrupt:
            process.stdin.close()
            process.wait(timeout=20)
        finally:
            if process.poll() is None:
                process.stdin.close()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=10)
            if not process.stdin.closed:
                process.stdin.close()
            process.stdout.close()


if __name__ == '__main__':
    main()
