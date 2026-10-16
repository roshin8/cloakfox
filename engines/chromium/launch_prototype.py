"""Launch disposable Chromium development windows with reported native capabilities."""
import argparse
import contextlib
import re
from pathlib import Path
import tempfile
import sys

# Support both `python -m ...` and the documented direct script invocation.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from engines.shared.persona_config import PersonaStore
from engines.chromium.controller import ChromiumController


def main():
    parser = argparse.ArgumentParser(description='Cloakfox Chromium development prototype; test keychain, partial native privacy only')
    parser.add_argument('--binary', type=Path,
        default=Path(__file__).parent / 'build/Release/CloakfoxChromium.app/Contents/MacOS/CloakfoxChromium')
    parser.add_argument('--container', action='append', default=[])
    parser.add_argument('--url', default='about:blank')
    parser.add_argument('--profile-root', type=Path, help='Optional dedicated prototype root; never use a Firefox/Chrome user profile')
    parser.add_argument('--disable-canvas-privacy', action='store_true', help='Disable canvas/WebGL readback protection and GPU identifier masking')
    parser.add_argument('--block-webgpu-readback', action='store_true', help='Deny WebGPU READ maps, including compute-result readback; requires native GPU privacy build')
    privacy = parser.add_mutually_exclusive_group()
    privacy.add_argument('--disable-privacy', dest='privacy_enabled', action='store_false')
    privacy.add_argument('--enable-privacy', dest='privacy_enabled', action='store_true')
    parser.set_defaults(privacy_enabled=None)
    parser.add_argument('--regenerate-persona', action='store_true', help='Generate a new seed for the next context/session')
    parser.add_argument('--clear-overrides-when-generating', action='store_true', help='Clear explicit overrides with persona regeneration')
    args = parser.parse_args()
    if args.clear_overrides_when_generating and not args.regenerate_persona:
        parser.error('--clear-overrides-when-generating requires --regenerate-persona')
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
        store = PersonaStore(root / 'personas')
        with ChromiumController(args.binary, root, store=store) as controller:
            ready = controller.ready
            print('Development prototype: Chromium ' + ready['chromiumVersion'] +
                  '; shared config, partial native privacy; parity incomplete.', flush=True)
            try:
                for container in args.container or ['1']:
                    snapshot = store.get(container, 'chromium')
                    overrides = snapshot['persona']['overrides'].copy()
                    if args.disable_canvas_privacy:
                        overrides['canvas'] = False
                    if args.block_webgpu_readback:
                        overrides['blockWebGPUReadback'] = True
                    enabled = snapshot['enabled'] if args.privacy_enabled is None else args.privacy_enabled
                    if enabled != snapshot['enabled'] or overrides != snapshot['persona']['overrides']:
                        snapshot = store.update(snapshot, enabled=enabled, overrides=overrides)
                    if args.regenerate_persona:
                        snapshot = store.regenerate(snapshot, clear_overrides=args.clear_overrides_when_generating)
                    controller.open(snapshot, args.url)
                controller.wait()
            except KeyboardInterrupt:
                pass


if __name__ == '__main__':
    main()
