// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { TARGET_AGENT_META } from '@equiped/types';
import type { DomainScoreBlock, ExportDomainData } from '../../types';
import { EvaluationResultsView } from '../EvaluationResultsView';


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
  render(<EvaluationResultsView evaluation={{ evaluation_id: "evaluation", document_id: "document", submitted_at: "2026-10-05" }}
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
    render(<EvaluationResultsView context="history"
      evaluation={{ evaluation_id: 'evaluation', document_id: 'document', submitted_at: '2026-10-05' }}
      results={{ evaluation_id: 'evaluation', document_id: 'document', synthesized_score: 97.5, domain_scores: { coordinator: domain }, flags: [], active_agents: ['coordinator'], failed_agents: [], is_partial: false, evaluation_status: 'COMPLETED' }}
      meta={TARGET_AGENT_META.coordinator} validAgent="coordinator" domainScore={domain}
      activeItem={null} activeDocument={null} onOpenReviewModal={vi.fn()} onOpenReevaluateModal={vi.fn()}
    />);
    expect(screen.getByRole('region', { name: 'Advisory curriculum alignment' })).toBeTruthy();
    expect(screen.getByText('1 / 4')).toBeTruthy();
  });

  it('does not invent a curriculum supplement for historical results', () => {
    renderScoreboard({ ...domain, adapter_version: 2, advisory_outputs: null });
    expect(screen.queryByRole('region', { name: 'Advisory curriculum alignment' })).toBeNull();
    expect(exportSpy.mock.calls[0][0].criteria).toHaveLength(10);
  });
  it('preserves the recorded evaluation ID for export and offers the same criteria filters in history', () => {
    render(<EvaluationResultsView context="history"
      evaluation={{ evaluation_id: 'recorded-run', document_id: 'document', submitted_at: '2026-10-05' }}
      results={{ evaluation_id: 'recorded-run', document_id: 'document', document_title: 'Recorded SLM', synthesized_score: 97.5, domain_scores: { coordinator: domain }, flags: [], active_agents: ['coordinator'], failed_agents: [], is_partial: false, evaluation_status: 'COMPLETED' }}
      meta={TARGET_AGENT_META.coordinator} validAgent="coordinator" domainScore={domain}
      activeItem={null} activeDocument={null} onOpenReviewModal={vi.fn()} onOpenReevaluateModal={vi.fn()}
    />);
    expect(screen.getByText('Back to evaluation history')).toBeDefined();
    expect(exportSpy.mock.calls[0][0].evaluationId).toBe('recorded-run');
    fireEvent.click(screen.getByRole('button', { name: 'Score 3: 1 criteria' }));
    expect(screen.getByText('Objective Gauging')).toBeDefined();
    expect(screen.queryByText('Criterion 1')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Clear score filter' }));
    expect(screen.getByText('Criterion 1')).toBeDefined();
  });

  it('keeps context out of the metadata rail and leaves criterion counts in the filters', () => {
    renderScoreboard({ ...domain, version: 3 });
    expect(screen.queryByText('SLM Module')).toBeNull();
    expect(screen.queryByText('Rubric version')).toBeNull();
    const metadata = within(screen.getByRole('complementary', { name: 'Evaluation metadata' }));
    for (const label of ['Course', 'Program', 'Evaluated', 'Desk']) expect(metadata.queryByText(label)).toBeNull();
    expect(metadata.getByText('Revision 3')).toBeDefined();
    const summary = within(screen.getByRole('region', { name: 'Program Coordinator performance score' }));
    expect(summary.queryByText(/criteria|strong|need attention/i)).toBeNull();
    expect(screen.getByRole('button', { name: 'All (10)' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Strong (10)' })).toBeDefined();
  });

  it('retains evidence warnings and source pages without repeating library links on each row', () => {
    const block = { ...domain, criteria: [{ ...domain.criteria[0], page_number: 2, is_ungrounded: true, evidence: 'Quoted module passage.' }] };
    renderScoreboard(block);
    const criterion = screen.getByText('Criterion 1').closest('details')!;
    fireEvent.click(criterion.querySelector('summary')!);
    expect(criterion.open).toBe(true);
    expect(within(criterion).getByText('Check evidence')).toBeDefined();
    expect(within(criterion).getByText('Evidence requires reviewer confirmation.')).toBeDefined();
    expect(within(criterion).getByText('Page 2')).toBeDefined();
    expect(within(criterion).queryByRole('link')).toBeNull();
    expect(screen.queryByText('SLM Document')).toBeNull();
  });

});
