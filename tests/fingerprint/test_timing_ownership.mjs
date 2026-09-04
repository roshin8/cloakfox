/* Regression gates for native performance-clock ownership and actor timers.
 *
 *   node --test tests/fingerprint/test_timing_ownership.mjs
 */
import test from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const timingActor = readFileSync(
  join(root, "additions/browser/components/cloakfox/actors/CloakfoxTimingChild.sys.mjs"),
  "utf8"
);
const performancePatch = readFileSync(
  join(root, "patches/performance-timeline-timing.patch"),
  "utf8"
);

const WRAPPERS = [
  { api: "setTimeout", original: "origSetTimeout" },
  { api: "setInterval", original: "origSetInterval" },
  { api: "requestAnimationFrame", original: "origRAF" },
];
const SEED_B64 = Buffer.from(Uint8Array.from({ length: 32 }, (_, i) => i + 1)).toString("base64");

function braceDelta(line) {
  let delta = 0;
  for (const char of line) {
    if (char === "{") delta++;
    else if (char === "}") delta--;
  }
  return delta;
}

function reconstructPatchedNow(patch) {
  const signature = "DOMHighResTimeStamp Performance::Now()";
  const signatureStart = patch.indexOf(signature);
  if (signatureStart < 0) throw new Error(`patch hunk not found: ${signature}`);
  const hunkStart = patch.lastIndexOf("@@", signatureStart);
  const hunkEnd = patch.indexOf("\n@@", signatureStart);
  const hunk = patch.slice(hunkStart, hunkEnd < 0 ? patch.length : hunkEnd);
  const [header, ...lines] = hunk.split("\n");
  if (!header.includes(`${signature} {`)) {
    throw new Error(`patch hunk header does not declare: ${signature}`);
  }

  // The hunk begins inside Firefox's pre-existing system-principal branch.
  // Reconstruct that elided opening scope, then apply every context/addition
  // line and skip only removed lines. This preserves each return's provenance.
  const method = [
    { code: `${signature} {`, source: "synthetic" },
    { code: "  if (/* pre-existing system-principal scope elided by hunk */) {", source: "synthetic" },
  ];
  let depth = 2;
  for (const line of lines) {
    if (line.startsWith("-")) continue;
    if (!line.startsWith("+") && !line.startsWith(" ") && line !== "") continue;
    const source = line.startsWith("+") ? "added" : "context";
    const code = line === "" ? "" : line.slice(1);
    method.push({ code, source });
    depth += braceDelta(code);
    if (depth === 0) return method;
    if (depth < 0) throw new Error("patched Performance::Now closed too many braces");
  }
  throw new Error("patched Performance::Now did not close");
}

function enumerateReturns(method) {
  let depth = 0;
  return method.flatMap((line, index) => {
    const depthAtStart = depth;
    depth += braceDelta(line.code);
    const match = /^\s*return\s+(.+);\s*$/.exec(line.code);
    return match ? [{ expression: match[1], source: line.source, depth: depthAtStart, index }] : [];
  });
}

function jsTokens(source) {
  const tokens = [];
  for (let i = 0; i < source.length;) {
    if (/\s/.test(source[i])) { i++; continue; }
    if (source.startsWith("//", i)) {
      i = source.indexOf("\n", i);
      if (i < 0) break;
      continue;
    }
    if (source.startsWith("/*", i)) {
      const end = source.indexOf("*/", i + 2);
      if (end < 0) throw new Error("unterminated block comment");
      i = end + 2;
      continue;
    }
    if (["'", '"', "`"].includes(source[i])) {
      const quote = source[i++];
      let value = "";
      while (i < source.length && source[i] !== quote) {
        if (source[i] === "\\") i++;
        value += source[i++] || "";
      }
      if (source[i] !== quote) throw new Error("unterminated string literal");
      i++;
      tokens.push({ type: "string", value });
      continue;
    }
    if (/[A-Za-z_$]/.test(source[i])) {
      const start = i++;
      while (/[A-Za-z0-9_$]/.test(source[i] || "")) i++;
      tokens.push({ type: "identifier", value: source.slice(start, i) });
      continue;
    }
    i++;
  }
  return tokens;
}

function assertActorHasNoClockOwnership(actor) {
  const forbidden = jsTokens(actor).filter(token =>
    (token.type === "identifier" && ["performance", "Performance", "origPerfNow", "now"].includes(token.value)) ||
    (token.type === "string" && ["performance", "Performance", "now"].includes(token.value))
  );
  assert.equal(forbidden.length, 0,
    `timing actor has forbidden clock ownership token(s): ${forbidden.map(t => t.value).join(", ")}`);
}

function findWrapperStatementEnd(source, start) {
  const callStart = source.indexOf("(", source.indexOf("setNativeIdentity", start));
  if (callStart < 0) throw new Error("wrapper installation call not found");
  let parens = 0;
  for (let i = callStart; i < source.length; i++) {
    if (source[i] === "(") parens++;
    else if (source[i] === ")") parens--;
    if (parens === 0 && source[i + 1] === ";") return i + 2;
  }
  throw new Error("wrapper installation statement did not terminate");
}

function mutateClock(actor, mode) {
  const anchor = "const pageWin = win.wrappedJSObject;";
  const injections = {
    direct: "pageWin.performance.now = () => 0;",
    alias: "const perf = pageWin.performance;\n    perf.now = () => 0;",
    computed: "Object.defineProperty(pageWin[\"performance\"], \"now\", { value: () => 0 });",
  };
  if (!injections[mode]) throw new Error(`unknown clock mutation: ${mode}`);
  const mutant = actor.replace(anchor, `${anchor}\n    ${injections[mode]}`);
  assert.notEqual(mutant, actor, `clock ${mode} mutation did not apply`);
  return mutant;
}

function mutateTimerPath(actor, spec, mode) {
  const marker = `pageWin.${spec.api} = setNativeIdentity`;
  const start = actor.indexOf(marker);
  if (start < 0) throw new Error(`${spec.api} installation marker not found`);
  const end = findWrapperStatementEnd(actor, start);
  const statement = actor.slice(start, end);
  if (mode === "comment") return `${actor.slice(0, start)}/*${statement}*/${actor.slice(end)}`;
  if (mode === "prng") {
    if (!statement.includes("prng()")) throw new Error(`${spec.api} PRNG call not found`);
    return `${actor.slice(0, start)}${statement.replace("prng()", "0")}${actor.slice(end)}`;
  }
  if (mode === "restore") {
    return `${actor.slice(0, end)}\n    pageWin["${spec.api}"] = ${spec.original};${actor.slice(end)}`;
  }
  throw new Error(`unknown ${spec.api} mutation: ${mode}`);
}

function mutateEarlyReturn(actor) {
  const anchor = "const pageWin = win.wrappedJSObject;";
  return actor.replace(anchor, `${anchor}\n    return;`);
}

function mutateRafOutsideGuard(actor) {
  const marker = "if (typeof origRAF === \"function\") {";
  const guardStart = actor.indexOf(marker);
  if (guardStart < 0) throw new Error("rAF availability guard not found");
  const guardEnd = actor.indexOf("\n    }", guardStart);
  if (guardEnd < 0) throw new Error("rAF availability guard end not found");
  return `${actor.slice(0, guardEnd + 6)}\n    pageWin.requestAnimationFrame = () => 0;${actor.slice(guardEnd + 6)}`;
}

function prepareActorSource(actor) {
  const prepared = actor.replace("export class CloakfoxTimingChild", "class CloakfoxTimingChild");
  if (prepared === actor) throw new Error("actor export adaptation did not apply");
  return `${prepared}\nglobalThis.CloakfoxTimingChild = CloakfoxTimingChild;`;
}

function makeOriginals(rafAvailable) {
  const calls = { timeout: [], interval: [], raf: [] };
  const timeout = function setTimeout(handler, delay, ...args) {
    calls.timeout.push({ handler, delay, args });
    return `timeout-${calls.timeout.length}`;
  };
  const interval = function setInterval(handler, delay, ...args) {
    calls.interval.push({ handler, delay, args });
    return `interval-${calls.interval.length}`;
  };
  const raf = rafAvailable ? function requestAnimationFrame(callback) {
    calls.raf.push({ callback });
    callback(100);
    return "raf-1";
  } : undefined;
  return { calls, timeout, interval, raf };
}

function installActor(actorSource, { enabled = true, hasSeed = true, rafAvailable = true } = {}) {
  const originals = makeOriginals(rafAvailable);
  const pageWin = {
    setTimeout: originals.timeout,
    setInterval: originals.interval,
    requestAnimationFrame: originals.raf,
  };
  const seedKey = "cloakfox.container.7.timing_seed";
  const context = vm.createContext({
    JSWindowActorChild: class {},
    Services: {
      prefs: { getBoolPref: () => enabled },
      cpmm: { sharedData: { get: () => hasSeed ? { [seedKey]: SEED_B64 } : {} } },
    },
    Cu: {
      exportFunction: fn => fn,
      waiveXrays: fn => fn,
    },
    atob: b64 => Buffer.from(b64, "base64").toString("binary"),
  });
  vm.runInContext(prepareActorSource(actorSource), context, { filename: "CloakfoxTimingChild.sys.mjs" });
  const child = new context.CloakfoxTimingChild();
  child.contentWindow = {
    docShell: { browsingContext: { originAttributes: { userContextId: 7 } } },
    wrappedJSObject: pageWin,
  };
  child.handleEvent({ type: "DOMDocElementInserted" });
  return { pageWin, originals };
}

function assertTimersEffective(actorSource, { rafAvailable = true } = {}) {
  const { pageWin, originals } = installActor(actorSource, { rafAvailable });
  assert.notEqual(pageWin.setTimeout, originals.timeout, "setTimeout must remain installed");
  assert.notEqual(pageWin.setInterval, originals.interval, "setInterval must remain installed");
  for (let i = 0; i < 12; i++) {
    pageWin.setTimeout(() => {}, 10);
    pageWin.setInterval(() => {}, 10);
  }
  assert.ok(originals.calls.timeout.some(call => call.delay > 10 && call.delay <= 12),
    "setTimeout wrapper must consume PRNG jitter");
  assert.ok(originals.calls.interval.some(call => call.delay > 10 && call.delay <= 12),
    "setInterval wrapper must consume PRNG jitter");

  if (!rafAvailable) {
    assert.equal(pageWin.requestAnimationFrame, undefined,
      "rAF must remain unavailable outside its native availability guard");
    return;
  }
  assert.notEqual(pageWin.requestAnimationFrame, originals.raf, "rAF must remain installed");
  let timestamp;
  pageWin.requestAnimationFrame(value => { timestamp = value; });
  assert.ok(timestamp > 100 && timestamp < 100.1,
    "rAF wrapper must consume PRNG noise in its callback timestamp");
}

function assertGeckoOwnsPerformanceNow(patch, actor) {
  const method = reconstructPatchedNow(patch);
  const returns = enumerateReturns(method);
  assert.equal(returns.length, 2, "Performance::Now must retain only its early and terminal returns");
  assert.deepEqual(returns[0], {
    expression: "rawTime", source: "context", depth: 2, index: 2,
  }, "only the pre-existing system-principal early return may expose rawTime");
  assert.deepEqual(returns[1], {
    expression: "PresentTimestamp(reduced)", source: "added", depth: 1, index: method.length - 2,
  }, "Performance::Now must terminally present the reduced clock");
  assert.match(method.map(line => line.code).join("\n"),
    /const DOMHighResTimeStamp reduced =\n      nsRFPService::ReduceTimePrecisionAsMSecs\(\n          rawTime, GetRandomTimelineSeed\(\), mRTPCallerType\);/);
  assertActorHasNoClockOwnership(actor);
}

function fixtureActor() {
  const mode = process.env.CLOAKFOX_TIMING_MUTATION;
  if (!mode) return timingActor;
  const [kind, detail, api] = mode.split(":");
  if (kind === "clock") return mutateClock(timingActor, detail);
  const spec = WRAPPERS.find(wrapper => wrapper.api === api);
  if (kind === "wrapper" && spec) return mutateTimerPath(timingActor, spec, detail);
  if (mode === "early-return") return mutateEarlyReturn(timingActor);
  if (mode === "raf-outside") return mutateRafOutsideGuard(timingActor);
  throw new Error(`unknown CLOAKFOX_TIMING_MUTATION: ${mode}`);
}

test("Gecko owns the complete reduced performance.now presentation path", () => {
  assertGeckoOwnsPerformanceNow(performancePatch, fixtureActor());
});

test("shipped timing actor installs effective timer and rAF wrappers", () => {
  assertTimersEffective(fixtureActor());
});

test("timing actor respects enabled, seed, and rAF availability gates", () => {
  for (const options of [{ enabled: false }, { hasSeed: false }]) {
    const { pageWin, originals } = installActor(timingActor, options);
    assert.equal(pageWin.setTimeout, originals.timeout);
    assert.equal(pageWin.setInterval, originals.interval);
    assert.equal(pageWin.requestAnimationFrame, originals.raf);
  }
  assertTimersEffective(timingActor, { rafAvailable: false });
});

test("vm adaptation requires the shipped actor export boundary", () => {
  assert.throws(() => prepareActorSource(
    timingActor.replace("export class CloakfoxTimingChild", "class CloakfoxTimingChild")
  ), /export adaptation did not apply/);
});

test("clock lexical gate ignores comments and unrelated literals", () => {
  assertActorHasNoClockOwnership(
    `${timingActor}\n// pageWin.performance.now is native\nconst note = "performance.now is native";`
  );
});

for (const mode of ["direct", "alias", "computed"]) {
  test(`clock gate rejects ${mode} performance.now ownership`, () => {
    assert.throws(() => assertGeckoOwnsPerformanceNow(performancePatch, mutateClock(timingActor, mode)),
      /forbidden clock ownership token/);
  });
}

test("Gecko gate rejects an added outer raw return before reduction", () => {
  const mutant = performancePatch.replace(
    "+  const DOMHighResTimeStamp reduced =",
    "+  return rawTime;\n+\n+  const DOMHighResTimeStamp reduced ="
  );
  assert.throws(() => assertGeckoOwnsPerformanceNow(mutant, timingActor), /only its early and terminal returns/);
});

test("Gecko gate rejects dead presentation followed by a raw reduced return", () => {
  const mutant = performancePatch.replace(
    "+  return PresentTimestamp(reduced);\n+}",
    "+  if (false) {\n+    return PresentTimestamp(reduced);\n+  }\n+  return reduced;\n+}"
  );
  assert.throws(() => assertGeckoOwnsPerformanceNow(mutant, timingActor), /only its early and terminal returns/);
});

test("Gecko gate rejects an outer raw reduced return", () => {
  const mutant = performancePatch.replace(
    "+  return PresentTimestamp(reduced);",
    "+  return reduced;"
  );
  assert.throws(() => assertGeckoOwnsPerformanceNow(mutant, timingActor), /terminally present/);
});

for (const spec of WRAPPERS) {
  for (const mode of ["comment", "prng", "restore"]) {
    test(`${spec.api} harness rejects ${mode} mutation`, () => {
      assert.throws(() => assertTimersEffective(mutateTimerPath(timingActor, spec, mode)),
        spec.api === "requestAnimationFrame" ? /rAF|requestAnimationFrame/ : new RegExp(spec.api));
    });
  }
}

test("timer harness rejects an unconditional return before installation", () => {
  assert.throws(() => assertTimersEffective(mutateEarlyReturn(timingActor)), /setTimeout must remain installed/);
});

test("timer harness rejects rAF assignment outside its availability guard", () => {
  assert.throws(() => assertTimersEffective(mutateRafOutsideGuard(timingActor), { rafAvailable: false }),
    /rAF must remain unavailable/);
});
