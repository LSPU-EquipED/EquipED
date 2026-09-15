import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';
import type { AlignmentRun } from '../../types';
import { AlignmentResultView } from '../AlignmentResultView';
import { ReplaceAlignmentModal } from '../ReplaceAlignmentModal';
import { drawAlignmentPdf } from '../../utils/alignmentPdf';
import {
  isAlignmentActive,
  levelLabels,
  levelStyles,
  shouldConfirmAlignmentReplacement,
} from '../../utils/alignmentPresentation';

function completedRun(): AlignmentRun {
  return {
    alignment_id: 'alignment-1',
    slm_document_id: 'slm-1',
    slm_title: 'Networking Module',
    syllabus_document_id: 'syllabus-1',
    syllabus_title: 'Networking Syllabus',
    requested_by: 'user-1',
    status: 'COMPLETED',
    alignment_level: 'PARTIALLY_MEETS',
    justification:
      'The SLM partially meets the selected syllabus. 1 of 2 substantial topics have supported syllabus matches.',
    model_name: 'sme-model',
    provenance: { agent_configuration: 'sme', requested_model: 'sme-model' },
    advisory_only: true,
    created_at: '2026-08-03T00:00:00Z',
    completed_at: '2026-08-03T00:01:00Z',
    updated_at: '2026-08-03T00:01:00Z',
    alignment_artifact: {
      status: 'PARTIALLY_MEETS',
      statement: 'Detailed result',
      total_topics: 2,
      aligned_topics: 1,
      advisory_only: true,
      content_matches: [
        {
          topic_id: 'T1',
          topic: 'Network configuration',
          slm_chunk_id: 'chunk-1',
          slm_page_number: 2,
          slm_evidence: 'Configure a network.',
          status: 'ALIGNED',
          rationale: 'The syllabus explicitly includes network configuration.',
          chunk_id: 'syllabus-chunk-1',
          content_ref: 'Week 2',
          content_text: 'Local area network configuration',
          page_number: 3,
        },
      ],
      unmatched_topics: [
        {
          topic_id: 'T2',
          topic: 'Mobile game development',
          slm_chunk_id: 'chunk-2',
          slm_page_number: 5,
          slm_evidence: 'Create a mobile game.',
          status: 'NOT_ALIGNED',
          rationale: 'No syllabus course content covers game development.',
        },
      ],
    },
  };
}

describe('alignment presentation', () => {
  it('assigns a distinct accessible label and color treatment to every level', () => {
    expect(Object.keys(levelLabels)).toEqual([
      'MEETS',
      'PARTIALLY_MEETS',
      'DOES_NOT_MEET',
      'UNAVAILABLE',
    ]);
    expect(new Set(Object.values(levelStyles).map((style) => style.badge)).size).toBe(4);
  });

  it('requires confirmation only when a stored result is terminal', () => {
    expect(shouldConfirmAlignmentReplacement(completedRun())).toBe(true);
    expect(shouldConfirmAlignmentReplacement({ ...completedRun(), status: 'FAILED' })).toBe(true);
    expect(shouldConfirmAlignmentReplacement({ ...completedRun(), status: 'RUNNING' })).toBe(false);
    expect(isAlignmentActive({ ...completedRun(), status: 'QUEUED' })).toBe(true);
  });

  it('renders aligned topics before topics outside the syllabus', () => {
    const markup = renderToStaticMarkup(<AlignmentResultView run={completedRun()} />);
    expect(markup.indexOf('Aligned topics')).toBeLessThan(
      markup.indexOf('Topics outside the syllabus'),
    );
    expect(markup).toContain('Why this level was assigned');
  });

  it('renders the permanent replacement warning only while open', () => {
    const props = { busy: false, onCancel: vi.fn(), onConfirm: vi.fn() };
    expect(renderToStaticMarkup(<ReplaceAlignmentModal open={false} {...props} />)).toBe('');
    const markup = renderToStaticMarkup(<ReplaceAlignmentModal open {...props} />);
    expect(markup).toContain('permanently replace');
    expect(markup).toContain('Replace and evaluate');
  });
});

describe('alignment PDF', () => {
  it('produces a valid full report PDF', () => {
    const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
    drawAlignmentPdf(pdf, completedRun(), autoTable);
    const bytes = new Uint8Array(pdf.output('arraybuffer'));
    expect(new TextDecoder().decode(bytes.slice(0, 5))).toBe('%PDF-');
    expect(bytes.length).toBeGreaterThan(1_000);
  });
});
