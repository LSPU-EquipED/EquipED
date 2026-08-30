import { describe, expect, it, vi } from 'vitest';
import * as httpModule from '@/shared/api/http';
import { rubricEditorApi } from '../rubricEditor.api';
import type { StrategyConfig } from '../../types';

describe('rubricEditorApi', () => {
  it('fetches rubric sets with and without query params', async () => {
    let capturedUrl = '';
    const spy = vi.spyOn(httpModule, 'requestJson').mockImplementation(async (url: string) => {
      capturedUrl = url;
      return { rubric_sets: [] };
    });

    await rubricEditorApi.getRubricSets();
    expect(capturedUrl).toBe('/admin/rubrics');

    await rubricEditorApi.getRubricSets({ all_revisions: true, agent_id: 'sme' });
    expect(capturedUrl).toBe('/admin/rubrics?all_revisions=true&agent_id=sme');

    spy.mockRestore();
  });

  it('fetches revisions with optional agent filter', async () => {
    let capturedUrl = '';
    const spy = vi.spyOn(httpModule, 'requestJson').mockImplementation(async (url: string) => {
      capturedUrl = url;
      return { revisions: [], active_pointers: {} };
    });

    await rubricEditorApi.getRevisions();
    expect(capturedUrl).toBe('/admin/rubrics/revisions');

    await rubricEditorApi.getRevisions('gad');
    expect(capturedUrl).toBe('/admin/rubrics/revisions?agent_id=gad');

    spy.mockRestore();
  });

  it('fetches a single rubric set revision by ID', async () => {
    let capturedUrl = '';
    const spy = vi.spyOn(httpModule, 'requestJson').mockImplementation(async (url: string) => {
      capturedUrl = url;
      return {};
    });

    await rubricEditorApi.getRubricSetById('set-123');
    expect(capturedUrl).toBe('/admin/rubrics/set-123');

    spy.mockRestore();
  });

  it('creates and deletes draft revision', async () => {
    let capturedUrl = '';
    let capturedInit: RequestInit | undefined;
    const spy = vi
      .spyOn(httpModule, 'requestJson')
      .mockImplementation(async (url: string, init?: RequestInit) => {
        capturedUrl = url;
        capturedInit = init;
        return {};
      });

    await rubricEditorApi.createDraft('coordinator');
    expect(capturedUrl).toBe('/admin/rubrics/agents/coordinator/draft');
    expect(capturedInit?.method).toBe('POST');

    await rubricEditorApi.deleteDraft('draft-123');
    expect(capturedUrl).toBe('/admin/rubrics/draft-123/draft');
    expect(capturedInit?.method).toBe('DELETE');

    spy.mockRestore();
  });

  it('validates draft revision', async () => {
    let capturedUrl = '';
    let capturedInit: RequestInit | undefined;
    const spy = vi
      .spyOn(httpModule, 'requestJson')
      .mockImplementation(async (url: string, init?: RequestInit) => {
        capturedUrl = url;
        capturedInit = init;
        return { is_valid: true, issues: [], estimated_prompt_chars: 500, criteria_count: 5 };
      });

    const report = await rubricEditorApi.validateDraft('draft-123');
    expect(capturedUrl).toBe('/admin/rubrics/draft-123/validate');
    expect(capturedInit?.method).toBe('POST');
    expect(report.is_valid).toBe(true);

    spy.mockRestore();
  });

  it('publishes revision with explicit activation option', async () => {
    let capturedUrl = '';
    let capturedInit: RequestInit | undefined;
    const spy = vi
      .spyOn(httpModule, 'requestJson')
      .mockImplementation(async (url: string, init?: RequestInit) => {
        capturedUrl = url;
        capturedInit = init;
        return {};
      });

    await rubricEditorApi.publishRevision('draft-123', true);
    expect(capturedUrl).toBe('/admin/rubrics/draft-123/publish');
    expect(capturedInit?.method).toBe('POST');
    expect(JSON.parse(capturedInit?.body as string)).toEqual({ activate: true });

    await rubricEditorApi.publishRevision('draft-123', false);
    expect(JSON.parse(capturedInit?.body as string)).toEqual({ activate: false });

    spy.mockRestore();
  });

  it('activates and retires revisions', async () => {
    let capturedUrl = '';
    let capturedInit: RequestInit | undefined;
    const spy = vi
      .spyOn(httpModule, 'requestJson')
      .mockImplementation(async (url: string, init?: RequestInit) => {
        capturedUrl = url;
        capturedInit = init;
        return {};
      });

    await rubricEditorApi.activateRevision('rev-old');
    expect(capturedUrl).toBe('/admin/rubrics/rev-old/activate');
    expect(capturedInit?.method).toBe('POST');

    await rubricEditorApi.retireRevision('rev-inactive');
    expect(capturedUrl).toBe('/admin/rubrics/rev-inactive/retire');
    expect(capturedInit?.method).toBe('POST');

    spy.mockRestore();
  });

  it('submits atomic tree reorder request', async () => {
    let capturedUrl = '';
    let capturedInit: RequestInit | undefined;
    const spy = vi
      .spyOn(httpModule, 'requestJson')
      .mockImplementation(async (url: string, init?: RequestInit) => {
        capturedUrl = url;
        capturedInit = init;
        return {};
      });

    const reorderPayload = {
      domains: [
        { rubric_domain_id: 'dom-1', criterion_ids: ['crit-1', 'crit-2'] },
        { rubric_domain_id: 'dom-2', criterion_ids: ['crit-3'] },
      ],
    };

    await rubricEditorApi.reorderRubricTree('draft-123', reorderPayload);
    expect(capturedUrl).toBe('/admin/rubrics/draft-123/reorder');
    expect(capturedInit?.method).toBe('POST');
    expect(JSON.parse(capturedInit?.body as string)).toEqual(reorderPayload);

    spy.mockRestore();
  });

  it('creates, updates, and deletes domains', async () => {
    let capturedUrl = '';
    let capturedInit: RequestInit | undefined;
    const spy = vi
      .spyOn(httpModule, 'requestJson')
      .mockImplementation(async (url: string, init?: RequestInit) => {
        capturedUrl = url;
        capturedInit = init;
        return {};
      });

    await rubricEditorApi.createDomain('draft-123', { code: 'OP', title: 'Organization' });
    expect(capturedUrl).toBe('/admin/rubrics/draft-123/domains');
    expect(capturedInit?.method).toBe('POST');
    expect(JSON.parse(capturedInit?.body as string)).toEqual({
      code: 'OP',
      title: 'Organization',
    });

    await rubricEditorApi.updateDomain('dom-1', { title: 'Assessment' });
    expect(capturedUrl).toBe('/admin/rubrics/domains/dom-1');
    expect(capturedInit?.method).toBe('PATCH');
    expect(JSON.parse(capturedInit?.body as string)).toEqual({ title: 'Assessment' });

    await rubricEditorApi.deleteDomain('dom-1');
    expect(capturedUrl).toBe('/admin/rubrics/domains/dom-1');
    expect(capturedInit?.method).toBe('DELETE');

    spy.mockRestore();
  });

  it('creates, updates, moves, and deletes criteria with strategy config', async () => {
    let capturedUrl = '';
    let capturedInit: RequestInit | undefined;
    const spy = vi
      .spyOn(httpModule, 'requestJson')
      .mockImplementation(async (url: string, init?: RequestInit) => {
        capturedUrl = url;
        capturedInit = init;
        return {};
      });

    const strategyConfig: StrategyConfig = {
      strategy: 'count_band',
      mode: 'minimum_count',
      threshold_4: 4,
      threshold_3: 3,
      threshold_2: 2,
    };

    await rubricEditorApi.createCriterion('dom-1', {
      criterion_code: 'OP-01',
      title: 'Topic Coherence',
      description: 'Topics are coherent.',
      scoring_rule: '4 for min 4',
      strategy_config: strategyConfig,
    });
    expect(capturedUrl).toBe('/admin/rubrics/domains/dom-1/criteria');
    expect(capturedInit?.method).toBe('POST');
    expect(JSON.parse(capturedInit?.body as string)).toEqual({
      criterion_code: 'OP-01',
      title: 'Topic Coherence',
      description: 'Topics are coherent.',
      scoring_rule: '4 for min 4',
      strategy_config: strategyConfig,
    });

    await rubricEditorApi.updateCriterion('crit-1', {
      title: 'Updated Title',
      strategy_config: strategyConfig,
    });
    expect(capturedUrl).toBe('/admin/rubrics/criteria/crit-1');
    expect(capturedInit?.method).toBe('PATCH');
    expect(JSON.parse(capturedInit?.body as string)).toEqual({
      title: 'Updated Title',
      strategy_config: strategyConfig,
    });

    await rubricEditorApi.moveCriterion('crit-1', { destination_domain_id: 'dom-2' });
    expect(capturedUrl).toBe('/admin/rubrics/criteria/crit-1/move');
    expect(capturedInit?.method).toBe('POST');
    expect(JSON.parse(capturedInit?.body as string)).toEqual({
      destination_domain_id: 'dom-2',
    });

    await rubricEditorApi.deleteCriterion('crit-1');
    expect(capturedUrl).toBe('/admin/rubrics/criteria/crit-1');
    expect(capturedInit?.method).toBe('DELETE');

    spy.mockRestore();
  });
});
