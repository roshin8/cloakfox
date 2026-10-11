/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

// Gecko computes the top-level schemeful site using its public suffix list,
// and propagates CookieJarSettings to frames and workers. Remove the foreign
// ancestor bit only: a tracker frame must use its publisher's site key.
export function canonicalSiteKey(partitionKey) {
  if (typeof partitionKey !== "string") return "";
  const site = /^(\([a-z][a-z0-9+.-]*,[^(),\s]+)(?:,f)?\)$/.exec(partitionKey);
  if (site) return `${site[1]})`;
  // Gecko's null-principal partition key: fresh UUID, never a shared "null".
  return /^[0-9a-f-]{36}\.mozilla$/i.test(partitionKey) ? partitionKey : "";
}

function sha256(bytes) {
  const hash = Cc["@mozilla.org/security/hash;1"].createInstance(Ci.nsICryptoHash);
  hash.init(Ci.nsICryptoHash.SHA256);
  hash.update(bytes, bytes.length);
  return Uint8Array.from(hash.finish(false), c => c.charCodeAt(0));
}

// RFC 2104 HMAC using NSS's SHA-256 through the synchronous chrome hash API.
// The key is the ASCII base64 encoding of the complete 32-byte master secret.
// The protocol and byte order match CloakfoxSiteSeedCore.hpp / NSS HMAC.
export function siteSeedBytes(secret, partitionKey, vector, baseSeed) {
  const site = canonicalSiteKey(partitionKey);
  if (!site || !/^[A-Za-z0-9+/]{43}=$/.test(secret || "") ||
      !Number.isInteger(baseSeed) || baseSeed <= 0 || baseSeed > 0xffffffff ||
      !/^[a-zA-Z0-9:_-]+$/.test(vector)) return null;
  const encoder = new TextEncoder();
  const key = encoder.encode(secret);
  const input = encoder.encode(`cloakfox-site-v1\n${vector}\n${baseSeed}\n${site}`);
  const inner = new Uint8Array(64 + input.length);
  const outer = new Uint8Array(96);
  for (let i = 0; i < 64; i++) {
    inner[i] = (key[i] || 0) ^ 0x36;
    outer[i] = (key[i] || 0) ^ 0x5c;
  }
  inner.set(input, 64);
  outer.set(sha256(inner), 64);
  return sha256(outer);
}

export function deriveSiteSeed(secret, partitionKey, vector, baseSeed) {
  const bytes = siteSeedBytes(secret, partitionKey, vector, baseSeed);
  if (!bytes) return 0;
  return ((bytes[0] * 0x1000000 + (bytes[1] << 16) +
    (bytes[2] << 8) + bytes[3]) >>> 0) || 1;
}

export function siteSeedForWindow(win, snapshot, vector) {
  try {
    const ucid = win.docShell.browsingContext.originAttributes.userContextId;
    const cfg = JSON.parse(snapshot[`cloakfox.s.cloak_cfg_${ucid}`] || "null");
    return deriveSiteSeed(cfg?.["fingerprint:secret"],
      win.document.cookieJarSettings.partitionKey, vector, cfg?.[vector]);
  } catch (_e) { return 0; }
}

// Actor-only vectors keep a full PRNG seed but use the same top-level context.
export function actorSiteSeed(win, snapshot, vector, seedB64) {
  try {
    const bytes = siteSeedBytes(seedB64, win.document.cookieJarSettings.partitionKey,
      vector, 1);
    return bytes ? btoa(String.fromCharCode(...bytes)) : "";
  } catch (_e) { return ""; }
}
