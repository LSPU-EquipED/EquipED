// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { TARGET_AGENT_META } from '@equiped/types';
import type { DomainScoreBlock, ExportDomainData } from '../../../types';
import { EvaluationResultsView } from '../EvaluationResultsView';


const exportSpy = vi.hoisted(() => vi.fn());
vi.mock('@tanstack/react-router', () => ({
  Link: ({ children }: { children: React.ReactNode }) => <a href="/documents">{children}</a>,
}));
vi.mock('../../exports/ExportDocument', () => ({
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
function renderScoreboard(block: DomainScoreBlock, agent: 'coordinator' | 'itso' = 'coordinator') {
  render(<EvaluationResultsView evaluation={{ evaluation_id: "evaluation", document_id: "document", submitted_at: "2026-10-05" }}
    results={{ evaluation_id: 'evaluation', document_id: 'document', synthesized_score: 97.5,
      domain_scores: { coordinator: block }, flags: [], active_agents: ['coordinator'],
      failed_agents: [], is_partial: false, evaluation_status: 'COMPLETED' }}
    domainScore={block} meta={TARGET_AGENT_META[agent]} validAgent={agent}
    activeItem={null} activeDocument={null} onOpenReviewModal={vi.fn()} onOpenReevaluateModal={vi.fn()}
  />);
}

describe('Coordinator result separation', () => {
  it('shows C-01 separately while passing only the ten official criteria to PDF export', () => {
    renderScoreboard(domain);
    expect(screen.getByRole('region', { name: 'Advisory curriculum alignment' })).toBeTruthy();
    expect(within(screen.getByRole('region', { name: 'Advisory curriculum alignment' })).getByText('1 / 4')).toBeTruthy();
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
    expect(within(screen.getByRole('region', { name: 'Advisory curriculum alignment' })).getByText('1 / 4')).toBeTruthy();
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

  it('shows module context inline and moves record identifiers after the criteria', () => {
    renderScoreboard({ ...domain, version: 3 });
    expect(screen.queryByText('SLM Module')).toBeNull();
    expect(screen.queryByText('Rubric version')).toBeNull();
    const metadata = within(screen.getByRole('region', { name: 'Evaluation metadata' }));
    expect(screen.queryByText('Module details')).toBeNull();
    expect(screen.queryByText('Record details')).toBeNull();
    expect(screen.getAllByRole('link', { name: 'Module Library' })).toHaveLength(1);
    const record = screen.getByRole('contentinfo', { name: 'Evaluation record' });
    expect(within(record).getByText('evaluation')).toBeDefined();
    expect(record.compareDocumentPosition(screen.getByText('Criterion 1')) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();
    expect(document.querySelector('details details')).toBeNull();
    for (const label of ['Course', 'Program', 'Evaluated', 'Desk']) expect(metadata.queryByText(label)).toBeNull();
    expect(metadata.getByText('Revision 3')).toBeDefined();
    const summary = within(screen.getByRole('region', { name: 'Program Coordinator performance score' }));
    expect(summary.queryByRole('button', { name: 'All (10)' })).toBeNull();
    expect(screen.getByRole('button', { name: 'All (10)' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Strong (10)' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'All (10)' }).getAttribute('aria-pressed')).toBe('true');
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

  it('places the finding before complete, keyboard-accessible evidence and preserves corrections', () => {
    const evidence = 'A long source passage. '.repeat(300) + 'Final source sentence.';
    renderScoreboard({ ...domain, criteria: [{ ...domain.criteria[0], evidence,
      reviewer_correction: { action: 'EDIT', score: 2, justification: 'Human reviewer rationale.' },
    }] });
    const criterion = screen.getByText('Criterion 1').closest('details')!;
    fireEvent.click(criterion.querySelector('summary')!);
    const source = within(criterion).getByRole('region', { name: 'OP-01 SLM evidence' });
    expect(source.tabIndex).toBe(0);
    expect(source.textContent).toContain(evidence);
    const finding = within(criterion).getByText('Grounded evaluation.');
    expect(finding.compareDocumentPosition(source) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(criterion).getByText('Human reviewer rationale.')).toBeDefined();
    expect(within(criterion).getByText(/Override score: 2 \/ 4/)).toBeDefined();
    expect(exportSpy.mock.calls[0][0].subtotal).toBe(3.9);
  });

  it('announces selected category and score filters and keeps empty score buckets disabled', () => {
    renderScoreboard(domain);
    const strong = screen.getByRole('button', { name: 'Strong (10)' });
    fireEvent.click(strong);
    expect(strong.getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('button', { name: 'All (10)' }).getAttribute('aria-pressed')).toBe('false');
    fireEvent.click(strong);
    expect(strong.getAttribute('aria-pressed')).toBe('false');
    const score = screen.getByRole('button', { name: 'Score 3: 1 criteria' });
    fireEvent.click(score);
    expect(score.getAttribute('aria-pressed')).toBe('true');
    expect(screen.queryByText('Criterion 1')).toBeNull();
    fireEvent.click(score);
    expect(score.getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByText('Criterion 1')).toBeDefined();
    expect((screen.getByRole('button', { name: 'Score 2: 0 criteria' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('keeps the overview readable without opening disclosures', () => {
    renderScoreboard({ ...domain, summary: 'Review the activities for stronger learner engagement.' });
    const summary = screen.getByText('Review the activities for stronger learner engagement.');
    expect(summary.closest('details')).toBeNull();
    const advisory = screen.getByRole('region', { name: 'Advisory curriculum alignment' });
    expect(advisory.closest('details')).toBeNull();
    expect(advisory.compareDocumentPosition(screen.getByText('Objective Gauging')) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();
    const objectiveDetails = within(advisory).getByText('Objective evidence (1)').closest('details')!;
    fireEvent.click(objectiveDetails.querySelector('summary')!);
    expect(within(objectiveDetails).getByText('An objective.')).toBeDefined();
    expect(document.querySelector('details details')).toBeNull();
  });

  it('preserves an expanded criterion when a filter keeps the same row mounted', () => {
    renderScoreboard(domain);
    const criterion = screen.getByText('Criterion 1').closest('details')!;
    fireEvent.click(criterion.querySelector('summary')!);
    fireEvent.click(screen.getByRole('button', { name: 'Strong (10)' }));
    expect(screen.getByText('Criterion 1').closest('details')).toBe(criterion);
    expect(criterion.open).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'All (10)' }));
    expect(criterion.open).toBe(true);
  });

  it('retains historical criterion aliases, source pages, and missing finding fallbacks', () => {
    const historical = { ...domain, criteria: [{ ...domain.criteria[0],
      code: 'LEGACY-1', criterion_text: '', criterion: 'Historical criterion',
      page_number: '7', justification: '', evidence: null,
      reviewer_correction: { action: 'REJECT' as const, score: null, justification: null },
    }] };
    renderScoreboard(historical);
    const criterion = screen.getByText('Historical criterion').closest('details')!;
    fireEvent.click(criterion.querySelector('summary')!);
    const row = within(criterion);
    expect(row.getByText('LEGACY-1')).toBeDefined();
    expect(row.getByText('Page 7')).toBeDefined();
    expect(row.getByText('No specialist finding was returned.')).toBeDefined();
    expect(row.getByText('No quoted evidence was returned.')).toBeDefined();
    expect(row.getByText('Finding rejected by reviewer')).toBeDefined();
    expect(row.queryByText(/Override score/)).toBeNull();
    expect(row.queryByRole('region', { name: 'LEGACY-1 SLM evidence' })).toBeNull();
  });

});

describe('Concise specialist findings and evidence limits', () => {
  const itsoDomain: DomainScoreBlock = {
    subtotal: 3.5, max_score: 4, status: 'OK', summary: 'Review rights and permissions.',
    criteria: [
      { criterion_id: 'ITSO-04', criterion_text: 'Student confidentiality', score: 4, justification: 'No concern detected in reviewed excerpts.', evidence: '[]' },
      { criterion_id: 'ITSO-05', criterion_text: 'Teacher and student rights', score: 3, justification: 'Permissions remain unverified.', evidence: '   ' },
    ],
  };

  it('replaces empty serialized evidence with explicit limits and reflects them in the summary', () => {
    renderScoreboard(itsoDomain, 'itso');
    expect(screen.getByText('No SLM quotations recorded: ITSO-04, ITSO-05. See each finding for review limits.')).toBeDefined();
    for (const title of ['Student confidentiality', 'Teacher and student rights']) {
      const row = screen.getByText(title).closest('details')!;
      fireEvent.click(row.querySelector('summary')!);
      expect(row.querySelector('blockquote')).toBeNull();
    }
    expect(screen.getByText('No SLM quotation was recorded for the confidentiality check. This does not confirm that the entire module is clear.')).toBeDefined();
    expect(screen.getByText('No SLM quotation establishes teacher/student permissions or protections. Confirm these provisions during review.')).toBeDefined();
  });

  it('shows full saved narratives and source receipts on demand without truncating quoted evidence', () => {
    const justification = 'Verification remains incomplete. ' + 'Reference details require review. '.repeat(30) + 'Source: https://example.org/complete-receipt';
    const summary = 'Ownership remains provisional. ' + 'Reference coverage is incomplete. '.repeat(30) + 'Final summary limit.';
    renderScoreboard({ ...domain, summary, criteria: [{ ...domain.criteria[0], justification, evidence: '["Actual SLM passage."]' }] });
    const row = screen.getByText('Criterion 1').closest('details')!;
    fireEvent.click(row.querySelector('summary')!);
    expect(row.textContent).not.toContain('https://example.org/complete-receipt');
    expect(row.querySelector('blockquote')!.textContent).toBe('“Actual SLM passage.”');
    expect(screen.queryByText(/No SLM quotations recorded:/)).toBeNull();
    const findingButton = within(row).getByRole('button', { name: 'Show full finding and source checks' });
    expect(findingButton.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(findingButton);
    expect(within(row).getByText(justification)).toBeDefined();
    expect(findingButton.getAttribute('aria-expanded')).toBe('true');
    expect(document.getElementById(findingButton.getAttribute('aria-controls')!)!.textContent).toBe(justification);
    expect(screen.queryByText(summary)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Show full summary' }));
    expect(screen.getByText(summary)).toBeDefined();
    fireEvent.click(within(row).getByRole('button', { name: 'Show less' }));
    expect(row.textContent).not.toContain('https://example.org/complete-receipt');
    expect(document.querySelector('details details')).toBeNull();
  });

  it('keeps missing quotation notices visible when no model summary was saved', () => {
    renderScoreboard({ ...itsoDomain, summary: '' }, 'itso');
    expect(screen.getByText('Specialist summary')).toBeDefined();
    expect(screen.getByText(/No SLM quotations recorded: ITSO-04, ITSO-05/)).toBeDefined();
  });

  it('labels permitted unquoted ITSO findings without asking for nonexistent quotation evidence', () => {
    const block: DomainScoreBlock = { ...itsoDomain, criteria: [
      { ...itsoDomain.criteria[0], is_ungrounded: true, evidence_status: 'no_concern_detected' },
      { ...itsoDomain.criteria[1], is_ungrounded: true, evidence_status: 'rights_unverified' },
    ] };
    renderScoreboard(block, 'itso');
    for (const title of ['Student confidentiality', 'Teacher and student rights']) {
      const row = screen.getByText(title).closest('details')!;
      fireEvent.click(row.querySelector('summary')!);
      expect(within(row).queryByText('Check evidence')).toBeNull();
      expect(within(row).queryByText('Evidence requires reviewer confirmation.')).toBeNull();
      expect(row.querySelector('blockquote')).toBeNull();
    }
    expect(screen.getByText('No concern detected in reviewed text')).toBeDefined();
    expect(screen.getByText('Rights unverified')).toBeDefined();
    expect(screen.getByText('Rights and permissions remain unverified from the reviewed text. This score is provisional.')).toBeDefined();
    expect(screen.getByText('Confidentiality: no concern detected in reviewed text. Rights and permissions: unverified.')).toBeDefined();
    expect(screen.queryByText(/No SLM quotations recorded:/)).toBeNull();
  });

  it('retains evidence warnings for unsupported scores and missing reasoning', () => {
    renderScoreboard({ ...itsoDomain, criteria: [
      { ...itsoDomain.criteria[0], score: 2, is_ungrounded: true, evidence_status: 'no_concern_detected' },
      { ...itsoDomain.criteria[1], justification: '', is_ungrounded: true, evidence_status: 'rights_unverified' },
    ] }, 'itso');
    expect(screen.getAllByText('Check evidence')).toHaveLength(2);
    expect(screen.queryByText('Rights unverified')).toBeNull();
  });

  it('shows a plain ITSO finding with source links and actual page passages separately', () => {
    const finding = 'Originality could not be confirmed from the available sources.';
    const note = 'Readable text was found for two of five references. Author and year details remain unconfirmed.';
    const excerpt = 'The retrieved page describes the fundamentals of human-computer interaction.';
    renderScoreboard({ ...itsoDomain, criteria: [{
      criterion_id: 'ITSO-01', criterion_text: 'Originality', score: 3, justification: finding,
      evidence: '["A real module quotation."]', reference_check_note: note,
      public_sources: [{ number: 3, title: 'Human-Computer Interaction', url: 'https://example.org/book', excerpt }],
    }] }, 'itso');
    const row = screen.getByText('Originality').closest('details')!;
    fireEvent.click(row.querySelector('summary')!);
    expect(within(row).getByText(finding).textContent).toBe(finding);
    expect(within(row).getByText(note)).toBeDefined();
    expect(within(row).getByRole('link', { name: 'Source 3: Human-Computer Interaction' }).getAttribute('href')).toBe('https://example.org/book');
    expect(within(row).getByRole('region', { name: 'ITSO-01 source 3 passage' }).textContent).toBe(excerpt);
    expect(within(row).getByRole('region', { name: 'ITSO-01 SLM evidence' }).textContent).toContain('A real module quotation.');
    expect(within(row).queryByRole('button', { name: 'Show full finding and source checks' })).toBeNull();
    expect(row.textContent).not.toContain('Tool-derived');
  });
});
