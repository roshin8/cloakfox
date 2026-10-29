"""Stage reviewed JS/data additions in the owned Firefox159 acceptance app only."""
import hashlib
import json
from pathlib import Path
import shutil

root=Path(__file__).resolve().parents[3]
base=root/'firefox-src/.tools159/acceptance-observed-gpu-defaults/Cloakfox.app'
app=root/'firefox-src/.tools159/acceptance-fpgen-personas/Cloakfox.app'
assert app.is_dir() and not any(p.is_symlink() for p in app.rglob('*'))
src=root/'additions/browser/components/cloakfox'
resources=app/'Contents/Resources/browser'
modules=['CloakfoxFPGenNetwork.sys.mjs','CloakfoxFPGenSampler.sys.mjs',
         'CloakfoxPersonas.sys.mjs','CloakfoxSeedSync.sys.mjs',
         'CloakfoxContainerWorkflows.sys.mjs','CloakfoxTemplates.sys.mjs',
         'CloakfoxInspector.sys.mjs']
content=['settings.html','settings.js','template-settings.js']
data=['fpgen-model-reference.zip','fpgen-model-source.json','fpgen-model-LICENSE.txt']
changed=[]
def stage(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
    changed.append({'source':str(source.relative_to(root)),'destination':str(target.relative_to(app)), 'sha256':digest})
for name in modules:stage(src/name,resources/'modules'/name)
for name in content:stage(src/'content'/name,resources/'chrome/browser/content/browser/cloakfox'/name)
# Data is also registered by moz.build for normal packaging.
for name in data:stage(src/name,resources/'modules'/name)
native={}
for name in ['Contents/MacOS/cloakfox','Contents/MacOS/XUL',
             'Contents/Resources/canonical-gpu/manifest.json',
             'Contents/Resources/canonical-gpu/libEGL_cloakfox_canonical.dylib',
             'Contents/Resources/canonical-gpu/libGLESv2_cloakfox_canonical.dylib',
             'Contents/Resources/canonical-gpu/libvk_swiftshader.dylib']:
    with (app/name).open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    with (base/name).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==digest
    native[name]=digest
(root/'docs/firefox-159/fpgen-personas/acceptance-app.json').write_text(json.dumps({
    'app':str(app),'base':str(base),'nativeFilesIdentical':native,'changedResources':changed, 'concurrentDependency':'CloakfoxInspector supplies the consistency confirmation imported by the concurrently edited settings UI; preserved unchanged'},indent=2)+'\n')
print(f'Staged {len(changed)} resources; {len(native)} native/backend files unchanged')
