import { describe, expect, it } from 'vitest';
import {
  truncateId,
  formatProcessingStatus,
  getHumanReadableTitle,
  getEvaluationDescription,
  getEvaluationActionLabel,
  formatInspectorDate,
} from '../moduleInspector.utils';

describe('moduleInspector.utils', () => {
  describe('truncateId', () => {
    it('returns short IDs unchanged if length <= 16', () => {
      expect(truncateId('doc-abc-123')).toBe('doc-abc-123');
      expect(truncateId('1234567890123456')).toBe('1234567890123456');
    });

    it('truncates IDs longer than 16 characters to first 8 and last 5', () => {
      expect(truncateId('1234567890abcdef12345')).toBe('12345678...12345');
      expect(truncateId('doc-long-identifier-here-99999')).toBe('doc-long...99999');
    });
  });

  describe('formatProcessingStatus', () => {
    it('maps known processing statuses correctly', () => {
      expect(formatProcessingStatus('PROCESSED')).toBe('Indexed');
      expect(formatProcessingStatus('PROCESSING')).toBe('Processing');
      expect(formatProcessingStatus('PENDING')).toBe('Pending');
      expect(formatProcessingStatus('FAILED')).toBe('Failed');
      expect(formatProcessingStatus('CLEANUP_PENDING')).toBe('Cleaning up');
    });

    it('returns status directly for unknown values and "Not specified" for nullish', () => {
      expect(formatProcessingStatus('CUSTOM_STATUS')).toBe('CUSTOM_STATUS');
      expect(formatProcessingStatus(null)).toBe('Not specified');
      expect(formatProcessingStatus(undefined)).toBe('Not specified');
      expect(formatProcessingStatus('')).toBe('Not specified');
    });
  });

  describe('getHumanReadableTitle', () => {
    it('combines courseTitle and lessonTitle when both are present', () => {
      expect(
        getHumanReadableTitle({
          title: 'raw-file.pdf',
          courseTitle: 'CS 101',
          lessonTitle: 'Module 1',
        }),
      ).toBe('CS 101 — Module 1');
    });

    it('falls back to lessonTitle if courseTitle is missing', () => {
      expect(
        getHumanReadableTitle({
          title: 'raw-file.pdf',
          courseTitle: null,
          lessonTitle: 'Module 1',
        }),
      ).toBe('Module 1');
    });

    it('falls back to courseTitle if lessonTitle is missing', () => {
      expect(
        getHumanReadableTitle({
          title: 'raw-file.pdf',
          courseTitle: 'CS 101',
          lessonTitle: null,
        }),
      ).toBe('CS 101');
    });

    it('falls back to title if both are missing', () => {
      expect(
        getHumanReadableTitle({
          title: 'raw-file.pdf',
          courseTitle: null,
          lessonTitle: null,
        }),
      ).toBe('raw-file.pdf');
    });
  });

  describe('getEvaluationDescription', () => {
    it('returns appropriate description for each actionType', () => {
      expect(getEvaluationDescription('view_results')).toContain('completed for this learning module');
      expect(getEvaluationDescription('start_evaluation')).toContain('indexed and ready for multi-agent evaluation');
      expect(getEvaluationDescription('view_progress')).toContain('pipeline is actively running');
      expect(getEvaluationDescription('processing')).toContain('ingestion is in progress');
      expect(getEvaluationDescription('upload_failed')).toContain('Ingestion failed for this document');
      expect(getEvaluationDescription('inspect_failure')).toBe('Multi-agent evaluation status for this module.');
      expect(getEvaluationDescription('checking_status')).toBe('Multi-agent evaluation status for this module.');
      expect(getEvaluationDescription('status_unavailable')).toBe('Multi-agent evaluation status for this module.');
    });
  });

  describe('getEvaluationActionLabel', () => {
    it('returns special labels for view_results and start_evaluation, or fallback', () => {
      expect(getEvaluationActionLabel('view_results', 'Fallback')).toBe('Open Evaluation');
      expect(getEvaluationActionLabel('start_evaluation', 'Fallback')).toBe('Launch Evaluation');
      expect(getEvaluationActionLabel('view_progress', 'Check Progress')).toBe('Check Progress');
      expect(getEvaluationActionLabel('inspect_failure', 'Custom Label')).toBe('Custom Label');
      expect(getEvaluationActionLabel('checking_status', 'Checking...')).toBe('Checking...');
      expect(getEvaluationActionLabel('status_unavailable', 'Unavailable')).toBe('Unavailable');
    });
  });

  describe('formatInspectorDate', () => {
    it('returns "Not specified" for null or undefined date strings', () => {
      expect(formatInspectorDate(null)).toBe('Not specified');
      expect(formatInspectorDate(undefined)).toBe('Not specified');
      expect(formatInspectorDate('')).toBe('Not specified');
    });

    it('formats valid ISO date string cleanly', () => {
      const formatted = formatInspectorDate('2026-09-10T14:30:00.000Z');
      expect(formatted).toMatch(/2026/);
      expect(formatted).toMatch(/Sep/);
      expect(formatted).toMatch(/10/);
    });
  });
});
