import { describe, expect, it } from 'vitest';
import {
  DEFAULT_TRAINING_AGENT_ID,
  TRAINING_AGENTS,
  TRAINING_AGENT_IDS,
  isTrainingAgentId,
} from '../trainingAgents';

describe('trainingAgents contract', () => {
  it('defines the expected agent ids and defaults to coordinator', () => {
    expect(TRAINING_AGENT_IDS).toEqual(['coordinator', 'sme', 'gad', 'itso']);
    expect(DEFAULT_TRAINING_AGENT_ID).toBe('coordinator');
    expect(TRAINING_AGENTS.map((a) => a.id)).toEqual(['coordinator', 'sme', 'gad', 'itso']);
  });

  it('validates training agent IDs via isTrainingAgentId', () => {
    expect(isTrainingAgentId('coordinator')).toBe(true);
    expect(isTrainingAgentId('sme')).toBe(true);
    expect(isTrainingAgentId('gad')).toBe(true);
    expect(isTrainingAgentId('itso')).toBe(true);
    expect(isTrainingAgentId('invalid')).toBe(false);
    expect(isTrainingAgentId('')).toBe(false);
    expect(isTrainingAgentId(null)).toBe(false);
    expect(isTrainingAgentId(undefined)).toBe(false);
    expect(isTrainingAgentId(123)).toBe(false);
  });
});
