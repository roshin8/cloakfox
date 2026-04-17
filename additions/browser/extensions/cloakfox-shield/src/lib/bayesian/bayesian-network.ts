/**
 * BayesianNetwork — generates statistically coherent fingerprints.
 * Ported from Apify fingerprint-suite (Apache-2.0).
 * Modified: loads JSON directly (no AdmZip), uses seeded PRNG.
 */

import { BayesianNode } from './bayesian-node';

export interface NetworkDefinition {
  nodes: Array<{
    name: string;
    parentNames: string[];
    possibleValues: string[];
    conditionalProbabilities: any;
  }>;
}

/** Random number generator interface — pass our seeded PRNG */
export interface RandomFn {
  /** Returns a number in [0, 1) */
  next(): number;
}

export class BayesianNetwork {
  private nodesInSamplingOrder: BayesianNode[] = [];
  nodesByName: Record<string, BayesianNode> = {};

  constructor(definition: NetworkDefinition) {
    this.nodesInSamplingOrder = definition.nodes.map(
      (nodeDef) => new BayesianNode(nodeDef)
    );
    this.nodesByName = Object.fromEntries(
      this.nodesInSamplingOrder.map((node) => [node.name, node])
    );
  }

  /** Generate a sample from the network using the provided RNG */
  generateSample(rng: RandomFn, inputValues: Record<string, string> = {}): Record<string, string> {
    const sample = { ...inputValues };
    for (const node of this.nodesInSamplingOrder) {
      if (!(node.name in sample)) {
        sample[node.name] = node.sample(sample, rng.next());
      }
    }
    return sample;
  }

  /**
   * Generate a sample consistent with the given value restrictions.
   * Returns empty object if no consistent sample can be found.
   */
  generateConsistentSample(
    rng: RandomFn,
    valuePossibilities: Record<string, string[]> = {}
  ): Record<string, string> {
    return this.recursiveConsistentSample(rng, {}, valuePossibilities, 0);
  }

  private recursiveConsistentSample(
    rng: RandomFn,
    sampleSoFar: Record<string, string>,
    valuePossibilities: Record<string, string[]>,
    depth: number
  ): Record<string, string> {
    if (depth >= this.nodesInSamplingOrder.length) return sampleSoFar;

    const bannedValues: string[] = [];
    const node = this.nodesInSamplingOrder[depth];
    let sampleValue: string | false;

    do {
      sampleValue = node.sampleWithRestrictions(
        sampleSoFar,
        valuePossibilities[node.name],
        bannedValues,
        rng.next()
      );
      if (!sampleValue) break;

      sampleSoFar[node.name] = sampleValue;

      const sample = this.recursiveConsistentSample(
        rng, sampleSoFar, valuePossibilities, depth + 1
      );
      if (Object.keys(sample).length !== 0) return sample;

      bannedValues.push(sampleValue);
    } while (sampleValue);

    return {};
  }
}
