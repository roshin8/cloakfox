/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: present a persona-OS-coherent speechSynthesis.getVoices() list
 * instead of the real host's TTS voices, which are a blatant OS tell (macOS,
 * Windows and Linux ship completely different voice sets).
 *
 * The fake voices are real SpeechSynthesisVoice instances (Object.create on the
 * page-side prototype, so `instanceof` holds); their properties are backed by a
 * chrome-side WeakMap and served through the INHERITED prototype getters
 * (native flags + "get <prop>" identity), so no own-property tell appears.
 * getVoices() returns the persona list; a one-shot voiceschanged event mirrors
 * the real async-load behaviour.
 */

// Per-OS voice sets — plausible defaults (name / lang / voiceURI / localService
// / default). All local, first entry is the default voice.
const VOICES = {
  windows: [
    { name: "Microsoft David - English (United States)", lang: "en-US",
      voiceURI: "Microsoft David - English (United States)",
      localService: true, default: true },
    { name: "Microsoft Zira - English (United States)", lang: "en-US",
      voiceURI: "Microsoft Zira - English (United States)",
      localService: true, default: false },
    { name: "Microsoft Mark - English (United States)", lang: "en-US",
      voiceURI: "Microsoft Mark - English (United States)",
      localService: true, default: false },
  ],
  macos: [
    { name: "Samantha", lang: "en-US",
      voiceURI: "com.apple.voice.compact.en-US.Samantha",
      localService: true, default: true },
    { name: "Daniel", lang: "en-GB",
      voiceURI: "com.apple.voice.compact.en-GB.Daniel",
      localService: true, default: false },
    { name: "Alex", lang: "en-US",
      voiceURI: "com.apple.speech.synthesis.voice.Alex",
      localService: true, default: false },
  ],
  linux: [
    { name: "English (America)", lang: "en-US",
      voiceURI: "English (America)", localService: true, default: true },
    { name: "English (Great Britain)", lang: "en-GB",
      voiceURI: "English (Great Britain)", localService: true, default: false },
  ],
};

const VOICE_PROPS = ["voiceURI", "name", "lang", "localService", "default"];

function osFromPlatform(platform) {
  if (/win/i.test(platform)) return "windows";
  if (/mac/i.test(platform)) return "macos";
  return "linux";
}

function setGetterIdentity(getterFn, name) {
  const waived = Cu.waiveXrays(getterFn);
  try {
    Object.defineProperty(waived, "name", {
      value: name, writable: false, enumerable: false, configurable: true,
    });
    Object.defineProperty(waived, "length", {
      value: 0, writable: false, enumerable: false, configurable: true,
    });
  } catch (_e) { /* best effort */ }
  return getterFn;
}

function setNativeIdentity(fn, name, length) {
  const waived = Cu.waiveXrays(fn);
  try {
    Object.defineProperty(waived, "name", {
      value: name, writable: false, enumerable: false, configurable: true,
    });
    Object.defineProperty(waived, "length", {
      value: length, writable: false, enumerable: false, configurable: true,
    });
  } catch (_e) { /* best effort */ }
  return fn;
}

export class CloakfoxSpeechChild extends JSWindowActorChild {
  handleEvent(event) {
    if (event.type !== "DOMDocElementInserted") return;
    try { this.#install(); } catch (_e) { /* never leak chrome:// */ }
  }

  #install() {
    const win = this.contentWindow;
    if (!win) return;
    if (!Services.prefs.getBoolPref("cloakfox.enabled", false)) return;

    const pageWin = win.wrappedJSObject;
    const Voice = pageWin.SpeechSynthesisVoice;
    const Synth = pageWin.SpeechSynthesis;
    if (!Voice?.prototype || !Synth?.prototype) return;

    const list = VOICES[osFromPlatform(win.navigator.platform || "")] ||
                 VOICES.linux;

    // Chrome-side backing store for the fake voices, keyed by the waived page
    // instance so the prototype getters can resolve their properties.
    const store = new WeakMap();

    // Override each SpeechSynthesisVoice.prototype getter to read the store,
    // falling back to native for any real voice that isn't ours.
    for (const prop of VOICE_PROPS) {
      const desc = Object.getOwnPropertyDescriptor(Voice.prototype, prop);
      const origGetter = desc?.get;
      if (!origGetter) continue;
      const getter = Cu.exportFunction(function () {
        const data = store.get(Cu.waiveXrays(this));
        if (data && prop in data) return data[prop];
        return origGetter.call(this);
      }, pageWin);
      setGetterIdentity(getter, `get ${prop}`);
      try {
        Object.defineProperty(Voice.prototype, prop, {
          get: getter, enumerable: true, configurable: true,
        });
      } catch (_e) { /* best effort */ }
    }

    // Build the fake voice instances (page-side, so `instanceof` holds).
    const fakeVoices = list.map((data) => {
      const inst = pageWin.Object.create(Voice.prototype);
      store.set(Cu.waiveXrays(inst), data);
      return inst;
    });

    // getVoices() returns a fresh page-side array of the fake voices.
    const origGetVoices = Synth.prototype.getVoices;
    const newGetVoices = Cu.exportFunction(function () {
      const arr = new pageWin.Array();
      for (const v of fakeVoices) arr.push(v);
      return arr;
    }, pageWin);
    setNativeIdentity(newGetVoices, origGetVoices.name, origGetVoices.length);
    try {
      Object.defineProperty(Synth.prototype, "getVoices", {
        value: newGetVoices, writable: true, enumerable: true, configurable: true,
      });
    } catch (_e) { /* best effort */ }

    // Mirror real async load: fire voiceschanged once so listeners re-query.
    try {
      const synth = pageWin.speechSynthesis;
      if (synth) {
        win.setTimeout(Cu.exportFunction(function () {
          try {
            const ev = new pageWin.Event("voiceschanged");
            synth.dispatchEvent(ev);
          } catch (_e) { /* ignore */ }
        }, pageWin), 0);
      }
    } catch (_e) { /* ignore */ }
  }
}
