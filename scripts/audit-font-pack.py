"""Record/check exact shipped font bytes, embedded attribution and licenses.

Generation requires fontTools; --check uses the Python standard library only.
It never downloads/replaces fonts. Invoke after an intentional font-pack update.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'bundle/fonts'
MANIFEST = ROOT / 'font-manifest.json'

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def generate():
    from fontTools.ttLib import TTFont
    records=[]
    notices=[]
    for path in sorted((ROOT/'macos').glob('*.ttf')):
        with TTFont(path) as font:
            names=font['name']
            copyright=names.getDebugName(0)
            license_text=names.getDebugName(13)
            assert copyright and license_text, f'Missing attribution: {path}'
            if 'Bitstream Vera Fonts Copyright' in license_text:
                license_path=ROOT/'licenses'/f'{path.stem}-LICENSE.txt'
                license_path.write_text(license_text+'\n')
                license_id='Bitstream-Vera/Arev'
            elif 'SIL Open Font License' in license_text:
                license_path=ROOT/'licenses/OFL-1.1.txt'
                assert license_path.exists()
                license_id='OFL-1.1'
            else: raise ValueError(f'Unrecognized license in {path}')
            notices.append(f'{path.name}\nFamily alias: {names.getDebugName(1)}\n{copyright}\nLicense: {license_path.name}\n')
            records.append(dict(file=str(path.relative_to(ROOT)),sha256=digest(path),family=names.getDebugName(1),copyright=copyright,license=license_id,licenseFile=str(license_path.relative_to(ROOT))))
    (ROOT/'FONT-NOTICES.txt').write_text('\n'.join(notices))
    license_files=sorted((ROOT/'licenses').glob('*.txt'))
    data=dict(version=1,fonts=records,licenses=[dict(file=str(p.relative_to(ROOT)),sha256=digest(p)) for p in license_files],notices=[dict(file='FONT-NOTICES.txt',sha256=digest(ROOT/'FONT-NOTICES.txt'))])
    MANIFEST.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')

def check():
    data=json.loads(MANIFEST.read_text())
    actual={str(p.relative_to(ROOT)) for p in (ROOT/'macos').glob('*.ttf')}
    assert actual=={r['file'] for r in data['fonts']},'Font inventory differs from manifest'
    for record in data['fonts']+data['licenses']+data['notices']:
        assert digest(ROOT/record['file'])==record['sha256'],f"Hash mismatch: {record['file']}"
    for record in data['fonts']:
        assert (ROOT/record['licenseFile']).is_file(),record
    assert (ROOT/'FONT-NOTICES.txt').is_file()
    print(f"Verified {len(data['fonts'])} fonts and {len(data['licenses'])} license files")

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    if not args.check:generate()
    check()
