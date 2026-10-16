"""Refresh mechanically auditable Gecko158 patch/pref/UI parity inputs.

Group coverage in feature-inventory.md is maintained by hand; this generator
updates only its marked appendix. Dynamic settings and API semantics still need
manual triage: collecting a name never claims that Chromium implements it.
"""
import hashlib
import json
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts._mixin import list_patches

START = '<!-- BEGIN GENERATED GECKO158 INVENTORY -->'
END = '<!-- END GENERATED GECKO158 INVENTORY -->'


def collect_inventory(root):
    root = Path(root)
    patches = [Path(path) for path in list_patches(str(root / 'patches'))]
    component = root / 'additions/browser/components/cloakfox'
    sources = sorted(path for path in component.rglob('*') if path.suffix in ('.mjs', '.js', '.html'))
    sources += [root / 'settings/cloakfox.cfg']
    preferences = set()
    bindings = set()
    for path in sources:
        text = path.read_text()
        preferences.update(re.findall(r'cloakfox\.(?:opt|webrtc)\.[A-Za-z_][\w.]*', text))
        preferences.update('cloakfox.opt.' + name for name in re.findall(r'\buserOpt\([\'"]([\w]+)[\'"]', text))
        if path.suffix == '.html':
            bindings.update(re.findall(r'(?:id|data-pref)=[\'"]([^\'"]+)[\'"]', text))
    inputs = patches + sources + [root / 'patches/order.txt', root / 'scripts/_mixin.py']
    return {
        'geckoVersion': '158.0',
        'patches': [str(path.relative_to(root)) for path in patches],
        'preferences': sorted(preferences),
        'settingsBindings': sorted(bindings),
        'actors': sorted(str(path.relative_to(root)) for path in component.glob('actors/*Child.sys.mjs')),
        'sourceSha256': {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs},
    }


def render_appendix(data):
    lines = [START, '## Active Gecko158 source inventory', '',
        f"Canonical patch resolver: {len(data['patches'])} active patches. These are rewrite/triage inputs, not a count of missing Chromium features. The source manifest records exact hashes and catches later source drift.", '',
        'Canvas/GPU/config entries have partial Chromium equivalents described above. Gecko UI, branding, build and compatibility patches can be engine-specific; no patch is mechanically applied to Chromium.', '']
    lines += [f'- `{path}`' for path in data['patches']]
    lines += ['', '## Optional/privacy preference inventory', '',
        'Literal cloakfox.opt / cloakfox.webrtc names plus dynamically constructed userOpt names from maintained158 modules, defaults and HTML. These are Gecko names; matching semantics remain pending unless the group table says otherwise.', '']
    lines += [f'- `{name}`' for name in data['preferences']]
    lines += ['', '## Settings surface inventory', '',
        'All id/data-pref bindings from component HTML, including secondary settings panels. This is a UI audit checklist; the Chromium companion does not expose the Gecko settings UI. Dynamic panels/API fields still require manual review.', '']
    lines += [f'- `{name}`' for name in data['settingsBindings']]
    lines += ['', '## Privileged actor inventory', '',
        'Gecko privileged actors are not installed in Chromium. Equivalent privacy behavior must use appropriate native Chromium hooks.', '']
    lines += [f'- `{path}`' for path in data['actors']]
    return '\n'.join(lines) + '\n' + END


def main():
    root = Path(__file__).resolve().parents[2]
    data = collect_inventory(root)
    directory = root / 'engines/chromium'
    (directory / 'gecko158-inventory.json').write_text(json.dumps(data, indent=2) + '\n')
    path = directory / 'feature-inventory.md'
    text = path.read_text()
    before, rest = text.split(START, 1)
    _, after = rest.split(END, 1)
    path.write_text(before + render_appendix(data) + after)
    print(f"Inventoried {len(data['patches'])} patches, {len(data['preferences'])} preferences, {len(data['settingsBindings'])} HTML bindings, {len(data['actors'])} actors")

if __name__ == '__main__': main()
