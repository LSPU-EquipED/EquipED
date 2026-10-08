// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { TARGET_AGENT_META } from '@equiped/types';
import type { DomainScoreBlock, ExportDomainData } from '../../types';
import { SpecialistResultsScoreboard } from '../SpecialistResultsScoreboard';
import { EvaluationResultsScoreboard } from '../EvaluationResultsScoreboard';

const exportSpy = vi.hoisted(() => vi.fn());
vi.mock('@tanstack/react-router', () => ({
  Link: ({ children }: { children: React.ReactNode }) => <a href="/documents">{children}</a>,
}));
vi.mock('../ExportDocument', () => ({
  SpecialistExportDownloadButton: ({ domainData }: { domainData: ExportDomainData }) => {
    exportSpy(domainData);
    return <button>Export</button>;
  },
}));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const domain: DomainScoreBlock = {
  adapter_version: 3, subtotal: 3.9, max_score: 4, status: 'OK',
  criteria: Array.from({ length: 10 }, (_, i) => ({
    criterion_id: i < 5 ? `OP-0${i + 1}` : `A-0${i - 4}`,
    criterion_text: i === 9 ? 'Objective Gauging' : `Criterion ${i + 1}`,
    score: i === 9 ? 3 : 4, justification: 'Grounded evaluation.',
  })),
  advisory_outputs: {
    contract: 'coordinator_alignment.v1', criterion_id: 'C-01',
    criterion_title: 'Curriculum Alignment', advisory_only: true,
    score: 1, justification: 'No curriculum support.',
    objective_matches: [{ objective_id: 'OBJ-0001', objective_text: 'An objective.', matched: false, excerpt: '', rejected: false }],
  },
};
function renderScoreboard(block: DomainScoreBlock) {
  render(<SpecialistResultsScoreboard
    results={{ evaluation_id: 'evaluation', document_id: 'document', synthesized_score: 97.5,
      domain_scores: { coordinator: block }, flags: [], active_agents: ['coordinator'],
      failed_agents: [], is_partial: false, evaluation_status: 'COMPLETED' }}
    domainScore={block} meta={TARGET_AGENT_META.coordinator} validAgent="coordinator"
    activeItem={null} activeDocument={null} onOpenReviewModal={vi.fn()} onOpenReevaluateModal={vi.fn()}
  />);
}

describe('Coordinator result separation', () => {
  it('shows C-01 separately while passing only the ten official criteria to PDF export', () => {
    renderScoreboard(domain);
    expect(screen.getByRole('region', { name: 'Advisory curriculum alignment' })).toBeTruthy();
    expect(screen.getByText('1 / 4')).toBeTruthy();
    const exported = exportSpy.mock.calls[0][0] as ExportDomainData;
    expect(exported.criteria).toHaveLength(10);
    expect(exported.criteria.some((row) => row.criterion_id === 'C-01')).toBe(false);
    expect(exported.subtotal).toBe(3.9);
  });

  it('also exposes the supplement on the evaluation-history result screen', () => {
    render(<EvaluationResultsScoreboard
      evaluation={{ evaluation_id: 'evaluation', document_id: 'document', status: 'COMPLETED', submitted_at: '2026-10-05' }}
      singleAgentMeta={TARGET_AGENT_META.coordinator} activeDomainData={domain}
      effectiveDomainId="coordinator" sortedCriteria={domain.criteria}
      isLoadingResults={false} isResultsError={false} onRetryResults={vi.fn()}
      onOpenReview={vi.fn()} onOpenReevaluate={vi.fn()}
    />);
    expect(screen.getByRole('region', { name: 'Advisory curriculum alignment' })).toBeTruthy();
    expect(screen.getByText('1 / 4')).toBeTruthy();
  });

  it('does not invent a curriculum supplement for historical results', () => {
    renderScoreboard({ ...domain, adapter_version: 2, advisory_outputs: null });
    expect(screen.queryByRole('region', { name: 'Advisory curriculum alignment' })).toBeNull();
    expect(exportSpy.mock.calls[0][0].criteria).toHaveLength(10);
  });
});
