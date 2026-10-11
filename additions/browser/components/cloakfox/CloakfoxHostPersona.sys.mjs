/* MPL-2.0. Keep native rendering and the sampled operating system coherent. */
export function normalizeHostOS(os) {
  const value = String(os).toLowerCase();
  if (["darwin", "macos", "mac"].includes(value)) return "macos";
  if (["winnt", "windows", "win32"].includes(value)) return "windows";
  if (value === "linux") return "linux";
  throw new Error(`Unsupported persona host OS: ${os}`);
}

export function fingerprintOS(fp) {
  const ua = fp?.userAgent || "";
  if (ua.includes("Windows NT")) return "windows";
  if (ua.includes("Macintosh")) return "macos";
  if (ua.includes("Linux")) return "linux";
  return null;
}

// Rejection sampling preserves the entire Bayesian joint distribution
// conditioned on host OS. Never rewrite a foreign tuple's UA/platform while
// retaining its foreign GPU, display or hardware samples. Bounded failure is
// explicit; silently returning a foreign tuple would violate the setting.
export function sampleHostFingerprint(prng, sampleFingerprint, os) {
  const host = normalizeHostOS(os);
  for (let attempt = 0; attempt < 4096; attempt++) {
    const fp = sampleFingerprint(prng);
    if (fingerprintOS(fp) === host) return fp;
  }
  throw new Error(`No ${host} persona in the fingerprint distribution`);
}
