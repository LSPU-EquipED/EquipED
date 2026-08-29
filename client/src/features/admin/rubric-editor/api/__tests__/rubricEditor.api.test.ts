import { describe, expect, it, vi } from 'vitest';
import * as httpModule from '@/shared/api/http';
import { rubricEditorApi } from '../rubricEditor.api';

describe('rubricEditorApi', () => {
  it('fetches the active rubric sets from /admin/rubrics', async () => {
    const spy = vi.spyOn(httpModule, 'requestJson').mockResolvedValue({ rubric_sets: [] });

    await rubricEditorApi.getRubricSets();

    expect(spy).toHaveBeenCalledWith('/admin/rubrics');
    spy.mockRestore();
  });

  it('PATCHes a criterion with a description + scoring_rule body', async () => {
    let capturedUrl: string | undefined;
    let capturedInit: RequestInit | undefined;
    const spy = vi
      .spyOn(httpModule, 'requestJson')
      .mockImplementation(async (url: string, init?: RequestInit) => {
        capturedUrl = url;
        capturedInit = init;
        return {};
      });

    await rubricEditorApi.updateCriterion('crit-1', {
      description: 'New description.',
      scoring_rule: 'New rule: count differently.',
    });

    expect(capturedUrl).toBe('/admin/rubrics/criteria/crit-1');
    expect(capturedInit?.method).toBe('PATCH');
    expect(JSON.parse(capturedInit?.body as string)).toEqual({
      description: 'New description.',
      scoring_rule: 'New rule: count differently.',
    });
    spy.mockRestore();
  });

  it('PATCHes a domain title', async () => {
    let capturedUrl: string | undefined;
    let capturedInit: RequestInit | undefined;
    const spy = vi
      .spyOn(httpModule, 'requestJson')
      .mockImplementation(async (url: string, init?: RequestInit) => {
        capturedUrl = url;
        capturedInit = init;
        return {};
      });

    await rubricEditorApi.updateDomain('dom-1', { title: 'Assessment' });

    expect(capturedUrl).toBe('/admin/rubrics/domains/dom-1');
    expect(capturedInit?.method).toBe('PATCH');
    expect(JSON.parse(capturedInit?.body as string)).toEqual({ title: 'Assessment' });
    spy.mockRestore();
  });
});
