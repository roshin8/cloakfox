/* MPL-2.0: privileged, owner-bound bounded GPU persona descriptors. */
export function gpuFamily(renderer) {
  const value = String(renderer).toLowerCase();
  if (/swiftshader|llvmpipe|softpipe|software/.test(value)) return null;
  if (/apple/.test(value)) return 'apple';
  if (/intel/.test(value)) return 'intel';
  if (/amd|radeon|firepro/.test(value)) return 'amd';
  if (/nvidia|geforce|quadro/.test(value)) return 'nvidia';
  return null;
}
// These are deliberately bounded virtual profiles, not promises of native
// vendor-driver parity. Native host validation independently restricts every
// controlled resource; unsupported backing contexts must fail creation.
export function createGPUProfile(config, owner) {
  if (!Number.isInteger(owner) || owner < 0 || owner > 0xffffffff) throw new Error('GPU profile requires an exact container owner');
  const renderer = config['webGl:renderer'], vendor = config['webGl:vendor'];
  const family = typeof renderer === 'string' && gpuFamily(renderer);
  if (!family || typeof vendor !== 'string' || !vendor || renderer.length > 512 || vendor.length > 256) throw new Error('GPU profiles require an Apple, Intel, AMD or NVIDIA BrowserForge persona');
  if (typeof config['fingerprint:secret'] !== 'string' || !/^[A-Za-z0-9+/]{43}=$/.test(config['fingerprint:secret']) || !Number.isInteger(config['canvas:seed']) || config['canvas:seed'] < 0 || config['canvas:seed'] > 0xffffffff) throw new Error('GPU profile identity is missing or invalid');
  const texture = {apple:6144,intel:4096,amd:7168,nvidia:8192}[family];
  for (const key of ['webGl:parameters','webGl2:parameters']) {
    const table = config[key];
    if (table === undefined) continue;
    if (!table || typeof table !== 'object' || Array.isArray(table)) throw new Error('Invalid persona GPU capability table');
    for (const [pname,minimum] of [[3379,texture],[34076,texture],[34024,texture],[34921,16],[36347,511],[36349,479],[35661,32],[34930,16],[35660,16]]) {
      if (Object.hasOwn(table,pname) && (!Number.isFinite(table[pname]) || table[pname] < minimum)) throw new Error('Persona GPU override conflicts with the bounded profile: '+pname);
    }
  }
  return {version:1,owner,family,renderer,vendor};
}
