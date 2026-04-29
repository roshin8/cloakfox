/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

/* Cloakfox: runtime BrowserForge Bayesian network sampler.
 *
 * JS port of browserforge/bayesian_network.py — generates fresh
 * fingerprints from the filtered desktop-Firefox network shipped in
 * CloakfoxBFNetwork.sys.mjs. Replaces the predefined-pool approach
 * (CloakfoxPersonaData) with on-demand sampling so each container
 * gets a unique fingerprint drawn from the real-world distribution
 * rather than one of 30 fixed bundles.
 *
 * Sampling order is topological: every non-root node is conditioned
 * on its parents (almost always just userAgent in this network), so
 * walking nodes in the order BrowserForge serialized them produces a
 * coherent fingerprint where webGl renderer matches platform, screen
 * matches devicePixelRatio, etc. — coherence comes for free from the
 * joint distribution.
 *
 * Determinism: callers pass a seeded PRNG (xorshift / mulberry32).
 * Same seed → same fingerprint, so a container's identity persists
 * across browser restarts via the master seed pref.
 */

import { NETWORK } from "resource:///modules/CloakfoxBFNetwork.sys.mjs";

// Walk the conditionalProbabilities tree using parent values to descend
// "deeper", falling back to "skip" when a parent's value isn't in the
// branch. Returns the leaf {value: probability} dict at the end.
function getProbsGivenParents(node, parentValues) {
  let probs = node.conditionalProbabilities;
  for (const parentName of node.parentNames || []) {
    const pv = parentValues[parentName];
    if (probs && probs.deeper && pv in probs.deeper) {
      probs = probs.deeper[pv];
    } else if (probs && probs.skip) {
      probs = probs.skip;
    } else {
      // No matching path — terminal probabilities live here as-is OR
      // we've fallen off the tree. Return what we have.
      return probs || {};
    }
  }
  return probs || {};
}

// Cumulative-probability sampling: walk possibilities, accumulate p,
// return the first one to exceed a [0,1) anchor. Identical algorithm
// to BrowserForge's Python implementation.
function sampleFromProbs(probs, prng) {
  const keys = Object.keys(probs);
  if (keys.length === 0) return null;
  const anchor = prng();
  let cum = 0;
  for (const k of keys) {
    cum += probs[k];
    if (cum > anchor) return k;
  }
  return keys[0];   // fallback for floating-point drift; matches Python
}

/**
 * Generate one full fingerprint sample from the network.
 *
 * @param {() => number} prng  Seeded PRNG returning [0, 1). Same seed →
 *                             same sample, so container identity persists.
 * @param {Object} [inputValues]  Pre-set values to lock; remaining
 *                                nodes will be sampled given these.
 *                                e.g. {userAgent: "Mozilla/5.0 (Mac...)"}
 * @returns {Object}  Flat dict of nodeName → sampled value.
 */
export function sampleFingerprint(prng, inputValues = {}) {
  const sample = { ...inputValues };
  for (const node of NETWORK.nodes) {
    if (node.name in sample) continue;
    const probs = getProbsGivenParents(node, sample);
    const value = sampleFromProbs(probs, prng);
    if (value !== null) sample[node.name] = value;
  }
  // BrowserForge encodes some compound values as JSON strings prefixed
  // with "*STRINGIFIED*" (e.g. screen, fonts arrays). Unpack them so
  // downstream code sees plain objects/arrays. Also handle the
  // *MISSING_VALUE* sentinel (BF uses it where the trained data had no
  // observation).
  for (const k of Object.keys(sample)) {
    const v = sample[k];
    if (v === "*MISSING_VALUE*") {
      sample[k] = null;
    } else if (typeof v === "string" && v.startsWith("*STRINGIFIED*")) {
      try {
        sample[k] = JSON.parse(v.slice("*STRINGIFIED*".length));
      } catch (_e) { /* leave as-is on parse error */ }
    }
  }
  return sample;
}

/** Lookup possible values for a node by name (UI / debugging). */
export function getNodeValues(name) {
  const node = NETWORK.nodes.find(n => n.name === name);
  return node ? node.possibleValues || [] : [];
}

/** All node names in topological order. Useful for UI listing. */
export function getNodeNames() {
  return NETWORK.nodes.map(n => n.name);
}
