import { describe, expect, it, vi } from 'vitest';
import * as httpModule from '@/shared/api/http';
import { modelValidationApi } from '../modelValidation.api';
import type { ModelValidationCreateBody } from '../../types';

describe('modelValidationApi', () => {
  it('submits exact {agent_id, rubric_set_id, rubric_criterion_id, expected_score} with no code-only fallback', async () => {
    let capturedBody: string | null = null;

    const spy = vi
      .spyOn(httpModule, 'requestJson')
      .mockImplementation(async (_url: string, options?: RequestInit) => {
        capturedBody = (options?.body as string) ?? null;
        return {
          validation_id: 'val-1',
          evaluation_id: 'eval-1',
          document_id: 'doc-1',
          document_title: 'SLM 1',
          partial_without_curriculum: true,
          bound_forms: [
            {
              agent_id: 'sme',
              rubric_set_id: 'set-sme-1',
              rubric_version: 1,
              adapter_key: 'sme_adapter',
              adapter_version: 1,
            },
          ],
          criterion_scores: [],
          status: 'SUBMITTED',
          error_message: null,
          created_at: '2026-08-30T00:00:00Z',
        };
      });

    const body: ModelValidationCreateBody = {
      document_id: 'doc-uuid-1',
      partial_without_curriculum: true,
      expected_scores: [
        {
          agent_id: 'sme',
          rubric_set_id: 'set-sme-uuid-1',
          rubric_criterion_id: 'crit-sme-uuid-1',
          expected_score: 4,
        },
        {
          agent_id: 'gad',
          rubric_set_id: 'set-gad-uuid-1',
          rubric_criterion_id: 'crit-gad-uuid-1',
          expected_score: 3,
        },
      ],
    };

    await modelValidationApi.createModelValidation(body);

    expect(spy).toHaveBeenCalledWith(
      '/admin/model-validations',
      expect.objectContaining({
        method: 'POST',
      }),
    );

    expect(capturedBody).not.toBeNull();
    const parsed = JSON.parse(capturedBody!);
    expect(parsed.document_id).toBe('doc-uuid-1');
    expect(parsed.partial_without_curriculum).toBe(true);
    expect(parsed.expected_scores).toEqual([
      {
        agent_id: 'sme',
        rubric_set_id: 'set-sme-uuid-1',
        rubric_criterion_id: 'crit-sme-uuid-1',
        expected_score: 4,
      },
      {
        agent_id: 'gad',
        rubric_set_id: 'set-gad-uuid-1',
        rubric_criterion_id: 'crit-gad-uuid-1',
        expected_score: 3,
      },
    ]);

    // Ensure no criterion_id or code property leaked into expected_scores items
    for (const score of parsed.expected_scores) {
      expect(score).not.toHaveProperty('criterion_id');
      expect(score).not.toHaveProperty('criterion_code');
      expect(score).toHaveProperty('agent_id');
      expect(score).toHaveProperty('rubric_set_id');
      expect(score).toHaveProperty('rubric_criterion_id');
      expect(score).toHaveProperty('expected_score');
    }

    spy.mockRestore();
  });

  it('fetches criteria catalog with GET /admin/model-validations/criteria', async () => {
    const spy = vi
      .spyOn(httpModule, 'requestJson')
      .mockResolvedValueOnce({ agents: [], total_criteria: 0 });

    const result = await modelValidationApi.getModelValidationCriteria();

    expect(spy).toHaveBeenCalledWith('/admin/model-validations/criteria');
    expect(result).toEqual({ agents: [], total_criteria: 0 });

    spy.mockRestore();
  });

  it('fetches validation history with GET /admin/model-validations', async () => {
    const spy = vi.spyOn(httpModule, 'requestJson').mockResolvedValueOnce({ items: [], total: 0 });

    const result = await modelValidationApi.getModelValidations();

    expect(spy).toHaveBeenCalledWith('/admin/model-validations');
    expect(result).toEqual({ items: [], total: 0 });

    spy.mockRestore();
  });

  it('fetches metrics with GET /admin/model-validations/metrics', async () => {
    const spy = vi
      .spyOn(httpModule, 'requestJson')
      .mockResolvedValueOnce({ completed_runs: 0, class_labels: [], confusion_matrix: [] });

    await modelValidationApi.getModelValidationMetrics();

    expect(spy).toHaveBeenCalledWith('/admin/model-validations/metrics');

    spy.mockRestore();
  });

  it('fetches detail with GET /admin/model-validations/:id', async () => {
    const spy = vi.spyOn(httpModule, 'requestJson').mockResolvedValueOnce({ validation_id: 'v-1' });

    await modelValidationApi.getModelValidation('v-1');

    expect(spy).toHaveBeenCalledWith('/admin/model-validations/v-1');

    spy.mockRestore();
  });

  it('fetches linked evaluation with GET /admin/model-validations/:id/evaluation', async () => {
    const spy = vi.spyOn(httpModule, 'requestJson').mockResolvedValueOnce({ evaluation_id: 'e-1' });

    await modelValidationApi.getModelValidationEvaluation('v-1');

    expect(spy).toHaveBeenCalledWith('/admin/model-validations/v-1/evaluation');

    spy.mockRestore();
  });
});
