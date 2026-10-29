/*
 * Local deterministic sampler for the pinned Scrapfly fpgen model projection.
 * Model observations never grant permissions or executable GPU capabilities.
 * The complete source archive and its Apache-2.0 attribution are packaged beside
 * this module. Cloakfox authored this sampler; no upstream Python runs at runtime.
 */
import { FPGEN_NETWORK } from "./CloakfoxFPGenNetwork.sys.mjs";

const NODES = new Map(FPGEN_NETWORK.nodes.map(node => [node.name, node]));
const BROWSERS = Object.freeze({firefox: "Firefox", chrome: "Chrome", edge: "Edge", safari: "Safari"});
const OS_NAMES = ["auto", "windows", "macos", "linux"];
const HARDWARE_NAMES = ["auto", "apple", "intel", "nvidia", "amd", "software", "other"];

function fail(message) { throw new Error("fpgen: " + message); }

function osForPlatform(platform) {
  if (/Windows NT/.test(platform)) return "windows";
  if (/Macintosh/.test(platform)) return "macos";
  if (/Linux/.test(platform) && !/Android/.test(platform)) return "linux";
  return null;
}

function hardwareForGPU(gpu) {
  const label = `${gpu.vendor} ${gpu.renderer}`;
  if (/llvmpipe|softpipe|swiftshader|software/i.test(label)) return "software";
  // Renderer describes the hardware; vendor may describe the ANGLE wrapper.
  if (/Intel/i.test(gpu.renderer)) return "intel";
  if (/NVIDIA|GeForce|Quadro/i.test(label)) return "nvidia";
  if (/AMD|Radeon|ATI Technologies/i.test(label)) return "amd";
  if (/Apple/i.test(label)) return "apple";
  return "other";
}

function distribution(name, evidence) {
  const node = NODES.get(name);
  let branch = node.conditionalProbabilities;
  for (const parent of node.parentNames) {
    const token = evidence[parent];
    if (!token || !Object.hasOwn(branch, token)) return [];
    branch = branch[token];
  }
  return Object.entries(branch);
}

const mass = entries => entries.reduce((sum, entry) => sum + entry[1], 0);

// Build only model-derived branch tables. These tables contain all supported
// source observations, never a container's chosen identity or random state.
function displayBranches(owner) {
  const screens = [];
  for (const [screen, weight] of distribution("screen", owner)) {
    const evidence = {...owner, screen};
    const orientations = [];
    for (const [orientation, orientationWeight] of distribution("matchMedia.mediaCss.orientation", evidence)) {
      const windows = distribution("window", {...evidence, "matchMedia.mediaCss.orientation":orientation});
      if (windows.length) orientations.push([{orientation, windows}, orientationWeight * mass(windows)]);
    }
    if (orientations.length) screens.push([{screen, orientations}, weight * mass(orientations)]);
  }
  return screens;
}

function memoryBranches(owner) {
  const memories = [];
  for (const [memory, weight] of distribution("navigator.deviceMemory", owner)) {
    const cpus = distribution("navigator.hardwareConcurrency", {...owner, "navigator.deviceMemory":memory});
    if (cpus.length) memories.push([{memory, cpus}, weight * mass(cpus)]);
  }
  return memories;
}

const OWNERS = new Map(NODES.get("browser").possibleValues.map(browser => {
  const platforms = [];
  for (const [platformInfo, probability] of distribution("platformInfo", {browser})) {
    const evidence = {browser, platformInfo};
    const screens = displayBranches(evidence);
    const gpus = distribution("gpu", evidence).map(([gpu, weight]) => {
      const memories = memoryBranches({...evidence, gpu});
      return [{gpu, memories}, weight * mass(memories)];
    }).filter(([, weight]) => weight > 0);
    if (screens.length && gpus.length && distribution("navigator.userAgent", evidence).length) {
      platforms.push({evidence, probability, screens, gpus});
    }
  }
  return [browser, platforms];
}));

function choose(entries, prng) {
  const total = entries.reduce((sum, entry) => sum + entry[1], 0);
  if (!(total > 0) || !Number.isFinite(total)) fail("no matching observations");
  const random = prng();
  if (!Number.isFinite(random) || random < 0 || random >= 1) fail("invalid random source; expected [0, 1)");
  let target = random * total;
  for (const [value, weight] of entries) {
    target -= weight;
    if (target < 0) return value;
  }
  return entries[entries.length - 1][0];
}

function validInteger(value, minimum, maximum) {
  return Number.isInteger(value) && value >= minimum && value <= maximum;
}

/** An explicit adapter boundary: never copy arbitrary object keys from data. */
export function adaptFPGenFingerprint(sample) {
  const ua = sample["navigator.userAgent"];
  const cpu = sample["navigator.hardwareConcurrency"];
  const sc = sample.screen;
  const win = sample.window;
  const gpu = sample.gpu;
  if (typeof ua !== "string" || ua.length > 1024 || !osForPlatform(ua)) fail("unsupported desktop user agent");
  if (!validInteger(cpu, 1, 256)) fail("invalid hardware concurrency observation");
  if (!sc || !validInteger(sc.width, 200, 16384) || !validInteger(sc.height, 200, 16384)) fail("invalid screen observation");
  if (!win || typeof win.devicePixelRatio !== "number" || !Number.isFinite(win.devicePixelRatio) || win.devicePixelRatio <= 0 || win.devicePixelRatio > 8) fail("invalid window observation");
  if (!gpu || ![gpu.vendor, gpu.renderer].every(v => typeof v === "string" && v.length > 0 && v.length <= 2048)) fail("invalid GPU observation");

  const screen = {width:sc.width, height:sc.height, devicePixelRatio:win.devicePixelRatio};
  // A few captured window layouts span monitors or include stale work areas.
  // Clamp geometry; the existing native mapper derives inner dimensions/chrome.
  screen.availWidth = validInteger(sc.availWidth, 1, 32768) ? Math.min(sc.availWidth, sc.width) : sc.width;
  screen.availHeight = validInteger(sc.availHeight, 1, 32768) ? Math.min(sc.availHeight, sc.height) : sc.height;
  for (const [name, maximum] of [["outerWidth", screen.availWidth], ["outerHeight", screen.availHeight]]) {
    if (validInteger(win[name], 1, 32768)) screen[name] = Math.min(win[name], maximum);
  }
  for (const name of ["availLeft", "availTop"]) {
    if (validInteger(sc[name], -32768, 32768)) screen[name] = sc[name];
  }
  for (const name of ["screenX", "screenY"]) {
    if (validInteger(win[name], -32768, 32768)) screen[name] = win[name];
  }
  return {userAgent:ua, hardwareConcurrency:cpu, screen, videoCard:{vendor:gpu.vendor, renderer:gpu.renderer}};
}

/**
 * Sample locally from the caller's container PRNG. No sample/seed cache exists.
 * Version is presentation metadata for bfToCloakKeys' existing UA normalizer;
 * it does not assert that the model recorded that version. Chromium has no
 * observed browser node and is explicitly unsupported, rather than using Chrome.
 */
export function sampleFPGenFingerprint(prng, {os = "auto", hardware = "auto", browser = "firefox", version = "auto"} = {}) {
  if (typeof prng !== "function") fail("a seeded random source is required");
  if (!OS_NAMES.includes(os)) fail("unknown operating system");
  if (!HARDWARE_NAMES.includes(hardware)) fail("unknown hardware family");
  if (!Object.hasOwn(BROWSERS, browser)) fail("unsupported browser identity family");
  if (version !== "auto" && version !== "random-recent" && !/^[1-9]\d{0,2}$/.test(String(version))) fail("invalid browser identity version");
  const values = FPGEN_NETWORK.values;
  const browserToken = NODES.get("browser").possibleValues.find(token => values[token] === BROWSERS[browser]);
  if (!browserToken) fail("browser absent from pinned model");

  // Joint conditioning weights each observed platform by its matching GPU mass.
  // This enumerates the complete small owner graph, avoiding rejection sampling,
  // beam truncation and upstream's uniform fallback for impossible constraints.
  const candidates = [];
  for (const owner of OWNERS.get(browserToken)) {
    const platformOS = osForPlatform(values[owner.evidence.platformInfo]);
    if (!platformOS || (os !== "auto" && os !== platformOS)) continue;
    for (const [gpu, gpuWeight] of owner.gpus) {
      const family = hardwareForGPU(values[gpu.gpu]);
      if (family === "apple" && platformOS !== "macos") continue;
      if (hardware !== "auto" && family !== hardware) continue;
      candidates.push([{owner, gpu}, owner.probability * mass(owner.screens) * gpuWeight]);
    }
  }
  if (!candidates.length) fail("no matching persona for this browser, OS and hardware family");
  const {owner, gpu} = choose(candidates, prng);
  const screen = choose(owner.screens, prng);
  const orientation = choose(screen.orientations, prng);
  const memory = choose(gpu.memories, prng);
  return adaptFPGenFingerprint({
    "navigator.userAgent": values[choose(distribution("navigator.userAgent", owner.evidence), prng)],
    "navigator.hardwareConcurrency": values[choose(memory.cpus, prng)],
    screen: values[screen.screen],
    window: values[choose(orientation.windows, prng)],
    gpu: values[gpu.gpu],
  });
}
