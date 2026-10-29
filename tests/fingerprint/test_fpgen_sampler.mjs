import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { sampleFPGenFingerprint, adaptFPGenFingerprint } from "../../additions/browser/components/cloakfox/CloakfoxFPGenSampler.sys.mjs";
import { FPGEN_NETWORK } from "../../additions/browser/components/cloakfox/CloakfoxFPGenNetwork.sys.mjs";

function rng(seed) { return () => { seed = Math.imul(seed ^ seed >>> 15, 1 | seed); seed ^= seed + Math.imul(seed ^ seed >>> 7, 61 | seed); return ((seed ^ seed >>> 14) >>> 0) / 4294967296; }; }

test("fpgen same seed and options are deterministic, separate seeds vary", () => {
  const options = { os: "macos", hardware: "apple", browser: "firefox", version: "159" };
  assert.deepEqual(sampleFPGenFingerprint(rng(42), options), sampleFPGenFingerprint(rng(42), options));
  assert.ok(new Set(Array.from({length: 20}, (_, i) => JSON.stringify(sampleFPGenFingerprint(rng(i + 1), options)))).size > 10);
});

test("fpgen conditions observed OS, browser and GPU families", () => {
  for (const [os, hardware, pattern] of [["windows", "nvidia", /Windows/], ["linux", "intel", /Linux/], ["macos", "apple", /Macintosh/]]) {
    for (let i = 1; i <= 30; i++) {
      const fp = sampleFPGenFingerprint(rng(i), {os, hardware, browser: "firefox"});
      assert.match(fp.userAgent, pattern);
      assert.match(fp.userAgent, /Firefox\//);
      assert.match(fp.videoCard.renderer, new RegExp(hardware, "i"));
      assert.ok(fp.screen.width >= fp.screen.availWidth);
      assert.ok(fp.screen.height >= fp.screen.availHeight);
      assert.ok(fp.hardwareConcurrency > 0);
    }
  }
  for (const [browser, pattern] of [["chrome", /Chrome\//], ["edge", /Edg\//], ["safari", /Version\/.+Safari\//]]) {
    assert.match(sampleFPGenFingerprint(rng(7), {browser}).userAgent, pattern);
  }
});

test("unsupported and impossible constraints throw without consuming random state", () => {
  for (const options of [{os:"android"}, {hardware:"bogus"}, {browser:"bogus"}, {browser:"chromium"}, {version:"oops"}, {version:0}, {os:"windows", hardware:"apple"}, {os:"linux", browser:"safari"}]) {
    let calls = 0;
    assert.throws(() => sampleFPGenFingerprint(() => { calls++; return 0.5; }, options), /fpgen/i);
    assert.equal(calls, 0);
  }
  assert.throws(() => sampleFPGenFingerprint(() => NaN), /random/i);
});

test("adapter allowlists fields and returns detached safe data", () => {
  const sample = { "navigator.userAgent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/146.0", "navigator.hardwareConcurrency":8,
    screen:{width:1920,height:1080,availWidth:1920,availHeight:1040,permissions:{camera:"granted"}},
    window:{devicePixelRatio:1,outerWidth:1900,outerHeight:1000,deviceId:"captured"}, gpu:{vendor:"NVIDIA",renderer:"NVIDIA GTX",secret:"captured"},
    permissions:{camera:"granted"}, "network.tls.scrapfly_fp":{version:772}, mediaDevices:[{deviceId:"captured"}] };
  const fp = adaptFPGenFingerprint(sample);
  assert.deepEqual(Object.keys(fp).sort(), ["hardwareConcurrency", "screen", "userAgent", "videoCard"]);
  assert.deepEqual(Object.keys(fp.videoCard).sort(), ["renderer", "vendor"]);
  assert.doesNotMatch(JSON.stringify(fp), /captured|permission|secret|tls|deviceId/);
  fp.screen.width = 1;
  assert.equal(sample.screen.width, 1920);
  assert.throws(() => adaptFPGenFingerprint({...sample, screen:{width:-1,height:100}}), /fpgen/i);
});

test("sample mutation cannot poison model or another container", () => {
  const a = sampleFPGenFingerprint(rng(12));
  const before = JSON.stringify(a);
  a.videoCard.vendor = "poison"; a.screen.width = 1;
  assert.equal(JSON.stringify(sampleFPGenFingerprint(rng(12))), before);
  assert.ok(Object.isFrozen(FPGEN_NETWORK));
  assert.ok(Object.isFrozen(FPGEN_NETWORK.nodes[0]));
});

test("every supported browser/OS/GPU constraint remains complete across seeds", () => {
  let supported = 0;
  for (const browser of ["firefox", "chrome", "edge", "safari"]) {
    for (const os of ["windows", "macos", "linux"]) {
      for (const hardware of ["auto", "apple", "intel", "nvidia", "amd", "software", "other"]) {
        const options = {browser, os, hardware};
        let probe;
        try { probe = sampleFPGenFingerprint(rng(1), options); }
        catch (error) {
          assert.match(error.message, /no matching persona/);
          assert.throws(() => sampleFPGenFingerprint(rng(99), options), /no matching persona/);
          continue;
        }
        supported++;
        const osPattern = {windows:/Windows/, macos:/Macintosh/, linux:/Linux/}[os];
        for (let i = 1; i <= 100; i++) {
          const fp = sampleFPGenFingerprint(rng(i), options);
          assert.match(fp.userAgent, osPattern);
          assert.ok(Number.isInteger(fp.hardwareConcurrency));
        }
        assert.ok(probe.screen.width > 0);
      }
    }
  }
  assert.equal(supported, 48);
});

test("entire pinned model is packaged and projection retains all selected distributions", () => {
  const root = new URL("../../additions/browser/components/cloakfox/", import.meta.url);
  const metadata = JSON.parse(readFileSync(new URL("fpgen-model-source.json", root)));
  const archive = readFileSync(new URL("fpgen-model-reference.zip", root));
  assert.equal(createHash("sha256").update(archive).digest("hex"), "6530b8322cdaa4ec042921c8d9a0369a0e6e0269ba636c01a7203e4a2f109936");
  assert.equal(metadata.sourceNodeCount, 120);
  assert.equal(metadata.sourceValueCount, 12256);
  assert.equal(metadata.incompleteWindowPaths.length, 9);
  assert.equal(createHash("sha256").update(readFileSync(new URL("CloakfoxFPGenNetwork.sys.mjs", root))).digest("hex"), metadata.projectionSHA256);
  assert.equal(FPGEN_NETWORK.nodes.find(n => n.name === "screen").possibleValues.length, 501);
  assert.equal(FPGEN_NETWORK.nodes.find(n => n.name === "window").possibleValues.length, 1409);
  assert.equal(FPGEN_NETWORK.nodes.find(n => n.name === "navigator.userAgent").possibleValues.length, 98);
  assert.equal(FPGEN_NETWORK.nodes.some(n => /permissions|tls|devices\./.test(n.name)), false);
});
