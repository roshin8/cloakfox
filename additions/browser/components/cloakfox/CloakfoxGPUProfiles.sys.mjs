import {createReferenceGPUProfile} from './CloakfoxGPUReferenceProfiles.sys.mjs';
/* MPL-2.0: privileged, owner-bound coherent GPU capability descriptors. */
import {GPU_PROFILE_CATALOG, GPU_PROFILE_REQUIREMENTS, GPU_PROFILE_CATALOG_VERSION} from './CloakfoxGPUCatalog.sys.mjs';
export function gpuFamily(renderer) {
  const value = String(renderer).toLowerCase();
  if (/swiftshader|llvmpipe|softpipe|software/.test(value)) return null;
  if (/apple/.test(value)) return 'apple';
  if (/intel/.test(value)) return 'intel';
  if (/amd|radeon|firepro/.test(value)) return 'amd';
  if (/nvidia|geforce|quadro/.test(value)) return 'nvidia';
  return null;
}
// Cohort selection never samples individual limits. Native code independently
// validates the same ceiling constraints and refuses unsupported contexts.
export function eligibleGPUProfiles(config, family) {
  const number = {apple:1,intel:2,amd:3,nvidia:4}[family];
  if (!number) return [];
  for (const key of ['webGl:parameters','webGl2:parameters']) {
    const table=config[key];
    if (table !== undefined && (!table || typeof table !== 'object' || Array.isArray(table))) throw new Error('Invalid persona GPU capability table');
  }
  return GPU_PROFILE_CATALOG.filter(profile => {
    if (!(profile.familyMask & (1 << (number-1)))) return false;
    return ['webGl:parameters','webGl2:parameters'].every((key,index) => {
      const table=config[key];if (table === undefined) return true;
      return GPU_PROFILE_REQUIREMENTS.every(requirement => {
        if (requirement.webgl2Only && !index || !Object.hasOwn(table,requirement.pname)) return true;
        const minimum=profile[requirement.field]*(requirement.multiplier||1), value=table[requirement.pname];
        const components=requirement.components||1;
        if (components===1) return Number.isFinite(value) && value>=minimum;
        return Array.isArray(value) && value.length===components && value.every(x=>Number.isFinite(x)&&x>=minimum);
      });
    });
  }).map(profile=>profile.id);
}
export function createGPUProfile(config, owner) {
  if (config['rendering:gpu_observed'] !== undefined && typeof config['rendering:gpu_observed'] !== 'boolean') throw new Error('Invalid observed GPU request');
  if (config['rendering:gpu_observed'] === true && config['rendering:gpu_reference'] !== true) throw new Error('Observed GPU requires reference rendering');
  if (config['rendering:gpu_reference'] === true) return createReferenceGPUProfile(config, owner);
  if (!Number.isInteger(owner) || owner < 0 || owner > 0xffffffff) throw new Error('GPU profile requires an exact container owner');
  const renderer = config['webGl:renderer'], vendor = config['webGl:vendor'];
  const family = typeof renderer === 'string' && gpuFamily(renderer);
  if (!family || typeof vendor !== 'string' || !vendor || renderer.length > 512 || vendor.length > 256) throw new Error('GPU profiles require an Apple, Intel, AMD or NVIDIA BrowserForge persona');
  if (typeof config['fingerprint:secret'] !== 'string' || !/^[A-Za-z0-9+/]{43}=$/.test(config['fingerprint:secret']) || !Number.isInteger(config['canvas:seed']) || config['canvas:seed'] < 0 || config['canvas:seed'] > 0xffffffff) throw new Error('GPU profile identity is missing or invalid');
  const catalog=eligibleGPUProfiles(config,family);
  if (!catalog.length) throw new Error('Persona GPU overrides conflict with every coherent catalog profile');
  return {version:GPU_PROFILE_CATALOG_VERSION,owner,family,renderer,vendor,catalog};
}
