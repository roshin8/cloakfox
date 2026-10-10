import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

// Exercise the real actor. SharedMap.get returns a fresh structured clone on
// every read in Gecko; count those reads instead of using a flaky speed gate.
function harness() {
  let enabled = true;
  let fdlibm = true;
  let dataNoise = false;
  let reads = 0;
  let prefReads = 0;
  let snapshot = {};
  const listeners = new Set();
  const prefListeners = new Map();
  const realmCalls = [];
  const sharedData = {
    get() { reads++; return structuredClone(snapshot); },
    addEventListener(type, listener) {
      assert.equal(type, "change"); listeners.add(listener);
    },
  };
  const context = vm.createContext({
    JSWindowActorChild: class {},
    Services: {
      cpmm: { sharedData },
      prefs: {
        getBoolPref(name, fallback) {
          prefReads++;
          return name === "cloakfox.enabled" ? enabled : name === "javascript.options.use_fdlibm_for_sin_cos_tan" ? fdlibm : name === "cloakfox.opt.math_data_noise" ? dataNoise : fallback;
        },
        addObserver(name, listener) { prefListeners.set(name, listener); },
      },
    },
    Cu: { cloneInto: () => ({}), waiveXrays: value => value, exportFunction: fn => fn },
    atob: value => Buffer.from(value, "base64").toString("binary"),
  });
  const source = readFileSync(new URL("../../additions/browser/components/cloakfox/actors/CloakfoxMathChild.sys.mjs", import.meta.url), "utf8");
  vm.runInContext(source.replace("export class CloakfoxMathChild", "class CloakfoxMathChild") + "\nglobalThis.Actor = CloakfoxMathChild;", context);
  function publish(configs, changedKeys = ["cloakfox-seeds"]) {
    snapshot = Object.fromEntries(Object.entries(configs).map(([ucid, config]) => [`cloakfox.s.cloak_cfg_${ucid}`, JSON.stringify(config)]));
    for (const listener of listeners) listener({ changedKeys });
  }
  function page(ucid) {
    const actor = new context.Actor();
    const pageMath = {};
    for (const name of Reflect.ownKeys(Math)) {
      const d = Object.getOwnPropertyDescriptor(Math, name);
      if (typeof d.value === "function") {
        const native = d.value;
        d.value = new Proxy(native, { apply(target, receiver, args) { realmCalls.push(name); return Reflect.apply(target, receiver, args); } });
      }
      Object.defineProperty(pageMath, name, d);
    }
    const win = { wrappedJSObject: { Math: pageMath }, docShell: { browsingContext: { originAttributes: { userContextId: ucid } } } };
    actor.contentWindow = win;
    actor.handleEvent({ type: "DOMDocElementInserted" });
    return win.wrappedJSObject.Math;
  }
  return { publish, page, realmCalls,
    setEnabled(value) { enabled = value; prefListeners.get("cloakfox.enabled")?.observe(); },
    setFdlibm(value) { fdlibm = value; prefListeners.get("javascript.options.use_fdlibm_for_sin_cos_tan")?.observe(); },
    setDataNoise(value) { dataNoise = value; },
    get reads() { return reads; }, get prefReads() { return prefReads; } };
}

test("animation math reuses one process snapshot across calls and windows", () => {
  const h = harness(); h.publish({ 0: { "math:trig_seed": 123 }, 2: { "math:trig_seed": 456 } });
  const a = h.page(0), b = h.page(2);
  const first = a.sin(.5);
  for (let i = 0; i < 1000; i++) { assert.equal(a.sin(.5), first); b.cos(i / 100); }
  assert.equal(h.reads, 1, "one deserialization per snapshot, not per Math call");
});

test("sin/cos/tan keep the page realm when its math-library policy can differ", () => {
  const h = harness(); h.publish({ 0: { "math:trig_seed": 123 } });
  const math = h.page(0);
  h.setFdlibm(false);
  for (const name of ["sin", "cos", "tan"]) {
    assert.equal(math[name](.5), math[name]({ valueOf() { return .5; } }));
  }
  assert.deepEqual(h.realmCalls, ["sin", "sin", "cos", "cos", "tan", "tan"]);
  h.realmCalls.length = 0; h.setFdlibm(true); math.sin(.5); math.cos(.5); math.tan(.5);
  assert.deepEqual(h.realmCalls, []);
});

test("numeric animation calls avoid realm round trips and repeated preference reads", () => {
  const h = harness(); h.publish({ 0: { "math:trig_seed": 123 } });
  const math = h.page(0), prefReads = h.prefReads;
  for (let i = 0; i < 1000; i++) { math.sin(i / 100); math.cos(i / 100); math.sqrt(i); }
  assert.equal(h.prefReads, prefReads, "read the master switch when it changes, not per operation");
  assert.equal(h.realmCalls.length, 0, "numeric calls use the same engine intrinsic in the actor realm");
  assert.ok(Number.isFinite(math.sin({ valueOf() { return .5; } })));
  assert.deepEqual(h.realmCalls, ["sin"], "coercion retains the original page-realm function");
  assert.throws(() => math.sin(Symbol()), TypeError);
});

test("published seed updates remain live in previously captured functions", () => {
  const h = harness(); h.publish({ 0: { "math:trig_seed": 123 }, 2: { "math:trig_seed": 456 } });
  const a = h.page(0), b = h.page(2), sin = a.sin, first = sin(.5), other = b.sin(.5);
  h.publish({ 0: { "math:trig_seed": 999 }, 2: { "math:trig_seed": 456 } });
  assert.notEqual(sin(.5), first); assert.equal(b.sin(.5), other);
  assert.equal(h.reads, 2);
  const updated = sin(.5); h.setEnabled(false);
  assert.equal(sin(.5), Math.sin(.5)); assert.equal(h.reads, 2);
  h.setEnabled(true); assert.equal(sin(.5), updated); assert.equal(h.reads, 2);
  h.publish({ 0: { "math:trig_seed": 999 }, 2: { "math:trig_seed": 456 } }, ["unrelated"]);
  assert.equal(sin(.5), updated); assert.equal(h.reads, 2);
});

test("removed or invalid seeds clear cached noise and a later seed restores it", () => {
  const h = harness(); h.publish({ 0: { "math:trig_seed": 123 } });
  const sin = h.page(0).sin, first = sin(.5);
  for (const config of [{}, { "math:trig_seed": 0 }, { "math:trig_seed": -1 }, { "math:trig_seed": "123" }]) {
    h.publish({ 0: config }); assert.equal(sin(.5), Math.sin(.5));
  }
  h.publish({ 0: { "math:trig_seed": 123 } }); assert.equal(sin(.5), first);
  assert.equal(h.reads, 6);
});

test("Firebase tree sizes retain all children with the failing live seed", () => {
  const h = harness();
  h.publish({ 0: { "math:trig_seed": 761685640 } });
  const math = h.page(0);
  // Firebase's Base12Num truncates this logarithm ratio. Rounding below an
  // integer drops nodes: a three-field {a, o, t} edit becomes only {t}.
  for (const [children, levels] of [[1, 1], [3, 2], [7, 3], [15, 4]]) {
    assert.equal(parseInt(math.log(children + 1) / math.log(2), 10), levels,
      `preserve the tree levels for ${children} children`);
  }
});

test("logarithms and powers preserve native values used by data encoders", () => {
  const h = harness();
  h.publish({ 0: { "math:trig_seed": 761685640 } });
  const math = h.page(0);
  for (const name of ["log", "log2", "log10", "log1p"]) {
    for (const value of [0, .5, 2, 4, 7, 1024]) {
      assert.equal(math[name](value), Math[name](value), `${name}(${value})`);
    }
    assert.equal(math[name]({ valueOf() { return 2; } }), Math[name](2));
  }
  for (const exponent of [-1022, -52, -1, 0, 52]) {
    assert.equal(math.pow(2, exponent), Math.pow(2, exponent));
  }
});

test("optional data-math noise applies to new pages and switching off restores native results", () => {
  const h = harness();
  h.publish({ 0: { "math:trig_seed": 761685640 } });
  const originalPage = h.page(0);
  h.setDataNoise(true);
  const noisyPage = h.page(0);
  for (const name of ["log", "log2", "log10", "log1p"]) {
    assert.notEqual(noisyPage[name](.3), Math[name](.3), `${name} is opt-in`);
    assert.equal(noisyPage[name](.3), noisyPage[name](.3), `${name} is deterministic`);
    assert.equal(noisyPage[name]({ valueOf() { return .3; } }), noisyPage[name](.3));
  }
  assert.notEqual(noisyPage.pow(2, -52), 2.220446049250313e-16);
  assert.equal(originalPage.pow(2, -52), 2.220446049250313e-16, "existing realms keep their installation policy");
  h.setDataNoise(false);
  const restoredPage = h.page(0);
  assert.equal(restoredPage.log(2), 0.6931471805599453);
  assert.equal(parseInt(restoredPage.log(4) / restoredPage.log(2), 10), 2);
  assert.equal(restoredPage.pow(2, -52), 2.220446049250313e-16);
});

test("opt-in data-math noise respects the master switch and zero seed", () => {
  const h = harness(); h.setDataNoise(true);
  h.publish({ 0: { "math:trig_seed": 761685640 } });
  const math = h.page(0);
  assert.notEqual(math.log(2), 0.6931471805599453);
  assert.equal(math.log(0), -Infinity);
  assert.equal(math.pow(2, 2), 4);
  assert.throws(() => math.log(Symbol()), TypeError);
  h.setEnabled(false);
  assert.equal(math.log(2), 0.6931471805599453);
  assert.equal(math.pow(2, -52), 2.220446049250313e-16);
  h.setEnabled(true); h.publish({ 0: { "math:trig_seed": 0 } });
  assert.equal(math.log(2), 0.6931471805599453);
});
