"""Assert actual runtime resources in a packaged app or loose development build."""
from contextlib import contextmanager
import os
from pathlib import Path
import zipfile


@contextmanager
def resource_inventory(root):
    archive = root / 'omni.ja'
    if archive.exists():
        with zipfile.ZipFile(archive) as reader:
            yield reader.namelist(), reader.read, 'archive'
    else:
        assert root.is_dir() and (root / 'chrome.manifest').is_file(), root
        # Development builds link chrome resource directories into dist/bin.
        entries = {}
        visited = set()
        for directory, children, files in os.walk(root, followlinks=True):
            resolved = Path(directory).resolve()
            if resolved in visited:
                children.clear()
                continue
            visited.add(resolved)
            for name in files:
                path = Path(directory) / name
                entries[str(path.relative_to(root))] = path
        assert entries, root
        yield list(entries), lambda name: entries[name].read_bytes(), 'loose'


def check_packaged_resources(binary):
    resources = Path(binary).parents[1] / 'Resources'
    with resource_inventory(resources) as (names, read, toolkit_layout):
        for suffix in ['html', 'js', 'css']:
            assert any(n.endswith('content/global/crashes.' + suffix) for n in names), suffix
    with resource_inventory(resources / 'browser') as (names, read, browser_layout):
        assert not any(n.endswith('browser-development-helpers.js') for n in names), 'obsolete helper shipped'
        main = next(n for n in names if n.endswith('content/browser/browser-main.js'))
        assert b'browser-development-helpers.js' not in read(main), 'helper startup call shipped'
        manifests = [n for n in names if n.endswith('.manifest')]
        assert manifests, 'no browser manifests found'
        assert all(b'DevelopmentHelpers.init' not in read(n) for n in manifests), 'helper category registration shipped'
    print(f'PASS: crash resources and development-helper removal (toolkit={toolkit_layout}, browser={browser_layout})')


if __name__ == '__main__':
    check_packaged_resources(os.environ['CLOAKFOX_BIN'])
