import { describe, expect, it } from 'vitest';
import { getActiveMapIds } from './evaluationMapData';

describe('evaluation map dependencies', () => {
  it('lights every scorecard input while excluding the standalone syllabus path', () => {
    const { activeNodes } = getActiveMapIds('scorecard');

    expect([...activeNodes]).toEqual(
      expect.arrayContaining(['slm', 'rubrics', 'program', 'policies', 'citations', 'synthesize']),
    );
    expect(activeNodes.has('roadmap')).toBe(false);
    expect(activeNodes.has('coordinator')).toBe(false);
    expect(activeNodes.has('syllabus')).toBe(false);
    expect(activeNodes.has('align')).toBe(false);
  });

  it('keeps standalone syllabus alignment isolated from rubric scoring', () => {
    const { activeNodes } = getActiveMapIds('syllabus-output');

    expect([...activeNodes]).toEqual(
      expect.arrayContaining(['slm', 'syllabus', 'align', 'syllabus-output']),
    );
    expect(activeNodes.has('rubrics')).toBe(false);
    expect(activeNodes.has('synthesize')).toBe(false);
  });
});
