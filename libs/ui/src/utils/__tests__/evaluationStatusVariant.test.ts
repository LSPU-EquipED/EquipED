import { describe, expect, it } from 'vitest';
import { getEvaluationStatusVariant } from '../evaluationStatusVariant';

describe('getEvaluationStatusVariant', () => {
  it('maps failure and error states to destructive variant', () => {
    expect(getEvaluationStatusVariant('FAILED')).toBe('destructive');
    expect(getEvaluationStatusVariant('failed')).toBe('destructive');
    expect(getEvaluationStatusVariant('ERROR')).toBe('destructive');
    expect(getEvaluationStatusVariant('error')).toBe('destructive');
  });

  it('maps COMPLETED_PARTIAL to warning variant before general COMPLETED', () => {
    expect(getEvaluationStatusVariant('COMPLETED_PARTIAL')).toBe('warning');
    expect(getEvaluationStatusVariant('completed_partial')).toBe('warning');
  });

  it('maps full completed states to success variant', () => {
    expect(getEvaluationStatusVariant('COMPLETED')).toBe('success');
    expect(getEvaluationStatusVariant('completed')).toBe('success');
    expect(getEvaluationStatusVariant('COMPLETED_WITH_WARNINGS')).toBe('success');
  });

  it('maps in-progress / running pipeline statuses to info variant', () => {
    expect(getEvaluationStatusVariant('IN_PROGRESS')).toBe('info');
    expect(getEvaluationStatusVariant('in_progress')).toBe('info');
    expect(getEvaluationStatusVariant('IN PROGRESS')).toBe('info');
    expect(getEvaluationStatusVariant('in progress')).toBe('info');
    expect(getEvaluationStatusVariant('EVALUATING')).toBe('info');
    expect(getEvaluationStatusVariant('PREPROCESSING')).toBe('info');
    expect(getEvaluationStatusVariant('SYNTHESIZING')).toBe('info');
    expect(getEvaluationStatusVariant('PROCESSING')).toBe('info');
  });

  it('maps queued, pending, submitted, and revision statuses to warning variant', () => {
    expect(getEvaluationStatusVariant('SUBMITTED')).toBe('warning');
    expect(getEvaluationStatusVariant('submitted')).toBe('warning');
    expect(getEvaluationStatusVariant('PENDING')).toBe('warning');
    expect(getEvaluationStatusVariant('pending')).toBe('warning');
    expect(getEvaluationStatusVariant('QUEUED')).toBe('warning');
    expect(getEvaluationStatusVariant('queued')).toBe('warning');
    expect(getEvaluationStatusVariant('REVISION')).toBe('warning');
    expect(getEvaluationStatusVariant('REVISION_REQUIRED')).toBe('warning');
    expect(getEvaluationStatusVariant('NEEDS_REVISION')).toBe('warning');
  });

  it('maps unknown, empty, or missing statuses to neutral variant', () => {
    expect(getEvaluationStatusVariant('UNKNOWN')).toBe('neutral');
    expect(getEvaluationStatusVariant('')).toBe('neutral');
    expect(getEvaluationStatusVariant('   ')).toBe('neutral');
    expect(getEvaluationStatusVariant(null)).toBe('neutral');
    expect(getEvaluationStatusVariant(undefined)).toBe('neutral');
    expect(getEvaluationStatusVariant('OTHER_UNHANDLED_STATE')).toBe('neutral');
  });
});
