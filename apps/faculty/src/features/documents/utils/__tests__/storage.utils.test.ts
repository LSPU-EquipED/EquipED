import { describe, expect, it } from 'vitest';
import {
  mapStatusToApi,
  calculateStorageMetrics,
  sortDocuments,
  formatFileSize,
  type StorageStatusFilter,
  type DocumentSortOption,
} from '../storage.utils';
import type { ClientDocument } from '@equiped/types';

describe('storage.utils', () => {
  describe('mapStatusToApi', () => {
    it('maps PROCESSED to ready', () => {
      expect(mapStatusToApi('PROCESSED')).toBe('ready');
    });

    it('maps PROCESSING to processing', () => {
      expect(mapStatusToApi('PROCESSING')).toBe('processing');
    });

    it('maps FAILED to failed', () => {
      expect(mapStatusToApi('FAILED')).toBe('failed');
    });

    it('maps all and invalid values to undefined', () => {
      expect(mapStatusToApi('all')).toBeUndefined();
      expect(mapStatusToApi('unknown' as StorageStatusFilter)).toBeUndefined();
    });
  });

  describe('calculateStorageMetrics', () => {
    it('calculates metrics from document array and total count', () => {
      const docs: ClientDocument[] = [
        {
          documentId: '1',
          title: 'Doc 1',
          courseCode: 'CS101',
          courseTitle: 'CS1',
          lessonTitle: 'L1',
          sourceType: 'slm',
          program: 'BSCS',
          academicYear: '2025',
          pageCount: 10,
          processingStatus: 'PROCESSED',
          hasOcrPages: true,
          uploadedAt: '2026-01-01',
          chunks: [],
        },
        {
          documentId: '2',
          title: 'Doc 2',
          courseCode: 'IT101',
          courseTitle: 'IT1',
          lessonTitle: 'L2',
          sourceType: 'slm',
          program: 'BSInfoTech',
          academicYear: '2025',
          pageCount: 25,
          processingStatus: 'PROCESSED',
          hasOcrPages: false,
          uploadedAt: '2026-01-02',
          chunks: [],
        },
        {
          documentId: '3',
          title: 'Doc 3',
          courseCode: 'CS102',
          courseTitle: 'CS2',
          lessonTitle: 'L3',
          sourceType: 'slm',
          program: 'BSCS',
          academicYear: '2025',
          pageCount: null,
          processingStatus: 'FAILED',
          hasOcrPages: true,
          uploadedAt: '2026-01-03',
          chunks: [],
        },
      ];

      const metrics = calculateStorageMetrics(docs, 15);

      expect(metrics).toEqual({
        totalModules: 15,
        totalIndexedPages: 35,
        bscsCount: 2,
        bsInfoTechCount: 1,
        ocrVerifiedCount: 2,
      });
    });

    it('handles empty document list', () => {
      const metrics = calculateStorageMetrics([], 0);

      expect(metrics).toEqual({
        totalModules: 0,
        totalIndexedPages: 0,
        bscsCount: 0,
        bsInfoTechCount: 0,
        ocrVerifiedCount: 0,
      });
    });
  });

  describe('formatFileSize', () => {
    it('formats file sizes accurately', () => {
      expect(formatFileSize(500)).toBe('500 B');
      expect(formatFileSize(2048)).toBe('2.0 KB');
      expect(formatFileSize(15.5 * 1024 * 1024)).toBe('15.50 MB');
    });
  });

  describe('sortDocuments', () => {
    const testDocs = [
      {
        documentId: 'doc-1',
        title: 'B - Advanced Algorithms',
        courseCode: 'CS201',
        courseTitle: 'Algorithms',
        pageCount: 30,
        uploadedAt: '2026-02-01T00:00:00Z',
      },
      {
        documentId: 'doc-2',
        title: 'A - Introduction to Programming',
        courseCode: 'CS101',
        courseTitle: 'Intro',
        pageCount: 50,
        uploadedAt: '2026-01-01T00:00:00Z',
      },
      {
        documentId: 'doc-3',
        title: 'C - Web Development',
        courseCode: 'IT105',
        courseTitle: 'Web Systems',
        pageCount: 15,
        uploadedAt: '2026-03-01T00:00:00Z',
      },
    ] as const;

    it('preserves immutability of the input array', () => {
      const original = Object.freeze([...testDocs]);
      const result = sortDocuments(original, 'title-asc');
      expect(result).not.toBe(original);
      expect(original[0].documentId).toBe('doc-1');
      expect(result[0].documentId).toBe('doc-2');
    });

    it('sorts uploaded-desc (newest first)', () => {
      const sorted = sortDocuments(testDocs, 'uploaded-desc');
      expect(sorted.map((d) => d.documentId)).toEqual(['doc-3', 'doc-1', 'doc-2']);
    });

    it('sorts uploaded-asc (oldest first)', () => {
      const sorted = sortDocuments(testDocs, 'uploaded-asc');
      expect(sorted.map((d) => d.documentId)).toEqual(['doc-2', 'doc-1', 'doc-3']);
    });

    it('sorts title-asc (A to Z)', () => {
      const sorted = sortDocuments(testDocs, 'title-asc');
      expect(sorted.map((d) => d.documentId)).toEqual(['doc-2', 'doc-1', 'doc-3']);
    });

    it('sorts title-desc (Z to A)', () => {
      const sorted = sortDocuments(testDocs, 'title-desc');
      expect(sorted.map((d) => d.documentId)).toEqual(['doc-3', 'doc-1', 'doc-2']);
    });

    it('sorts course-asc', () => {
      const sorted = sortDocuments(testDocs, 'course-asc');
      expect(sorted.map((d) => d.documentId)).toEqual(['doc-2', 'doc-1', 'doc-3']);
    });

    it('sorts pages-desc (most pages first)', () => {
      const sorted = sortDocuments(testDocs, 'pages-desc');
      expect(sorted.map((d) => d.documentId)).toEqual(['doc-2', 'doc-1', 'doc-3']);
    });

    it('falls back gracefully on unknown sort option or missing fields', () => {
      const fallback = sortDocuments(testDocs, 'unknown' as DocumentSortOption);
      expect(fallback.map((d) => d.documentId)).toEqual(['doc-1', 'doc-2', 'doc-3']);

      const docsWithNulls = [
        { documentId: '1', uploadedAt: '2026-01-01', title: null, courseCode: null, courseTitle: 'Alpha', pageCount: null },
        { documentId: '2', uploadedAt: '2026-01-02', title: 'Beta', courseCode: 'CS1', courseTitle: null, pageCount: 10 },
      ];
      const byCourse = sortDocuments(docsWithNulls, 'course-asc');
      expect(byCourse.map((d) => d.documentId)).toEqual(['1', '2']);
      const byPages = sortDocuments(docsWithNulls, 'pages-desc');
      expect(byPages.map((d) => d.documentId)).toEqual(['2', '1']);
    });
  });
});
