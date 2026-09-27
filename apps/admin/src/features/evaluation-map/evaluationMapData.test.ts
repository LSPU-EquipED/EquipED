import { describe, expect, it } from 'vitest';
import {
  knowledgeConsumers,
  knowledgeSourceKinds,
  knowledgeSources,
} from './evaluationMapData';

describe('evaluationMapData', () => {
  it('defines 4 authoritative sources and 5 evaluation consumers', () => {
    expect(knowledgeSources).toHaveLength(4);
    expect(knowledgeConsumers).toHaveLength(5);
  });

  it('maps each authoritative source to evaluation consumers', () => {
    const rubric = knowledgeSources.find((source) => source.id === 'rubrics');

    expect(rubric?.consumers).toEqual(
      expect.arrayContaining(['sme', 'coordinator', 'gad', 'itso', 'synthesis']),
    );
    expect(knowledgeConsumers.map((consumer) => consumer.id)).toEqual(
      expect.arrayContaining(rubric?.consumers ?? []),
    );

    const policy = knowledgeSources.find((source) => source.id === 'policy');
    expect(policy?.consumers).toContain('itso');
  });

  it('contains truthful illustrative role distribution and copy across sources', () => {
    const referenceSources = knowledgeSources.filter((source) => source.role === 'reference');
    const reviewTopicSources = knowledgeSources.filter((source) => source.role === 'review-topic');

    expect(referenceSources).toHaveLength(3);
    expect(reviewTopicSources).toHaveLength(1);
    expect(reviewTopicSources[0]?.id).toBe('curriculum');

    // Verify absence of unsupported operational claims
    for (const source of knowledgeSources) {
      expect(source.referenceContext).not.toMatch(/revision \d+/i);
      expect(source.referenceContext).not.toMatch(/active/i);
      expect(source.referenceContext).not.toMatch(/updated from/i);
      expect(source.referenceContext).not.toMatch(/indexed/i);
      expect(source.referenceContext).not.toMatch(/ready/i);
      expect(source.referenceContext).not.toMatch(/available/i);
    }
  });

  it('provides filter categories including all and specific source kinds', () => {
    expect(knowledgeSourceKinds.map((k) => k.value)).toEqual([
      'all',
      'rubric',
      'syllabus',
      'curriculum',
      'policy',
    ]);
  });
});
