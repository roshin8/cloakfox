import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

// Execute the actual self-contained GPU table emitter, without Gecko imports.
const source = fs.readFileSync(new URL('../../additions/browser/components/cloakfox/CloakfoxPersonas.sys.mjs', import.meta.url), 'utf8');
const begin = source.indexOf('const GL =');
const end = source.indexOf('\n}', source.indexOf('export function fillWebGLKeys', begin)) + 2;
const context = vm.createContext({});
vm.runInContext(source.slice(begin, end).replace('export function', 'function'), context);

test('every GPU class emits WebGL2 limits without exposing them on WebGL1', () => {
  for (const renderer of ['NVIDIA GTX 980', 'AMD Radeon', 'Intel UHD', 'Apple M1', 'Generic GPU']) {
    const keys = {};
    context.fillWebGLKeys(keys, renderer);
    for (const [pname, value] of Object.entries({35375:24, 35380:256, 32883:2048, 35071:256})) {
      assert.equal(keys['webGl2:parameters'][pname], value, renderer + ':' + pname);
      assert.equal(keys['webGl:parameters'][pname], undefined);
    }
  }
});
