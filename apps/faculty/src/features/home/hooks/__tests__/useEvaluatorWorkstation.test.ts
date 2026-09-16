// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useEvaluatorWorkstation, ALL_SPECIALISTS } from '../useEvaluatorWorkstation';

describe('useEvaluatorWorkstation', () => {
  it('returns all specialists for admin user', () => {
    const { result } = renderHook(() => useEvaluatorWorkstation(['sme'], 'admin'));
    expect(result.current.allowedSpecialists).toEqual(ALL_SPECIALISTS);
    expect(result.current.hasSingleSpecialist).toBe(false);
    expect(result.current.singleSpecialist).toBe(ALL_SPECIALISTS[0]);
  });

  it('returns all specialists when permissions are undefined or null (unrestricted default)', () => {
    const { result: nullResult } = renderHook(() => useEvaluatorWorkstation(null, 'faculty'));
    expect(nullResult.current.allowedSpecialists).toEqual(ALL_SPECIALISTS);

    const { result: undefResult } = renderHook(() => useEvaluatorWorkstation(undefined, 'faculty'));
    expect(undefResult.current.allowedSpecialists).toEqual(ALL_SPECIALISTS);
  });

  it('identifies single specialist role accurately', () => {
    const { result } = renderHook(() => useEvaluatorWorkstation(['sme'], 'faculty'));
    expect(result.current.allowedSpecialists).toHaveLength(1);
    expect(result.current.allowedSpecialists[0].id).toBe('sme');
    expect(result.current.hasSingleSpecialist).toBe(true);
    expect(result.current.singleSpecialist.id).toBe('sme');
  });

  it('returns empty array when permissions are explicitly empty', () => {
    const { result } = renderHook(() => useEvaluatorWorkstation([], 'faculty'));
    expect(result.current.allowedSpecialists).toHaveLength(0);
    expect(result.current.hasSingleSpecialist).toBe(false);
    expect(result.current.singleSpecialist).toBeUndefined();
  });

  it('filters to multiple granted permissions', () => {
    const { result } = renderHook(() => useEvaluatorWorkstation(['sme', 'gad'], 'faculty'));
    expect(result.current.allowedSpecialists).toHaveLength(2);
    expect(result.current.allowedSpecialists.map((s) => s.id)).toEqual(['sme', 'gad']);
    expect(result.current.hasSingleSpecialist).toBe(false);
  });
});
