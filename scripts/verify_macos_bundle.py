"""Reject Mozilla/appearance bundles at Cloakfox packaging boundaries."""
import plistlib
import sys
from pathlib import Path


def verify_bundle(app):
    app = Path(app)
    if app.name != 'Cloakfox.app' or app.is_symlink():
        raise ValueError('Only a Cloakfox.app bundle may be packaged')
    resources = app / 'Contents/Resources'
    with (app / 'Contents/Info.plist').open('rb') as source:
        info = plistlib.load(source)
    if (info.get('CFBundleIdentifier') != 'org.mozilla.cloakfox' or
            info.get('CFBundleExecutable') != 'cloakfox' or
            info.get('CFBundleName') != 'Cloakfox' or
            any((resources / name).exists() for name in
                ['cloakfox-appearance.json', 'cloakfox-profile.ini'])):
        raise ValueError('Refusing to package a Mozilla or appearance-mode app as Cloakfox')


if __name__ == '__main__':
    verify_bundle(sys.argv[1])
