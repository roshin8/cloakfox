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

test('uniform vector and component capacities describe the same storage', () => {
  for (const renderer of ['NVIDIA GTX 980', 'AMD Radeon', 'Intel UHD', 'Apple M1', 'Generic GPU']) {
    const keys = {};
    context.fillWebGLKeys(keys, renderer);
    const gl1 = keys['webGl:parameters'];
    const gl2 = keys['webGl2:parameters'];
    for (const [vectors, components] of [[36347, 35658], [36349, 35657]]) {
      assert.equal(gl1[vectors], gl2[vectors], renderer);
      assert.equal(gl2[vectors] * 4, gl2[components], renderer);
      assert.equal(gl1[components], undefined, 'WebGL2 component enums remain invalid on WebGL1');
    }
  }
});

test('varying vectors follow Gecko fragment-input capacity without expanding vertex outputs', () => {
  for (const renderer of ['NVIDIA GTX 980', 'AMD Radeon', 'Intel UHD', 'Apple M1', 'Generic GPU']) {
    const keys = {};
    context.fillWebGLKeys(keys, renderer);
    const gl2 = keys['webGl2:parameters'];
    assert.equal(gl2[36348] * 4, gl2[37157], renderer);
    assert.equal(gl2[37154], undefined, 'vertex outputs retain backend capacity');
    assert.equal(keys['webGl:parameters'][37157], undefined);
  }
});
