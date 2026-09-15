import { describe, expect, it } from 'vitest';
import { ApiError } from '@/shared/api/http';
import {
  areAllCriterionScoresComplete,
  criterionKey,
  formatTimestamp,
  groupCriteriaByAgent,
  isPartialValidationAgent,
  isStaleBindingError,
} from '../helpers';
import type { ModelValidationAgentCriteria, ModelValidationCriterionScore } from '../../types';

const dynamicPartialCatalog: ModelValidationAgentCriteria[] = [
  {
    agent_id: 'sme',
    agent_name: 'Subject Matter Expert',
    rubric_set_id: 'set-sme-uuid-1',
    rubric_version: 2,
    domains: [
      {
        rubric_domain_id: 'dom-sme-1',
        code: 'CONTENT',
        title: 'Content Quality',
        display_order: 1,
        criteria: [
          {
            rubric_criterion_id: 'crit-sme-uuid-1',
            criterion_code: 'SME_1',
            criterion_id: 'crit-sme-uuid-1',
            title: 'Content accuracy',
            description: 'Check content accuracy',
            domain_title: 'Content Quality',
            display_order: 1,
          },
          {
            rubric_criterion_id: 'crit-sme-uuid-2',
            criterion_code: 'SME_2',
            criterion_id: 'crit-sme-uuid-2',
            title: 'Pedagogy',
            description: 'Check pedagogy',
            domain_title: 'Content Quality',
            display_order: 2,
          },
        ],
      },
    ],
    criteria: [
      {
        rubric_criterion_id: 'crit-sme-uuid-1',
        criterion_code: 'SME_1',
        criterion_id: 'crit-sme-uuid-1',
        title: 'Content accuracy',
        description: 'Check content accuracy',
        domain_title: 'Content Quality',
        display_order: 1,
      },
      {
        rubric_criterion_id: 'crit-sme-uuid-2',
        criterion_code: 'SME_2',
        criterion_id: 'crit-sme-uuid-2',
        title: 'Pedagogy',
        description: 'Check pedagogy',
        domain_title: 'Content Quality',
        display_order: 2,
      },
    ],
  },
  {
    agent_id: 'gad',
    agent_name: 'GAD',
    rubric_set_id: 'set-gad-uuid-1',
    rubric_version: 1,
    domains: [
      {
        rubric_domain_id: 'dom-gad-1',
        code: 'GENDER',
        title: 'Gender and Development',
        display_order: 1,
        criteria: [
          {
            rubric_criterion_id: 'crit-gad-uuid-1',
            criterion_code: 'GAD_1',
            criterion_id: 'crit-gad-uuid-1',
            title: 'Gender sensitivity',
            description: 'Check gender sensitivity',
            domain_title: 'Gender and Development',
            display_order: 1,
          },
        ],
      },
    ],
    criteria: [
      {
        rubric_criterion_id: 'crit-gad-uuid-1',
        criterion_code: 'GAD_1',
        criterion_id: 'crit-gad-uuid-1',
        title: 'Gender sensitivity',
        description: 'Check gender sensitivity',
        domain_title: 'Gender and Development',
        display_order: 1,
      },
    ],
  },
  {
    agent_id: 'itso',
    agent_name: 'ITSO',
    rubric_set_id: 'set-itso-uuid-1',
    rubric_version: 3,
    domains: [
      {
        rubric_domain_id: 'dom-itso-1',
        code: 'SEC',
        title: 'Security and IP',
        display_order: 1,
        criteria: [
          {
            rubric_criterion_id: 'crit-itso-uuid-1',
            criterion_code: 'ITSO_1',
            criterion_id: 'crit-itso-uuid-1',
            title: 'Data privacy',
            description: 'Check data privacy',
            domain_title: 'Security and IP',
            display_order: 1,
          },
        ],
      },
    ],
    criteria: [
      {
        rubric_criterion_id: 'crit-itso-uuid-1',
        criterion_code: 'ITSO_1',
        criterion_id: 'crit-itso-uuid-1',
        title: 'Data privacy',
        description: 'Check data privacy',
        domain_title: 'Security and IP',
        display_order: 1,
      },
    ],
  },
];

describe('isPartialValidationAgent', () => {
  it('identifies partial validation agents correctly', () => {
    expect(isPartialValidationAgent('sme')).toBe(true);
    expect(isPartialValidationAgent('gad')).toBe(true);
    expect(isPartialValidationAgent('itso')).toBe(true);
    expect(isPartialValidationAgent('coordinator')).toBe(false);
    expect(isPartialValidationAgent('unknown')).toBe(false);
  });
});

describe('criterionKey', () => {
  it('formats key as agentId:rubricCriterionId', () => {
    expect(criterionKey('sme', 'crit-123')).toBe('sme:crit-123');
  });
});

describe('areAllCriterionScoresComplete', () => {
  it('is complete for the dynamic 3-agent active catalog once every criterion has an integer score 1-4', () => {
    expect(
      areAllCriterionScoresComplete(dynamicPartialCatalog, {
        'sme:crit-sme-uuid-1': '4',
        'sme:crit-sme-uuid-2': '3',
        'gad:crit-gad-uuid-1': '2',
        'itso:crit-itso-uuid-1': '4',
      }),
    ).toBe(true);
  });

  it('is incomplete when any active criterion is missing a score', () => {
    expect(
      areAllCriterionScoresComplete(dynamicPartialCatalog, {
        'sme:crit-sme-uuid-1': '4',
        'sme:crit-sme-uuid-2': '3',
        'gad:crit-gad-uuid-1': '2',
      }),
    ).toBe(false);
  });

  it('is incomplete when a score is out of the 1-4 scale', () => {
    expect(
      areAllCriterionScoresComplete(dynamicPartialCatalog, {
        'sme:crit-sme-uuid-1': '4',
        'sme:crit-sme-uuid-2': '3',
        'gad:crit-gad-uuid-1': '2',
        'itso:crit-itso-uuid-1': '5',
      }),
    ).toBe(false);
  });

  it('is incomplete when rubric_set_id is missing on an agent', () => {
    const invalidCatalog = [
      {
        ...dynamicPartialCatalog[0],
        rubric_set_id: '',
      },
      dynamicPartialCatalog[1],
      dynamicPartialCatalog[2],
    ] as ModelValidationAgentCriteria[];

    expect(
      areAllCriterionScoresComplete(invalidCatalog, {
        'sme:crit-sme-uuid-1': '4',
        'sme:crit-sme-uuid-2': '3',
        'gad:crit-gad-uuid-1': '2',
        'itso:crit-itso-uuid-1': '4',
      }),
    ).toBe(false);
  });

  it('is incomplete when the catalog is empty', () => {
    expect(areAllCriterionScoresComplete([], {})).toBe(false);
  });

  it('is incomplete when an agent group has no criteria', () => {
    const catalogWithEmptyGroup: ModelValidationAgentCriteria[] = [
      ...dynamicPartialCatalog,
      {
        agent_id: 'itso',
        agent_name: 'ITSO',
        rubric_set_id: 'set-empty',
        rubric_version: 1,
        domains: [],
        criteria: [],
      },
    ];
    expect(areAllCriterionScoresComplete(catalogWithEmptyGroup, {})).toBe(false);
  });
});

describe('isStaleBindingError', () => {
  it('returns true for 409 conflict and 422 unprocessable entity ApiErrors', () => {
    const err409 = new ApiError('Conflict', { status: 409, payload: { detail: 'Stale rubric' } });
    const err422 = new ApiError('Unprocessable', {
      status: 422,
      payload: { detail: 'Cross-revision' },
    });
    expect(isStaleBindingError(err409)).toBe(true);
    expect(isStaleBindingError(err422)).toBe(true);
  });

  it('returns false for other status codes or non-ApiErrors', () => {
    const err500 = new ApiError('Server error', { status: 500, payload: null });
    const err404 = new ApiError('Not found', { status: 404, payload: null });
    expect(isStaleBindingError(err500)).toBe(false);
    expect(isStaleBindingError(err404)).toBe(false);
    expect(isStaleBindingError(new Error('Random error'))).toBe(false);
    expect(isStaleBindingError(null)).toBe(false);
  });
});

describe('groupCriteriaByAgent', () => {
  it('groups criteria by agent id in standard agent order and preserves rubric version/set', () => {
    const scores: ModelValidationCriterionScore[] = [
      {
        expected_score_id: '1',
        agent_id: 'itso',
        rubric_set_id: 'set-itso-1',
        rubric_version: 3,
        rubric_criterion_id: 'crit-itso-1',
        criterion_id: 'ITSO_1',
        criterion_title: 'ITSO Criterion 1',
        expected_score: 4,
        actual_score: 4,
        absolute_error: 0,
      },
      {
        expected_score_id: '2',
        agent_id: 'sme',
        rubric_set_id: 'set-sme-1',
        rubric_version: 2,
        rubric_criterion_id: 'crit-sme-1',
        criterion_id: 'SME_1',
        criterion_title: 'SME Criterion 1',
        expected_score: 3,
        actual_score: 3,
        absolute_error: 0,
      },
    ];

    const grouped = groupCriteriaByAgent(scores);
    expect(grouped).toHaveLength(2);
    expect(grouped[0]?.agentId).toBe('sme');
    expect(grouped[0]?.rubricSetId).toBe('set-sme-1');
    expect(grouped[0]?.rubricVersion).toBe(2);
    expect(grouped[1]?.agentId).toBe('itso');
    expect(grouped[1]?.rubricSetId).toBe('set-itso-1');
    expect(grouped[1]?.rubricVersion).toBe(3);
  });

  it('returns empty array when input scores are empty', () => {
    expect(groupCriteriaByAgent([])).toEqual([]);
  });
});

describe('formatTimestamp', () => {
  it('returns dash for null or invalid date', () => {
    expect(formatTimestamp(null)).toBe('—');
    expect(formatTimestamp(undefined)).toBe('—');
    expect(formatTimestamp('invalid-date')).toBe('—');
  });

  it('formats valid ISO date string', () => {
    const formatted = formatTimestamp('2026-07-30T10:00:00Z');
    expect(formatted).not.toBe('—');
    expect(typeof formatted).toBe('string');
  });
});
