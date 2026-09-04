/* Regression gates for native performance-clock ownership and actor timers.
 *
 *   node --test tests/fingerprint/test_timing_ownership.mjs
 */
import test from "node:test";
import assert from "node:assert/strict";
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
  { api: "setTimeout", original: "origSetTimeout", installDepth: 1 },
  { api: "setInterval", original: "origSetInterval", installDepth: 1 },
  { api: "requestAnimationFrame", original: "origRAF", installDepth: 2 },
];

function extractBalancedBlock(source, start) {
  const open = source.indexOf("{", start);
  if (open < 0) throw new Error("block opening brace not found");
  let depth = 0;
  for (let i = open; i < source.length; i++) {
    if (source[i] === "{") depth++;
    else if (source[i] === "}") {
      depth--;
      if (depth === 0) return source.slice(start, i + 1);
    }
  }
  throw new Error("unbalanced block");
}

function extractAddedNowMethod(patch) {
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

  const firstAdded = lines.findIndex(line =>
    line === "+  const DOMHighResTimeStamp reduced ="
  );
  if (firstAdded < 0) throw new Error("added reduced-clock declaration not found");

  let depth = 1; // Opening brace declared by the Now() hunk header.
  const tail = [];
  for (let i = firstAdded; i < lines.length; i++) {
    if (!lines[i].startsWith("+")) continue;
    const code = lines[i].slice(1);
    tail.push(code);
    for (const char of code) {
      if (char === "{") depth++;
      else if (char === "}") depth--;
    }
    if (depth === 0) return tail.join("\n");
    if (depth < 0) throw new Error("added Now() tail closed too many braces");
  }
  throw new Error("added Now() tail did not close its declared method body");
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

function extractInstallBody(actor) {
  const installStart = actor.indexOf("\n  #install() {");
  if (installStart < 0) throw new Error("timing actor #install not found");
  return extractBalancedBlock(actor, installStart + 3);
}

function braceDepthAt(source, index) {
  let depth = 0;
  for (let i = 0; i < index; i++) {
    if (source[i] === "{") depth++;
    else if (source[i] === "}") depth--;
  }
  return depth;
}

function apiAssignments(source, api) {
  return [...source.matchAll(new RegExp(`\\bpageWin\\.${api}\\s*=`, "g"))]
    .map(match => match.index);
}

function extractActorWrapper(install, original) {
  const originalStart = install.indexOf(`const ${original} =`);
  if (originalStart < 0) throw new Error(`${original} declaration not found`);
  const wrapperStart = install.indexOf("Cu.exportFunction(function", originalStart);
  if (wrapperStart < 0) throw new Error(`${original} wrapper not found`);
  return extractBalancedBlock(install, wrapperStart);
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

function assertGeckoOwnsPerformanceNow(patch, actor) {
  const addedNow = extractAddedNowMethod(patch);
  assert.match(addedNow, /^  const DOMHighResTimeStamp reduced =\n      nsRFPService::ReduceTimePrecisionAsMSecs\(\n          rawTime, GetRandomTimelineSeed\(\), mRTPCallerType\);/);
  assert.equal((addedNow.match(/\breturn\b/g) || []).length, 1,
    "added Performance::Now body must contain exactly one terminal return");
  assert.match(addedNow, /\n  return PresentTimestamp\(reduced\);\n}$/,
    "added Performance::Now body must terminally return PresentTimestamp(reduced)");
  assert.doesNotMatch(addedNow, /return\s+(?:reduced|rawTime)\s*;/,
    "added Performance::Now body must not return an unpresented clock");
  assertActorHasNoClockOwnership(actor);
}

function assertActorRetainsTimerPaths(actor) {
  const install = extractInstallBody(actor);
  assert.match(actor, /function\s+makePRNG\s*\(\s*seedBytes\s*\)/,
    "timing actor must retain the shared PRNG definition");
  assert.match(install, /const\s+prng\s*=\s*makePRNG\s*\(\s*b64ToBytes\s*\(\s*seedB64\s*\)\s*\)/,
    "timer paths must share the per-container PRNG");

  for (const spec of WRAPPERS) {
    const assignments = apiAssignments(install, spec.api);
    assert.equal(assignments.length, 1,
      `${spec.api} must have one effective installation, without restoration`);
    assert.equal(braceDepthAt(install, assignments[0]), spec.installDepth,
      `${spec.api} installation must be on its effective #install path`);
    assert.match(install.slice(assignments[0]),
      new RegExp(`^pageWin\\.${spec.api}\\s*=\\s*setNativeIdentity\\s*\\(\\s*Cu\\.exportFunction`),
      `${spec.api} must install its exported wrapper`);
    const wrapper = extractActorWrapper(install, spec.original);
    assert.match(wrapper, new RegExp(`\\b${spec.original}\\.call\\s*\\(`),
      `${spec.api} wrapper must delegate to ${spec.original}`);
    assert.match(wrapper, /\bprng\s*\(\s*\)/,
      `${spec.api} wrapper must consume the shared PRNG`);
  }

  const raf = WRAPPERS[2];
  const rafInstall = apiAssignments(install, raf.api)[0];
  const rafGuard = install.lastIndexOf(`if (typeof ${raf.original} === "function") {`, rafInstall);
  assert.ok(rafGuard >= 0 && braceDepthAt(install, rafGuard) === 1,
    "rAF installation must be guarded only by native rAF availability");
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
  if (mode === "remove") {
    return actor.replace(marker, `pageWin.disabled${spec.api} = setNativeIdentity`);
  }
  if (mode === "prng") {
    const statementEnd = findWrapperStatementEnd(actor, start);
    const before = actor.slice(0, start);
    const statement = actor.slice(start, statementEnd);
    const after = actor.slice(statementEnd);
    if (!statement.includes("prng()")) throw new Error(`${spec.api} PRNG call not found`);
    return `${before}${statement.replace("prng()", "0")}${after}`;
  }
  if (mode === "restore") {
    const end = findWrapperStatementEnd(actor, start);
    return `${actor.slice(0, end)}\n    pageWin.${spec.api} = ${spec.original};${actor.slice(end)}`;
  }
  if (mode === "dead") {
    const end = findWrapperStatementEnd(actor, start);
    const statement = actor.slice(start, end);
    return `${actor.slice(0, start)}if (false) {\n    ${statement}\n    }${actor.slice(end)}`;
  }
  throw new Error(`unknown ${spec.api} mutation: ${mode}`);
}

function fixtureActor() {
  const mode = process.env.CLOAKFOX_TIMING_MUTATION;
  if (!mode) return timingActor;
  const [kind, detail, api] = mode.split(":");
  if (kind === "clock") return mutateClock(timingActor, detail);
  const spec = WRAPPERS.find(wrapper => wrapper.api === api);
  if (kind === "wrapper" && spec) return mutateTimerPath(timingActor, spec, detail);
  throw new Error(`unknown CLOAKFOX_TIMING_MUTATION: ${mode}`);
}

test("Gecko owns the reduced performance.now presentation path", () => {
  assertGeckoOwnsPerformanceNow(performancePatch, fixtureActor());
});

test("timing actor retains all seeded timer and rAF paths", () => {
  assertActorRetainsTimerPaths(fixtureActor());
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

test("Gecko gate rejects dead presentation followed by a raw reduced return", () => {
  const mutant = performancePatch.replace(
    "+  return PresentTimestamp(reduced);\n+}",
    "+  if (false) {\n+    return PresentTimestamp(reduced);\n+  }\n+  return reduced;\n+}"
  );
  assert.throws(() => assertGeckoOwnsPerformanceNow(mutant, timingActor),
    /exactly one terminal return|terminally return/);
});

test("Gecko gate rejects an outer raw reduced return", () => {
  const mutant = performancePatch.replace(
    "+  return PresentTimestamp(reduced);",
    "+  return reduced;"
  );
  assert.throws(() => assertGeckoOwnsPerformanceNow(mutant, timingActor),
    /terminally return|unpresented clock/);
});

for (const spec of WRAPPERS) {
  for (const mode of ["remove", "prng", "restore", "dead"]) {
    test(`${spec.api} gate rejects ${mode} mutation`, () => {
      assert.throws(() => assertActorRetainsTimerPaths(mutateTimerPath(timingActor, spec, mode)),
        new RegExp(spec.api));
    });
  }
}
