import { describe, expect, it } from 'vitest';
import {
  deriveSyllabusMetrics,
  filterSyllabusItems,
} from '../syllabusFiltering';
import type { AlignmentSlmItem, AlignmentSlmStats } from '../../types';

describe('syllabusFiltering utils', () => {
  const sampleItems: AlignmentSlmItem[] = [
    {
      document_id: 'doc-1',
      title: 'Module 1: Introduction to CS',
      program: 'BSCS',
      course_code: 'CS101',
      course_title: 'Intro to CS',
      lesson_title: 'Lesson 1',
      processing_status: 'COMPLETED',
      uploaded_at: '2026-03-01T00:00:00Z',
      evaluation_available: true,
      current_result: {
        alignment_id: 'run-1',
        slm_document_id: 'doc-1',
        syllabus_document_id: 'syl-1',
        syllabus_title: 'CS101 Syllabus',
        requested_by: 'faculty',
        status: 'COMPLETED',
        alignment_level: 'MEETS',
        advisory_only: true,
        created_at: '2026-03-01T00:00:00Z',
        updated_at: '2026-03-01T00:00:00Z',
      },
    },
    {
      document_id: 'doc-2',
      title: 'Module 2: Data Structures',
      program: 'BSCS',
      course_code: 'CS102',
      course_title: 'Data Structures',
      lesson_title: 'Lesson 2',
      processing_status: 'COMPLETED',
      uploaded_at: '2026-03-01T00:00:00Z',
      evaluation_available: true,
      current_result: {
        alignment_id: 'run-2',
        slm_document_id: 'doc-2',
        syllabus_document_id: 'syl-2',
        syllabus_title: 'CS102 Syllabus',
        requested_by: 'faculty',
        status: 'COMPLETED',
        alignment_level: 'PARTIALLY_MEETS',
        advisory_only: true,
        created_at: '2026-03-01T00:00:00Z',
        updated_at: '2026-03-01T00:00:00Z',
      },
    },
    {
      document_id: 'doc-3',
      title: 'Module 3: Algorithms',
      program: 'BSIT',
      course_code: 'IT201',
      course_title: 'Algorithms',
      lesson_title: 'Lesson 3',
      processing_status: 'COMPLETED',
      uploaded_at: '2026-03-01T00:00:00Z',
      evaluation_available: true,
      current_result: {
        alignment_id: 'run-3',
        slm_document_id: 'doc-3',
        syllabus_document_id: 'syl-3',
        syllabus_title: 'IT201 Syllabus',
        requested_by: 'faculty',
        status: 'COMPLETED',
        alignment_level: 'DOES_NOT_MEET',
        advisory_only: true,
        created_at: '2026-03-01T00:00:00Z',
        updated_at: '2026-03-01T00:00:00Z',
      },
    },
    {
      document_id: 'doc-4',
      title: 'Module 4: Machine Learning',
      program: 'BSCS',
      course_code: 'CS401',
      course_title: 'ML Basics',
      lesson_title: 'Lesson 4',
      processing_status: 'PROCESSING',
      uploaded_at: '2026-03-01T00:00:00Z',
      evaluation_available: true,
      current_result: {
        alignment_id: 'run-4',
        slm_document_id: 'doc-4',
        syllabus_document_id: 'syl-4',
        syllabus_title: 'CS401 Syllabus',
        requested_by: 'faculty',
        status: 'RUNNING',
        alignment_level: null,
        advisory_only: true,
        created_at: '2026-03-01T00:00:00Z',
        updated_at: '2026-03-01T00:00:00Z',
      },
    },
  ];

  describe('deriveSyllabusMetrics', () => {
    it('uses server stats directly when provided', () => {
      const stats: AlignmentSlmStats = {
        total: 50,
        meets: 25,
        partially_meets: 15,
        needs_attention: 5,
        pending: 5,
      };

      const metrics = deriveSyllabusMetrics(stats, sampleItems);
      expect(metrics).toEqual({
        meets: 25,
        partiallyMeets: 15,
        attention: 5,
        pending: 5,
      });
    });

    it('falls back to calculating metrics from items when stats are not provided', () => {
      const metrics = deriveSyllabusMetrics(undefined, sampleItems);
      expect(metrics).toEqual({
        meets: 1,
        partiallyMeets: 1,
        attention: 1,
        pending: 1,
      });
    });
  });

  describe('filterSyllabusItems', () => {
    it('returns all items when filter is ALL and search is empty', () => {
      const result = filterSyllabusItems(sampleItems, 'ALL', '');
      expect(result).toHaveLength(4);
    });

    it('filters by status MEETS', () => {
      const result = filterSyllabusItems(sampleItems, 'MEETS', '');
      expect(result).toHaveLength(1);
      expect(result[0].document_id).toBe('doc-1');
    });

    it('filters by status PARTIALLY_MEETS', () => {
      const result = filterSyllabusItems(sampleItems, 'PARTIALLY_MEETS', '');
      expect(result).toHaveLength(1);
      expect(result[0].document_id).toBe('doc-2');
    });

    it('filters by status ATTENTION', () => {
      const result = filterSyllabusItems(sampleItems, 'ATTENTION', '');
      expect(result).toHaveLength(1);
      expect(result[0].document_id).toBe('doc-3');
    });

    it('filters by status PENDING', () => {
      const result = filterSyllabusItems(sampleItems, 'PENDING', '');
      expect(result).toHaveLength(1);
      expect(result[0].document_id).toBe('doc-4');
    });

    it('filters by search term matching title or course', () => {
      const result = filterSyllabusItems(sampleItems, 'ALL', 'Algorithms');
      expect(result).toHaveLength(1);
      expect(result[0].document_id).toBe('doc-3');
    });

    it('filters by search term matching syllabus title', () => {
      const result = filterSyllabusItems(sampleItems, 'ALL', 'CS102 Syllabus');
      expect(result).toHaveLength(1);
      expect(result[0].document_id).toBe('doc-2');
    });
  });
});
