// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MonitoringTable } from '../MonitoringTable';
import { formatRevisionContext } from '../../utils';
import * as useMonitoringMatrixModule from '../../hooks/useMonitoringMatrix';
import type { MatrixListResponse } from '../../types';

describe('formatRevisionContext helper', () => {
  it('returns em dash when domainScores is null or empty', () => {
    expect(formatRevisionContext(null)).toBe('—');
    expect(formatRevisionContext(undefined)).toBe('—');
    expect(formatRevisionContext({})).toBe('—');
  });

  it('formats single revision version', () => {
    const domainScores = {
      sme: {
        version: 1,
        form_snapshot_id: 'snap-1',
        subtotal: 4,
        max_score: 4,
        status: 'OK',
      },
    };
    expect(formatRevisionContext(domainScores)).toBe('Rev 1');
  });

  it('formats multiple distinct revisions in sorted order', () => {
    const domainScores = {
      sme: {
        version: 2,
        form_snapshot_id: 'snap-2',
        subtotal: 4,
        max_score: 4,
        status: 'OK',
      },
      coordinator: {
        version: 1,
        form_snapshot_id: 'snap-1',
        subtotal: 3,
        max_score: 4,
        status: 'OK',
      },
      itso: {
        version: 2,
        form_snapshot_id: 'snap-3',
        subtotal: 3,
        max_score: 4,
        status: 'OK',
      },
    };
    expect(formatRevisionContext(domainScores)).toBe('Rev 1, 2');
  });

  it('formats exact legacy notice when blocks exist without form_snapshot_id or version', () => {
    const domainScores = {
      sme: {
        version: undefined,
        form_snapshot_id: undefined,
        subtotal: 3,
        max_score: 4,
        status: 'OK',
      },
    };
    expect(formatRevisionContext(domainScores)).toBe('Legacy — form snapshot unavailable');
  });

  it('does not assume fixed agent keys or criterion counts', () => {
    const arbitraryDynamicDomains = {
      novel_domain_alpha: {
        version: 5,
        form_snapshot_id: 'snap-5',
        subtotal: 4,
        max_score: 4,
        status: 'OK',
      },
    };
    expect(formatRevisionContext(arbitraryDynamicDomains)).toBe('Rev 5');
  });
});

describe('MonitoringTable Component', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  function renderTable() {
    return render(
      <QueryClientProvider client={queryClient}>
        <MonitoringTable />
      </QueryClientProvider>,
    );
  }

  it('renders Form Revision column and displays revision context supplied by API', () => {
    const mockData: MatrixListResponse = {
      items: [
        {
          matrix_id: 'mat-1',
          document_id: 'doc-1',
          evaluation_id: 'eval-1',
          faculty_name: 'Dr. Santos',
          program: 'BSCS',
          document_title: 'Algorithms Module',
          evaluation_status: 'COMPLETED',
          synthesized_score: 92,
          adjectival_rating: 'Very Satisfactory',
          domain_scores: {
            sme: {
              version: 2,
              form_snapshot_id: 'snap-1',
              subtotal: 4,
              max_score: 4,
              status: 'OK',
            },
          },
          flag_count: 0,
          feedback_status: 'NO_FEEDBACK',
          last_updated: '2026-08-20T10:00:00Z',
        },
        {
          matrix_id: 'mat-2',
          document_id: 'doc-2',
          evaluation_id: 'eval-2',
          faculty_name: 'Prof. Reyes',
          program: 'BSInfoTech',
          document_title: 'Web Dev Module',
          evaluation_status: 'COMPLETED',
          synthesized_score: 85,
          adjectival_rating: 'Satisfactory',
          domain_scores: {
            sme: {
              subtotal: 3,
              max_score: 4,
              status: 'OK',
            },
          },
          flag_count: 1,
          feedback_status: 'NO_FEEDBACK',
          last_updated: '2026-08-21T10:00:00Z',
        },
      ],
      total: 2,
      page: 1,
      page_size: 20,
    };

    vi.spyOn(useMonitoringMatrixModule, 'useMonitoringMatrix').mockReturnValue({
      data: mockData,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useMonitoringMatrixModule.useMonitoringMatrix>);

    renderTable();

    // Check header
    expect(screen.getByText('Form Revision')).toBeDefined();

    // Check row 1 has revision
    expect(screen.getByText('Rev 2')).toBeDefined();

    // Check row 2 has exact legacy notice
    expect(screen.getByText('Legacy — form snapshot unavailable')).toBeDefined();
  });

  it('matrix feature never imports from evaluation feature (strict feature boundary)', () => {
    const matrixDir = path.resolve(__dirname, '../..');
    expect(path.basename(matrixDir)).toBe('matrix');

    const files: string[] = [];
    function scanDir(dir: string) {
      for (const entry of fs.readdirSync(dir)) {
        const full = path.join(dir, entry);
        if (fs.statSync(full).isDirectory()) {
          if (entry !== '__tests__') scanDir(full);
        } else if (/\.(ts|tsx)$/.test(entry)) {
          files.push(full);
        }
      }
    }
    scanDir(matrixDir);

    expect(files.length).toBeGreaterThan(0);
    const evalImportPattern = /from\s+['"].*features\/evaluation.*['"]/;
    for (const file of files) {
      const content = fs.readFileSync(file, 'utf-8');
      expect(
        evalImportPattern.test(content),
        `Found cross-feature import from evaluation in ${file}`,
      ).toBe(false);
    }
  });
});
