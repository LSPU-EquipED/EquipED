// Unit tests for the PDF report view-model layer.
//
// These tests focus on what the PDF actually renders, not on jsPDF
// internals. They assert that:
//   * the canonical 1-4 scale and 0-100 monitoring % stay separate;
//   * partial / failed / skipped agents are not turned into fake
//     scorecards;
//   * unavailable institutional metadata renders as a sentinel rather
//     than as a hard-coded string.
import { describe, expect, it } from 'vitest';
import type { EvaluationResultsResponse } from '../../types';
import {
  REPORT_AGENT_ORDER,
  buildReportModel,
  findUnsupportedChars,
  formatAgentMonitoringLabel,
  formatAgentRatingLabel,
  formatAgentSubtotalLabel,
  formatHeaderField,
} from '../pdfReport';

function makeResults(
  overrides: Partial<EvaluationResultsResponse> = {},
): EvaluationResultsResponse {
  return {
    evaluation_id: 'eval-1',
    document_id: 'doc-1',
    document_title: 'Sample SLM',
    program: 'BSIT',
    synthesized_score: 86.0,
    overall_score: 3.44,
    adjectival_rating: 'Satisfactory',
    domain_scores: {
      sme: {
        criteria: [
          { criterion_id: 's1', criterion_text: 'Accuracy', score: 4, justification: 'Precise.' },
        ],
        subtotal: 4,
        max_score: 4,
        status: 'OK',
        adjectival_rating: 'Very Satisfactory',
        summary: 'Accurate content overall.',
      },
      coordinator: {
        criteria: [
          { criterion_id: 'c1', criterion_text: 'Alignment', score: 3, justification: 'Aligned.' },
        ],
        subtotal: 3,
        max_score: 4,
        status: 'OK',
        adjectival_rating: 'Satisfactory',
        summary: 'Curriculum aligned to outcomes.',
      },
      gad: {
        criteria: [
          {
            criterion_id: 'g1',
            criterion_text: 'Inclusivity',
            score: 4,
            justification: 'Inclusive.',
          },
        ],
        subtotal: 4,
        max_score: 4,
        status: 'OK',
        adjectival_rating: 'Very Satisfactory',
        summary: 'GAD review complete.',
      },
      itso: {
        criteria: [
          { criterion_id: 'i1', criterion_text: 'Privacy', score: 3, justification: 'Compliant.' },
        ],
        subtotal: 3,
        max_score: 4,
        status: 'OK',
        adjectival_rating: 'Satisfactory',
        summary: 'ITSO review complete.',
      },
    },
    flags: [],
    active_agents: ['sme', 'coordinator', 'gad', 'itso'],
    failed_agents: [],
    is_partial: false,
    partial_reason: null,
    evaluation_status: 'COMPLETED',
    submitted_at: null,
    completed_at: '2026-07-15T10:00:00Z',
    duration_seconds: 12,
    ...overrides,
  };
}

describe('buildReportModel - canonical scale separation', () => {
  it('keeps the 1-4 overall and 0-100 monitoring % on distinct lines', () => {
    const model = buildReportModel(makeResults());
    expect(model.header.hasOverall).toBe(true);
    expect(model.header.overallScore).toBe(3.44);
    expect(model.header.monitoringPercent).toBe(86);
    expect(model.header.overallScore).toBeLessThanOrEqual(4);
    expect(model.header.monitoringPercent).toBeGreaterThanOrEqual(0);
    expect(model.header.monitoringPercent).toBeLessThanOrEqual(100);
  });

  it('reports an unavailable overall when the server returned no synthesis', () => {
    const model = buildReportModel(makeResults({ overall_score: undefined, synthesized_score: 0 }));
    expect(model.header.hasOverall).toBe(false);
    expect(model.header.overallScore).toBeNull();
  });
});

describe('buildReportModel - partial / skipped / failed agents', () => {
  it('marks Coordinator as skipped in a deliberate no-curriculum partial', () => {
    const model = buildReportModel(
      makeResults({
        is_partial: true,
        partial_reason: 'No curriculum reference was attached.',
        domain_scores: {
          sme: makeResults().domain_scores.sme,
          gad: makeResults().domain_scores.gad,
          itso: makeResults().domain_scores.itso,
        },
        active_agents: ['sme', 'gad', 'itso'],
        failed_agents: [],
      }),
    );
    const coordinator = model.agents.find((a) => a.agentId === 'coordinator')!;
    expect(coordinator.state).toBe('skipped_partial');
    expect(coordinator.subtotal).toBeNull();
    expect(coordinator.criteria).toHaveLength(0);
    expect(formatAgentSubtotalLabel(coordinator)).toBe('—');
    expect(formatAgentMonitoringLabel(coordinator)).toBe('Skipped');
    expect(formatAgentRatingLabel(coordinator)).toBe('Skipped');
  });

  it('does not invent a scorecard for a failed agent', () => {
    const model = buildReportModel(
      makeResults({
        is_partial: true,
        partial_reason: 'GAD agent failed during evaluation.',
        domain_scores: {
          sme: makeResults().domain_scores.sme,
          coordinator: makeResults().domain_scores.coordinator,
          itso: makeResults().domain_scores.itso,
        },
        active_agents: ['sme', 'coordinator', 'itso'],
        failed_agents: ['gad'],
      }),
    );
    const gad = model.agents.find((a) => a.agentId === 'gad')!;
    expect(gad.state).toBe('failed');
    expect(gad.subtotal).toBeNull();
    expect(gad.criteria).toHaveLength(0);
    expect(formatAgentRatingLabel(gad)).toBe('Unavailable (failed)');
  });

  it('keeps the canonical agent order', () => {
    const model = buildReportModel(makeResults());
    const orderedIds = model.agents.map((a) => a.agentId);
    expect(orderedIds).toEqual([...REPORT_AGENT_ORDER]);
  });
});

describe('buildReportModel - unavailable institutional metadata', () => {
  it('uses null for missing document title and program', () => {
    const model = buildReportModel(makeResults({ document_title: undefined, program: undefined }));
    expect(model.header.documentTitle).toBeNull();
    expect(model.header.program).toBeNull();
    expect(formatHeaderField(model.header.documentTitle, 'Not available')).toBe('Not available');
    expect(formatHeaderField(model.header.program, 'Not specified')).toBe('Not specified');
  });

  it('falls back to the helper-provided label for blank strings', () => {
    expect(formatHeaderField('', 'Not available')).toBe('Not available');
    expect(formatHeaderField('   ', 'Not available')).toBe('Not available');
  });
});

describe('buildReportModel - chunk_id sanitization', () => {
  it('removes raw chunk_id tokens from criterion text and notes', () => {
    const model = buildReportModel(
      makeResults({
        domain_scores: {
          sme: {
            criteria: [
              {
                criterion_id: 's1',
                criterion_text: 'chunk_id "abc-123" accuracy check',
                score: 3,
                justification: 'See chunk_id "abc-123" for evidence.',
              },
            ],
            subtotal: 3,
            max_score: 4,
            status: 'OK',
            adjectival_rating: 'Satisfactory',
            summary: 'OK',
          },
          coordinator: { criteria: [], subtotal: 0, max_score: 4, status: 'OK' },
          gad: { criteria: [], subtotal: 0, max_score: 4, status: 'OK' },
          itso: { criteria: [], subtotal: 0, max_score: 4, status: 'OK' },
        },
      }),
    );
    const sme = model.agents.find((a) => a.agentId === 'sme')!;
    expect(sme.criteria).toHaveLength(1);
    expect(sme.criteria[0].text).not.toContain('chunk_id');
    expect(sme.criteria[0].text).not.toContain('abc-123');
    expect(sme.criteria[0].note).not.toContain('chunk_id');
  });
});

describe('findUnsupportedChars', () => {
  it('returns an empty string for plain ASCII / Latin-1 input', () => {
    expect(findUnsupportedChars('Laguna State Polytechnic University')).toBe('');
    expect(findUnsupportedChars('Mabuhay! ñ Ñ ¿¡')).toBe('');
  });

  it('flags characters outside the WinAnsi range', () => {
    // CJK is outside Latin-1.
    const chars = findUnsupportedChars('hello 你好 world');
    expect(chars).toContain('你');
    expect(chars).toContain('好');
  });
});

// Coordinator status regression: a Coordinator listed in
// `failed_agents` or carrying a `status: 'ERROR'` block must always
// render as failed, even when the overall result is also partial
// (which happens whenever any agent fails). A `skipped_partial`
// verdict is reserved for the deliberate no-curriculum path, which
// the server signals by keeping `evaluation_status === 'COMPLETED'`
// while marking the result partial.
describe('buildReportModel - Coordinator status discrimination', () => {
  it('marks Coordinator as failed when listed in failed_agents, not as skipped_partial', () => {
    const model = buildReportModel(
      makeResults({
        // The overall status is FAILED because Coordinator crashed;
        // the result is partial because synthesis normalized over the
        // surviving agents.
        is_partial: true,
        partial_reason: 'coordinator: crashed during retrieval',
        evaluation_status: 'FAILED',
        domain_scores: {
          sme: makeResults().domain_scores.sme,
          // No coordinator block - it never produced a result.
          gad: makeResults().domain_scores.gad,
          itso: makeResults().domain_scores.itso,
        },
        active_agents: ['sme', 'gad', 'itso'],
        failed_agents: ['coordinator'],
      }),
    );
    const coordinator = model.agents.find((a) => a.agentId === 'coordinator')!;
    expect(coordinator.state).toBe('failed');
    expect(coordinator.state).not.toBe('skipped_partial');
    expect(coordinator.subtotal).toBeNull();
    expect(coordinator.criteria).toHaveLength(0);
    expect(formatAgentRatingLabel(coordinator)).toBe('Unavailable (failed)');
    expect(formatAgentMonitoringLabel(coordinator)).toBe('Unavailable');
    // The reason must not mention an intentional / deliberate skip.
    expect(coordinator.stateReason.toLowerCase()).not.toContain('skipped');
    expect(coordinator.stateReason.toLowerCase()).not.toContain('deliberate');
    expect(coordinator.stateReason.toLowerCase()).toContain('did not complete');
  });

  it('marks Coordinator as failed when its domain block carries status ERROR', () => {
    const model = buildReportModel(
      makeResults({
        is_partial: true,
        partial_reason: 'partial synthesis after Coordinator error',
        evaluation_status: 'FAILED',
        // Coordinator block is present but flagged ERROR. It must
        // not be reported as available.
        domain_scores: {
          sme: makeResults().domain_scores.sme,
          coordinator: {
            criteria: [],
            subtotal: 0,
            max_score: 4,
            status: 'ERROR',
            summary: 'Coordinator crashed during curriculum retrieval.',
          },
          gad: makeResults().domain_scores.gad,
          itso: makeResults().domain_scores.itso,
        },
        active_agents: ['sme', 'coordinator', 'gad', 'itso'],
        failed_agents: [],
      }),
    );
    const coordinator = model.agents.find((a) => a.agentId === 'coordinator')!;
    expect(coordinator.state).toBe('failed');
    expect(coordinator.state).not.toBe('skipped_partial');
    expect(coordinator.stateReason.toLowerCase()).toContain('error');
  });

  it('marks Coordinator as failed in an accidental partial even when failed_agents is empty', () => {
    // The server might forget to add the agent to `failed_agents` in
    // some failure modes (e.g. the agent raised before being
    // recorded). The view model must still treat the missing
    // Coordinator as failed, not as a deliberate skip, when the
    // overall status is FAILED.
    const model = buildReportModel(
      makeResults({
        is_partial: true,
        partial_reason: 'Partial: some agents failed',
        evaluation_status: 'FAILED',
        domain_scores: {
          sme: makeResults().domain_scores.sme,
          gad: makeResults().domain_scores.gad,
          itso: makeResults().domain_scores.itso,
        },
        active_agents: ['sme', 'gad', 'itso'],
        failed_agents: [],
      }),
    );
    const coordinator = model.agents.find((a) => a.agentId === 'coordinator')!;
    expect(coordinator.state).toBe('failed');
    expect(coordinator.state).not.toBe('skipped_partial');
  });

  it('marks Coordinator as skipped_partial only for the deliberate no-curriculum case (COMPLETED + partial)', () => {
    // Sanity check: the original happy path is preserved. The
    // server signals a deliberate no-curriculum partial by completing
    // the job successfully and attaching a partial reason that
    // names the missing curriculum.
    const model = buildReportModel(
      makeResults({
        is_partial: true,
        partial_reason: 'No curriculum reference was attached.',
        evaluation_status: 'COMPLETED',
        domain_scores: {
          sme: makeResults().domain_scores.sme,
          gad: makeResults().domain_scores.gad,
          itso: makeResults().domain_scores.itso,
        },
        active_agents: ['sme', 'gad', 'itso'],
        failed_agents: [],
      }),
    );
    const coordinator = model.agents.find((a) => a.agentId === 'coordinator')!;
    expect(coordinator.state).toBe('skipped_partial');
    expect(coordinator.stateReason).toContain('No curriculum reference');
  });

  it('does not infer a deliberate skip for other agents missing from the domain map', () => {
    // Non-coordinator agents that disappear from the domain map
    // without a `failed_agents` listing and without an ERROR block
    // are reported as `unavailable`, never as a deliberate skip.
    const model = buildReportModel(
      makeResults({
        is_partial: true,
        partial_reason: 'sme: ran out of context',
        evaluation_status: 'FAILED',
        domain_scores: {
          // SME is gone entirely, not in failed_agents.
          coordinator: makeResults().domain_scores.coordinator,
          gad: makeResults().domain_scores.gad,
          itso: makeResults().domain_scores.itso,
        },
        active_agents: ['coordinator', 'gad', 'itso'],
        failed_agents: ['sme'],
      }),
    );
    const sme = model.agents.find((a) => a.agentId === 'sme')!;
    expect(sme.state).toBe('failed');
    expect(sme.state).not.toBe('skipped_partial');
  });
});

describe('buildReportModel - dynamic CID forms and ungrounded/legacy notice', () => {
  it('explicitly marks ungrounded criteria with tierLabel Ungrounded and isUngrounded flag', () => {
    const model = buildReportModel(
      makeResults({
        domain_scores: {
          sme: {
            criteria: [
              {
                criterion_id: 'CUSTOM-01',
                criterion_text: 'Dynamic Domain Criterion',
                description: 'Authoritative dynamically authored criterion',
                score: 4,
                justification: 'Well presented.',
                is_ungrounded: true,
              },
            ],
            subtotal: 4,
            max_score: 4,
            status: 'OK',
            version: 3,
            form_snapshot_id: 'snap-1',
          },
        },
      }),
    );

    const sme = model.agents.find((a) => a.agentId === 'sme')!;
    expect(sme.criteria).toHaveLength(1);
    expect(sme.criteria[0].criterionId).toBe('CUSTOM-01');
    expect(sme.criteria[0].isUngrounded).toBe(true);
    expect(sme.criteria[0].tierLabel).toBe('Ungrounded');
    expect(sme.criteria[0].description).toBe('Authoritative dynamically authored criterion');
    expect(sme.revisionLabel).toBe('Revision 3');
  });

  it('renders exact legacy notice without inventing a revision when legacy_notice is set', () => {
    const model = buildReportModel(
      makeResults({
        legacy_notice: 'Legacy — form snapshot unavailable',
        domain_scores: {
          sme: {
            criteria: [
              {
                criterion_id: 'LEGACY-01',
                criterion_text: 'Historical criterion',
                score: 3,
                justification: 'Legacy output.',
                is_ungrounded: false,
              },
            ],
            subtotal: 3,
            max_score: 4,
            status: 'OK',
            version: undefined,
            form_snapshot_id: undefined,
          },
        },
      }),
    );

    expect(model.header.legacyNotice).toBe('Legacy — form snapshot unavailable');
    const sme = model.agents.find((a) => a.agentId === 'sme')!;
    expect(sme.revisionLabel).toBe('Legacy — form snapshot unavailable');
    expect(sme.revisionLabel).not.toContain('Revision');
  });
});
