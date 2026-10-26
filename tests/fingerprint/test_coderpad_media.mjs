import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

function harness({enabled = true, version = '2.5.0', mediaVersion = '7.1.0.15306', combined = true, processor = false, capturing = false} = {}) {
  const timers = new Map();
  let captures = 0;
  const source = {getVideoTracks: () => [{readyState: 'live'}]};
  const instance = {isSupportVideoShare: combined, isSupportMediaStreamTrackProcessor: processor,
    isVideoTagFrameAccessible: true, videoCaptureValue: capturing ? {videoCtrl: {srcObject: source}} : null};
  const self = {children: [], getAttribute: () => '41', append(node) {this.children.push(node); node.parentNode = this;}};
  const remote = {children: [], getAttribute: () => '52', append() {throw Error('Remote video must not change');}};
  const created = [];
  const document = {
    querySelectorAll: () => [remote, self],
    createElement(tag) {
      assert.equal(tag, 'video');
      const node = {style: {}, parentNode: null, setAttribute() {},
        play() {this.plays = (this.plays || 0) + 1; return Promise.resolve();},
        remove() {this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1); this.parentNode = null;}};
      created.push(node); return node;
    },
  };
  const inner = {[Symbol('different-context-name')]: {mediaAgent: {instance}}};
  const client = {stream: {[Symbol('different-stream-name')]: inner},
    getCurrentUserInfo: () => ({userId: 41, bVideoOn: !!instance.videoCaptureValue})};
  const sdk = {VERSION: version, videoClient: client, createClient() {captures++; throw Error('No client creation');}};
  function req() {return {renamedExport: sdk};}
  req.m = {9876: function sdkFactory() {return 'createLocalVideoTrack preloadDependentAssets';}};
  const page = {JsMediaSDK_Instance: {pkgVersion: mediaVersion}, document, webpackChunkcoderpad: []};
  page.webpackChunkcoderpad.push = entry => entry[2](req);
  const win = {wrappedJSObject: page, document,
    setInterval(fn) {timers.set(1, fn); return 1;}, clearInterval(id) {timers.delete(id);}};
  const context = vm.createContext({JSWindowActorChild: class {}, Services: {prefs: {getBoolPref: () => enabled}},
    Cu: {cloneInto: structuredClone, waiveXrays: x => x, exportFunction: fn => fn}});
  const code = readFileSync(new URL('../../additions/browser/components/cloakfox/actors/CloakfoxCoderPadMediaChild.sys.mjs', import.meta.url), 'utf8');
  vm.runInContext(code.replace('export class CloakfoxCoderPadMediaChild', 'class CloakfoxCoderPadMediaChild') + '\nglobalThis.Actor=CloakfoxCoderPadMediaChild;', context);
  const actor = new context.Actor(); actor.contentWindow = win; actor.browsingContext = {id: 19};
  actor.handleEvent({type: 'DOMDocElementInserted'});
  const tick = () => {for (const fn of timers.values()) fn();};
  return {instance, source, self, remote, created, actor, tick, sdk, page, client, timers,
    get captures() {return captures;}};
}

test('affected combined worker uses the existing canvas frame sender without starting capture', () => {
  const h = harness(); h.tick();
  assert.equal(h.instance.isVideoTagFrameAccessible, false);
  assert.equal(h.instance.isSupportVideoShare, true);
  assert.equal(h.captures, 0); assert.equal(h.created.length, 0);
});

test('local preview reuses the authorized stream and leaves remote players alone', () => {
  const h = harness({capturing: true}); h.tick();
  assert.equal(h.created.length, 1);
  const video = h.created[0];
  assert.equal(video.srcObject, h.source); assert.equal(video.muted, true);
  assert.equal(video.parentNode, h.self); assert.equal(h.remote.children.length, 0);
  h.tick(); assert.equal(h.created.length, 1); assert.equal(video.plays, 1);
  h.instance.videoCaptureValue = null; h.tick();
  assert.equal(video.parentNode, null); assert.equal(video.srcObject, null);
  assert.equal(h.captures, 0);
});

test('camera switch updates only the local preview and teardown releases the stream', () => {
  const h = harness({capturing: true}); h.tick(); const video = h.created[0];
  const next = {}; h.instance.videoCaptureValue.videoCtrl.srcObject = next; h.tick();
  assert.equal(video.srcObject, next); assert.equal(video.plays, 2);
  h.actor.didDestroy(); assert.equal(video.srcObject, null); assert.equal(video.parentNode, null);
  assert.equal(h.timers.size, 0);
});

test('standard workers, supported processors and unverified SDK versions remain unchanged', () => {
  for (const options of [{combined: false}, {processor: true}, {version: '2.6.0'}, {mediaVersion: 'future'}]) {
    const h = harness({...options, capturing: true}); h.tick();
    assert.equal(h.instance.isVideoTagFrameAccessible, true); assert.equal(h.created.length, 0);
  }
});

test('opt-out makes no SDK, capture or DOM changes', () => {
  const h = harness({enabled: false, capturing: true}); h.tick();
  assert.equal(h.instance.isVideoTagFrameAccessible, true); assert.equal(h.created.length, 0);
  assert.equal(h.timers.size, 0); assert.equal(h.captures, 0);
});

test('late initialization and client replacement reconcile without creating a client', () => {
  const h = harness(); const client = h.client;
  h.sdk.videoClient = null; h.instance.isVideoTagFrameAccessible = true; h.tick();
  assert.equal(h.instance.isVideoTagFrameAccessible, true);
  h.sdk.videoClient = client; h.tick(); assert.equal(h.instance.isVideoTagFrameAccessible, false);
  const next = {...h.instance, isVideoTagFrameAccessible: true};
  h.sdk.videoClient = {stream: {[Symbol()]: {[Symbol()]: {mediaAgent: {instance: next}}}}, getCurrentUserInfo: () => ({userId: 42})};
  h.tick(); assert.equal(next.isVideoTagFrameAccessible, false); assert.equal(h.captures, 0);
});
