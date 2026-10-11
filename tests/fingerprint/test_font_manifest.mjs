import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const root=new URL('../../bundle/fonts/',import.meta.url);
test('all bundled font bytes have exact hashes, license text and attribution',async()=>{
 const manifest=JSON.parse(await readFile(new URL('font-manifest.json',root),'utf8'));
 const actual=(await readdir(new URL('macos/',root))).filter(f=>f.endsWith('.ttf')).map(f=>'macos/'+f).sort();
 assert.deepEqual(manifest.fonts.map(f=>f.file).sort(),actual);
 const licenses=new Set(manifest.licenses.map(r=>r.file));
 for(const font of manifest.fonts) {
  assert.ok(/copyright|©|\(c\)/i.test(font.copyright),font.file);
  assert.ok(licenses.has(font.licenseFile),font.file);
 }
 for(const record of [...manifest.fonts,...manifest.licenses,...manifest.notices]) {
  const bytes=await readFile(new URL(record.file,root));
  assert.equal(createHash('sha256').update(bytes).digest('hex'),record.sha256,record.file);
 }
});
