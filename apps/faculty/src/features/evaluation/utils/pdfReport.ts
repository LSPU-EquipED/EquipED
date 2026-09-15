// PDF report view models and shared rendering helpers.
//
// The PDF is derived from the same evaluation-results payload the
// interactive scorecard uses, so it never invents fields that the
// persisted result does not contain. The view-model layer normalizes
// raw payloads into a typed structure with explicit "unavailable"
// placeholders for missing metadata and explicit "skipped" / "failed"
// sections for agents that did not produce a scorecard.

import type { CriterionScoreItem, EvaluationResultsResponse } from '../types';
import {
  CANONICAL_MAX_SCORE,
  EXPORT_CRITERION_NOTE_MAX_CHARS,
  EXPORT_FLAG_REASON_MAX_CHARS,
  PDF_PAGE_BOTTOM_MM,
  PDF_PAGE_TOP_RESUME_MM,
  adjectivalRating,
  agentDisplayLabel,
  boundNarrative,
  cleanJustification,
  formatMonitoringPercent,
  formatScore,
  monitoringPercentage,
  scoreTier,
} from './scoreHelpers';

export const REPORT_AGENT_ORDER = ['sme', 'coordinator', 'gad', 'itso'] as const;
export type ReportAgentId = (typeof REPORT_AGENT_ORDER)[number];

export type ReportAgentSectionState = 'available' | 'skipped_partial' | 'failed' | 'unavailable';

export interface ReportAgentSection {
  agentId: ReportAgentId | string;
  displayLabel: string;
  revisionLabel: string | null;
  state: ReportAgentSectionState;
  stateReason: string;
  subtotal: number | null;
  maxScore: number | null;
  adjectivalRating: string;
  monitoringPercent: number | null;
  criteria: ReadonlyArray<ReportCriterion>;
}

export interface ReportCriterion {
  criterionId: string;
  index: number;
  text: string;
  score: number;
  scaleLabel: string;
  tier: ReturnType<typeof scoreTier>;
  tierLabel: string;
  note: string;
  isUngrounded: boolean;
  description: string | null;
}

export interface ReportFlag {
  flagId: string;
  agentId: string;
  agentLabel: string;
  criterionText: string;
  score: number | null;
  scaleLabel: string;
  reason: string;
}

export interface ReportHeader {
  evaluationId: string;
  documentId: string;
  documentTitle: string | null;
  program: string | null;
  evaluationStatus: string;
  completedAt: string | null;
  isPartial: boolean;
  partialReason: string | null;
  overallScore: number | null;
  overallAdjectival: string;
  monitoringPercent: number | null;
  hasOverall: boolean;
  legacyNotice: string | null;
}

export interface ReportModel {
  header: ReportHeader;
  agents: ReadonlyArray<ReportAgentSection>;
  flags: ReadonlyArray<ReportFlag>;
}

// Localized reason strings. Kept as constants so tests can assert on
// the user-facing wording without coupling to a hard-coded literal.
const REASON_FAILED_BY_STATUS =
  'This agent reported an error. Other agent results may still be available.';
const REASON_FAILED_BY_LIST =
  'This agent did not complete. The overall evaluation has been marked partial and the remaining agents were weighted accordingly.';
const REASON_UNAVAILABLE = 'No agent output was recorded for this domain.';
const REASON_COORDINATOR_SKIPPED_FALLBACK =
  'Program Coordinator curriculum-grounded review was skipped because no curriculum reference was available.';

function resolveAgentState(
  agentId: string,
  domainBlock: EvaluationResultsResponse['domain_scores'][string] | undefined,
  results: EvaluationResultsResponse,
): { state: ReportAgentSectionState; reason: string } {
  // 1. An agent is "failed" if either the server explicitly listed
  //    it in `failed_agents` or the persisted domain block carries
  //    an `ERROR` status. This check must come first so a failed
  //    Coordinator is never misreported as a deliberate partial
  //    skip.
  const failedByList = results.failed_agents?.includes(agentId) ?? false;
  const failedByBlock = domainBlock?.status === 'ERROR';
  if (failedByList || failedByBlock) {
    return {
      state: 'failed',
      reason: failedByBlock ? REASON_FAILED_BY_STATUS : REASON_FAILED_BY_LIST,
    };
  }

  // 2. The overall `evaluation_status` is the server's authoritative
  //    signal that discriminates a deliberate no-curriculum partial
  //    (which the server completes with `evaluation_status =
  //    'COMPLETED'`) from an accidental partial caused by an agent
  //    crash (which the server finishes with `evaluation_status =
  //    'FAILED'`). We use that discriminator to decide what a
  //    missing domain block actually means.
  const overallFailed = results.evaluation_status === 'FAILED';

  // 2a. A missing Coordinator block under a FAILED evaluation must
  //     be reported as failed, not as a deliberate skip and not as
  //     "no output recorded". The server's FAILED status means
  //     something went wrong; if Coordinator is missing too, the
  //     honest read is that the agent did not complete.
  if (agentId === 'coordinator' && !domainBlock && overallFailed) {
    return {
      state: 'failed',
      reason: REASON_FAILED_BY_LIST,
    };
  }

  // 2b. A missing Coordinator block under a COMPLETED-but-partial
  //     evaluation is the deliberate no-curriculum path. Only this
  //     combination is allowed to render as `skipped_partial`.
  const isDeliberatePartialSkip =
    agentId === 'coordinator' && !domainBlock && results.is_partial && !overallFailed;
  if (isDeliberatePartialSkip) {
    return {
      state: 'skipped_partial',
      reason: results.partial_reason || REASON_COORDINATOR_SKIPPED_FALLBACK,
    };
  }

  // 3. No domain block, not failed, and not a deliberate partial
  //    skip: the agent simply produced no output we can report.
  if (!domainBlock) {
    return {
      state: 'unavailable',
      reason: REASON_UNAVAILABLE,
    };
  }

  return { state: 'available', reason: '' };
}

function buildCriterionRows(criteria: ReadonlyArray<CriterionScoreItem>): ReportCriterion[] {
  return criteria.map((criterion, index) => {
    const isUngrounded = Boolean(criterion.is_ungrounded);
    const tier = scoreTier(criterion.score);
    const tierLabel = isUngrounded
      ? 'Ungrounded'
      : tier === 'strong'
        ? 'Strong'
        : tier === 'moderate'
          ? 'Moderate'
          : tier === 'weak'
            ? 'Needs attention'
            : 'Not available';
    const note = boundNarrative(
      criterion.justification || criterion.evidence || '',
      EXPORT_CRITERION_NOTE_MAX_CHARS,
    );
    return {
      criterionId: criterion.criterion_id,
      index: index + 1,
      text: cleanJustification(criterion.criterion_text) || '(criterion text unavailable)',
      score: Number.isFinite(criterion.score) ? criterion.score : 0,
      scaleLabel: '1-4',
      tier,
      tierLabel,
      note,
      isUngrounded,
      description: criterion.description ?? null,
    };
  });
}

function resolveRevisionLabel(
  domainBlock: EvaluationResultsResponse['domain_scores'][string] | undefined,
  results: EvaluationResultsResponse,
): string | null {
  if (results.legacy_notice || (domainBlock && domainBlock.form_snapshot_id == null)) {
    return 'Legacy — form snapshot unavailable';
  }
  if (domainBlock?.version != null) {
    return `Revision ${domainBlock.version}`;
  }
  return null;
}

export function buildReportModel(results: EvaluationResultsResponse): ReportModel {
  const domainScores = results.domain_scores || {};
  const agents: ReportAgentSection[] = REPORT_AGENT_ORDER.map((agentId) => {
    const domain = domainScores[agentId];
    const { state, reason } = resolveAgentState(agentId, domain, results);
    const subtotal = domain?.subtotal ?? null;
    const maxScore = domain?.max_score ?? CANONICAL_MAX_SCORE;
    const monitoring =
      subtotal != null && domain
        ? monitoringPercentage(subtotal, maxScore || CANONICAL_MAX_SCORE)
        : null;
    const revisionLabel = resolveRevisionLabel(domain, results);
    return {
      agentId,
      displayLabel: agentDisplayLabel(agentId),
      revisionLabel,
      state,
      stateReason: reason,
      subtotal,
      maxScore: domain?.max_score ?? null,
      adjectivalRating: domain?.adjectival_rating || adjectivalRating(subtotal),
      monitoringPercent: monitoring,
      criteria: domain ? buildCriterionRows(domain.criteria) : [],
    };
  });

  // Keep the canonical agent order, but make sure any unexpected agent
  // recorded in the payload still renders. (Defensive: order keys come
  // from the typed enum above, but the data shape permits extras.)
  for (const extra of Object.keys(domainScores)) {
    if (REPORT_AGENT_ORDER.includes(extra as ReportAgentId)) continue;
    const domain = domainScores[extra];
    const { state, reason } = resolveAgentState(extra, domain, results);
    const revisionLabel = resolveRevisionLabel(domain, results);
    agents.push({
      agentId: extra,
      displayLabel: agentDisplayLabel(extra),
      revisionLabel,
      state,
      stateReason: reason,
      subtotal: domain?.subtotal ?? null,
      maxScore: domain?.max_score ?? null,
      adjectivalRating: domain?.adjectival_rating || adjectivalRating(domain?.subtotal ?? null),
      monitoringPercent:
        domain?.subtotal != null && domain
          ? monitoringPercentage(domain.subtotal, domain.max_score || CANONICAL_MAX_SCORE)
          : null,
      criteria: domain ? buildCriterionRows(domain.criteria) : [],
    });
  }

  const flags: ReportFlag[] = (results.flags || []).map((flag) => ({
    flagId: flag.flag_id,
    agentId: flag.agent_id,
    agentLabel: agentDisplayLabel(flag.agent_id),
    criterionText: cleanJustification(flag.criterion_text) || '(criterion text unavailable)',
    score: Number.isFinite(flag.score) ? flag.score : null,
    scaleLabel: '1-4',
    reason: boundNarrative(flag.justification, EXPORT_FLAG_REASON_MAX_CHARS),
  }));

  const hasOverall = typeof results.overall_score === 'number';
  const overallScore = hasOverall ? (results.overall_score as number) : null;
  const monitoringPercent =
    overallScore != null ? monitoringPercentage(overallScore, CANONICAL_MAX_SCORE) : null;

  return {
    header: {
      evaluationId: results.evaluation_id,
      documentId: results.document_id,
      documentTitle: results.document_title ?? null,
      program: results.program ?? null,
      evaluationStatus: results.evaluation_status || 'UNKNOWN',
      completedAt: results.completed_at ?? null,
      isPartial: Boolean(results.is_partial),
      partialReason: results.partial_reason ?? null,
      overallScore,
      overallAdjectival: results.adjectival_rating || adjectivalRating(overallScore),
      monitoringPercent,
      hasOverall,
      legacyNotice: results.legacy_notice ?? null,
    },
    agents,
    flags,
  };
}

export function formatHeaderField(value: string | null | undefined, fallback: string): string {
  const trimmed = (value || '').trim();
  return trimmed.length > 0 ? trimmed : fallback;
}

export function formatAgentSubtotalLabel(section: ReportAgentSection): string {
  if (section.state !== 'available' || section.subtotal == null || section.maxScore == null) {
    return '—';
  }
  return `${formatScore(section.subtotal)} / ${formatScore(section.maxScore)}`;
}

export function formatAgentRatingLabel(section: ReportAgentSection): string {
  if (section.state === 'available') return section.adjectivalRating || 'Not available';
  if (section.state === 'skipped_partial') return 'Skipped';
  if (section.state === 'failed') return 'Unavailable (failed)';
  return 'Unavailable';
}

export function formatAgentMonitoringLabel(section: ReportAgentSection): string {
  if (section.state === 'skipped_partial') return 'Skipped';
  if (section.state === 'failed') return 'Unavailable';
  if (section.state === 'unavailable') return 'Unavailable';
  if (section.subtotal == null || section.maxScore == null) return 'Unavailable';
  return formatMonitoringPercent(section.subtotal, section.maxScore || CANONICAL_MAX_SCORE);
}

// Validate a piece of text against the jsPDF font in use. The built-in
// Helvetica/Times/Courier fonts only support WinAnsi (Latin-1) plus the
// standard PDF symbols. Strings containing characters outside that set
// would be rendered as missing glyphs. We return the offending ranges
// for diagnostics.
//
// We allow tab, LF and CR explicitly (whitespace is harmless in PDFs)
// and the printable ASCII + Latin-1 Supplement ranges that WinAnsi covers.
// The character ranges are built from char codes so the source does not
// contain raw control characters (which trip the `no-control-regex` lint).
const NON_WIN_ANSI_RANGES = [
  [0x09, 0x0d], // \t \n \v \f \r
  [0x20, 0x7e], // printable ASCII
  [0xa0, 0xff], // Latin-1 Supplement
];
const NON_WIN_ANSI_PATTERN = NON_WIN_ANSI_RANGES.map(([start, end]) =>
  start === end
    ? `\\u${start.toString(16).padStart(4, '0')}`
    : `\\u${start.toString(16).padStart(4, '0')}-\\u${end.toString(16).padStart(4, '0')}`,
).join('');
const NON_WIN_ANSI = new RegExp(`[^${NON_WIN_ANSI_PATTERN}]`, 'g');

export function findUnsupportedChars(text: string): string {
  if (!text) return '';
  const matches = text.match(NON_WIN_ANSI) || [];
  if (matches.length === 0) return '';
  // De-duplicate to keep the diagnostic readable.
  return Array.from(new Set(matches)).join('');
}

export function requirePageBreak(
  pdf: {
    addPage: (size?: string, orientation?: string) => void;
    internal: { pageSize: { getHeight: () => number } };
  },
  nextY: number,
  pageBottomGuard: number = PDF_PAGE_BOTTOM_MM,
): number {
  const pageHeight = pdf.internal.pageSize.getHeight();
  const guard = Math.min(pageBottomGuard, pageHeight - 12);
  if (nextY > guard) {
    pdf.addPage('a4', 'portrait');
    return PDF_PAGE_TOP_RESUME_MM;
  }
  return nextY;
}
