import test from 'node:test';
import assert from 'node:assert/strict';
import { initMediaWebsiteLabels, initCameraExposure } from '../../additions/browser/components/cloakfox/content/media-label-controls.mjs';

class Element {
  value = ''; disabled = false; hidden = false; textContent = ''; validity = '';
  children = []; events = new Map();
  addEventListener(name, fn) { this.events.set(name, fn); }
  emit(name) { return this.events.get(name)?.({ preventDefault() {} }); }
  setCustomValidity(value) { this.validity = value; }
  removeAttribute() {} setAttribute() {} reportValidity() {} focus() {}
  append(option) { this.children.push(option); if (this.children.length === 1) this.value = option.value; }
  replaceChildren(...options) { this.children = []; this.value = ''; options.forEach(o => this.append(o)); }
}
class Option { constructor(text, value) { this.text = text; this.value = value; } }
const settle = () => new Promise(resolve => setImmediate(resolve));
function setup(kind, inventory, initial = {}) {
  const elements = new Map(), values = new Map(Object.entries(initial));
  const document = { getElementById(id) {
    if (!elements.has(id)) elements.set(id, new Element());
    return elements.get(id);
  } };
  const prefs = {
    getStringPref(k, fallback) { return values.get(k) ?? fallback; },
    getIntPref(k, fallback) { return values.get(k) ?? fallback; },
    setStringPref(k, v) { values.set(k, v); },
    setIntPref(k, v) { values.set(k, v); },
  };
  const navigator = { mediaDevices: {
    async getCloakfoxCameras() { return inventory; },
    async getCloakfoxAudioDevices() { return inventory; },
  } };
  initMediaWebsiteLabels(kind, { document, navigator, prefs, Option });
  return { values, element: suffix => document.getElementById(`cfx-${kind}-${suffix}`) };
}

for (const kind of ['camera', 'microphone', 'speaker']) {
  test(`${kind}: custom fallback requires save and rejects invalid names`, async () => {
    const { values, element } = setup(kind, []);
    const key = `cloakfox.${kind}.website_label_`;
    element('website-label').value = '4'; element('website-label').emit('change');
    assert.equal(element('website-custom-form').hidden, false);
    assert.equal(values.has(key + 'style'), false);
    for (const invalid of [' ', 'x'.repeat(129), 'bad\u0000label']) {
      element('website-custom').value = invalid;
      element('website-custom-form').emit('submit');
      assert.equal(values.has(key + 'custom'), false);
      assert.ok(element('website-custom').validity);
    }
    element('website-custom').value = '  Studio 📻  ';
    element('website-custom-form').emit('submit');
    assert.equal(values.get(key + 'custom'), 'Studio 📻');
    assert.equal(values.get(key + 'style'), 4);
    element('website-label').value = '0'; element('website-label').emit('change');
    assert.equal(values.get(key + 'style'), 0);
    assert.equal(element('website-custom-form').hidden, true);
    await settle();
  });
}

test('audio inventory filters kinds and disallows unnamed placeholder saves', async () => {
  const inventory = [
    { kind: 'audioinput', deviceId: 'mic-1', label: 'USB' },
    { kind: 'audioinput', deviceId: 'mic-2', label: 'USB' },
    { kind: 'audiooutput', deviceId: 'output-1', label: 'USB' },
    { kind: 'audiooutput', deviceId: '', label: '' },
  ];
  const mic = setup('microphone', inventory), speaker = setup('speaker', inventory);
  await settle();
  assert.deepEqual(mic.element('website-device').children.map(o => [o.value,o.text]),
    [['mic-1','USB (1)'],['mic-2','USB (2)']]);
  assert.deepEqual(speaker.element('website-device').children.map(o => o.value), ['output-1']);
  mic.element('device-name').value = 'Interview'; mic.element('device-form').emit('submit');
  assert.deepEqual(JSON.parse(mic.values.get('cloakfox.microphone.website_label_map')), { 'mic-1': 'Interview' });
  assert.equal(speaker.values.has('cloakfox.speaker.website_label_map'), false);
  mic.element('device-reset').emit('click');
  assert.deepEqual(JSON.parse(mic.values.get('cloakfox.microphone.website_label_map')), {});
  const placeholder = setup('microphone', [{kind:'audioinput',deviceId:'',label:''}]);
  await settle();
  assert.equal(placeholder.element('device-save').disabled, true);
  assert.equal(placeholder.element('website-device').children[0].text, 'Microphone access required');
});

test('per-device save preserves other names, rejects invalid labels and caps map size', async () => {
  const initial = { 'cloakfox.speaker.website_label_map': JSON.stringify({ other:'Other speaker' }) };
  const { values, element } = setup('speaker', [{kind:'audiooutput',deviceId:'one',label:'One'}], initial);
  await settle();
  element('device-name').value = 'Desk'; element('device-form').emit('submit');
  assert.deepEqual(JSON.parse(values.get('cloakfox.speaker.website_label_map')), {other:'Other speaker',one:'Desk'});
  element('device-name').value = 'bad\u0000name'; element('device-form').emit('submit');
  assert.equal(JSON.parse(values.get('cloakfox.speaker.website_label_map')).one, 'Desk');
  values.set('cloakfox.speaker.website_label_map', JSON.stringify(Object.fromEntries(
    Array.from({length:64},(_,i)=>[`device${i}`,`Speaker ${i}`]))));
  element('device-name').value = '65th'; element('device-form').emit('submit');
  assert.equal(Object.keys(JSON.parse(values.get('cloakfox.speaker.website_label_map'))).length,64);
  assert.match(element('device-status').textContent, /at most 64/);
});

for (const [kind,deviceKind,title] of [['camera',undefined,'Webcam'],['microphone','audioinput','Microphone'],['speaker','audiooutput','Speaker']]) {
  test(`${kind}: permission placeholder cannot silently save`, async () => {
    const { values, element } = setup(kind,[{kind:deviceKind,deviceId:'',label:''}]);
    await settle();
    assert.equal(element('device-save').disabled,true);
    assert.equal(element('device-name').disabled,true);
    assert.equal(element('website-device').children[0].text,`${title} access required`);
    element('device-name').value='Unusable name';element('device-form').emit('submit');
    assert.equal(values.has(`cloakfox.${kind}.website_label_map`),false);
  });
}


test('camera choices follow maximum and preserve disconnected selections', async () => {
  const elements=new Map(),saved=[];
  const document={getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},createElement(){return new Element();}};
  const context={id:12,ids:['a','missing'],limit:2};
  const refresh=initCameraExposure({document,
    navigator:{mediaDevices:{async getCloakfoxCameras(){return ['a','b','c'].map(deviceId=>({deviceId,label:deviceId}));}}},
    getContext:()=>context,save:value=>saved.push(value)});
  await settle();
  const inputs=()=>document.getElementById('cfx-camera-exposure-devices').children.map(row=>row.children[0]);
  assert.equal(inputs().filter(i=>i.checked).length,2);
  assert.equal(inputs().find(i=>i.value==='b').disabled,true);
  inputs().find(i=>i.value==='missing').checked=false;inputs()[0].emit('change');
  assert.equal(inputs().find(i=>i.value==='b').disabled,false);
  inputs().find(i=>i.value==='b').checked=true;inputs()[0].emit('change');
  document.getElementById('cfx-camera-exposure-form').emit('submit');
  assert.deepEqual(saved,[['a','b']]);
  context.limit=1;await refresh();
  assert.equal(document.getElementById('cfx-camera-exposure-save').disabled,true);
  inputs().find(i=>i.value==='missing').checked=false;inputs()[0].emit('change');
  assert.equal(document.getElementById('cfx-camera-exposure-save').disabled,false);
  context.limit=0;context.ids=[];await refresh();
  assert.ok(inputs().every(i=>i.disabled));
  document.getElementById('cfx-camera-exposure-form').emit('submit');
  assert.deepEqual(saved.at(-1),[]);
});
