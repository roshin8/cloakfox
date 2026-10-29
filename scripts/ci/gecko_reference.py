"""Stage a verified stock Firefox reference privately; never install or launch it."""
import argparse,hashlib,json,plistlib,re,shutil,subprocess,sys
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen


def expected_digest(text,relative):
    records=[parts[0] for line in text.splitlines()
             if len(parts:=line.split(None,1))==2 and parts[1].lstrip('*')==relative]
    if len(records)!=1 or not re.fullmatch(r'[a-fA-F0-9]{128}',records[0]):
        raise ValueError('Expected exactly one valid official SHA512 record')
    return records[0].lower()


def stage_reference(version,output,fetch=urlopen):
    if not re.fullmatch(r'\d+\.\d+(?:\.\d+)?',version):raise ValueError('Invalid Firefox release version')
    output=Path(output).resolve();app=output/'Firefox.app';mount=output/'mount'
    if app.exists() or mount.exists():raise FileExistsError('Reference destination must be fresh; existing apps/checkpoints are retained')
    if output==Path('/Applications') or Path('/Applications') in output.parents:raise ValueError('Reference must stay outside Applications')
    output.mkdir(parents=True,exist_ok=True)
    base=f'https://archive.mozilla.org/pub/firefox/releases/{version}/'
    with fetch(base+'SHA512SUMS') as response:sums=response.read()
    (output/'SHA512SUMS').write_bytes(sums)
    relative=f'mac/en-US/Firefox {version}.dmg';expected=expected_digest(sums.decode(),relative)
    url=base+quote(relative,safe='/');archive=output/'reference.dmg';digest=hashlib.sha512()
    with fetch(url) as response,archive.open('xb') as target:
        while chunk:=response.read(1024*1024):target.write(chunk);digest.update(chunk)
    if digest.hexdigest()!=expected:raise ValueError('Stock Firefox archive SHA512 mismatch')
    subprocess.run(['hdiutil','attach',str(archive),'-readonly','-nobrowse','-mountpoint',str(mount)],check=True)
    try:
        source=mount/'Firefox.app'
        info=plistlib.loads((source/'Contents/Info.plist').read_bytes())
        if info.get('CFBundleIdentifier')!='org.mozilla.firefox' or info.get('CFBundleShortVersionString')!=version:
            raise ValueError('Unexpected stock Firefox bundle identity/version')
        subprocess.run(['codesign','--verify','--deep','--strict',str(source)],check=True)
        shutil.copytree(source,app,symlinks=False)
    finally:subprocess.run(['hdiutil','detach',str(mount)],check=True)
    subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
    (output/'reference.json').write_text(json.dumps({'version':version,'url':url,'sha512':expected,'signatureVerified':True,'installed':False},indent=2)+'\n')
    return app/'Contents/MacOS/firefox'


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--version',required=True);parser.add_argument('--output-dir',type=Path,required=True);args=parser.parse_args()
    if sys.platform!='darwin':parser.error('The DMG reference staging helper requires macOS')
    print(stage_reference(args.version,args.output_dir))
if __name__=='__main__':main()
