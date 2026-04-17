/**
 * BayesianNode — single node in a Bayesian network.
 * Ported from Apify fingerprint-suite (Apache-2.0).
 * Modified to accept seeded PRNG instead of Math.random().
 */

interface NodeDefinition {
  name: string;
  parentNames: string[];
  possibleValues: string[];
  conditionalProbabilities: any;
}

export class BayesianNode {
  private nodeDefinition: NodeDefinition;

  constructor(nodeDefinition: NodeDefinition) {
    this.nodeDefinition = nodeDefinition;
  }

  /** Extract conditional probabilities given known parent values */
  private getProbabilitiesGivenKnownValues(
    parentValues: Record<string, string> = {}
  ): Record<string, number> {
    let probabilities = this.nodeDefinition.conditionalProbabilities;

    for (const parentName of this.parentNames) {
      const parentValue = parentValues[parentName];
      if (parentValue in probabilities.deeper) {
        probabilities = probabilities.deeper[parentValue];
      } else {
        probabilities = probabilities.skip;
      }
    }
    return probabilities;
  }

  /** Sample a value using weighted probabilities and a random number [0,1) */
  private sampleFromPossibilities(
    possibleValues: string[],
    totalProbability: number,
    probabilities: Record<string, number>,
    random: number,
  ): string {
    let chosenValue = possibleValues[0];
    const anchor = random * totalProbability;
    let cumulative = 0;
    for (const value of possibleValues) {
      cumulative += probabilities[value];
      if (cumulative > anchor) {
        chosenValue = value;
        break;
      }
    }
    return chosenValue;
  }

  /** Sample from conditional distribution given parent values */
  sample(parentValues: Record<string, string> = {}, random: number): string {
    const probabilities = this.getProbabilitiesGivenKnownValues(parentValues);
    const possibleValues = Object.keys(probabilities);
    return this.sampleFromPossibilities(possibleValues, 1.0, probabilities, random);
  }

  /** Sample with restrictions on possible values */
  sampleWithRestrictions(
    parentValues: Record<string, string>,
    valuePossibilities: string[] | undefined,
    bannedValues: string[],
    random: number,
  ): string | false {
    const probabilities = this.getProbabilitiesGivenKnownValues(parentValues);
    let totalProbability = 0;
    const validValues: string[] = [];
    const valuesInDistribution = Object.keys(probabilities);
    const possibleValues = valuePossibilities || valuesInDistribution;

    for (const value of possibleValues) {
      if (!bannedValues.includes(value) && valuesInDistribution.includes(value)) {
        validValues.push(value);
        totalProbability += probabilities[value];
      }
    }

    if (validValues.length === 0) return false;
    return this.sampleFromPossibilities(validValues, totalProbability, probabilities, random);
  }

  get name(): string {
    return this.nodeDefinition.name;
  }

  get parentNames(): string[] {
    return this.nodeDefinition.parentNames;
  }

  get possibleValues(): string[] {
    return this.nodeDefinition.possibleValues;
  }
}
