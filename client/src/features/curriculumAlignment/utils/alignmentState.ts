import { isApiError, type ApiError } from '@/shared/api/http';
import type { ClientDocument, DocumentProcessingStatus } from '@/shared/types/documents';
import type {
  AlignmentCheck,
  AlignmentCoverage,
  AlignmentCoverageScope,
  AlignmentProvenance,
  AlignmentStatus,
} from '../types';

export type AlignmentSelectionState = {
  documentId: string;
  courseId: string;
  activeCheckId: string | null;
};

export type AlignmentSelectionAction =
  | { type: 'setDocument'; documentId: string }
  | { type: 'setCourse'; courseId: string }
  | { type: 'runCheckSuccess'; checkId: string }
  | { type: 'selectHistoryItem'; documentId: string; courseId: string; checkId: string }
  | { type: 'clearActiveCheck' };

export function alignmentSelectionReducer(
  state: AlignmentSelectionState,
  action: AlignmentSelectionAction,
): AlignmentSelectionState {
  switch (action.type) {
    case 'setDocument':
      return {
        ...state,
        documentId: action.documentId,
        activeCheckId: null,
      };
    case 'setCourse':
      return {
        ...state,
        courseId: action.courseId,
        activeCheckId: null,
      };
    case 'runCheckSuccess':
      return {
        ...state,
        activeCheckId: action.checkId,
      };
    case 'selectHistoryItem':
      return {
        ...state,
        documentId: action.documentId,
        courseId: action.courseId,
        activeCheckId: action.checkId,
      };
    case 'clearActiveCheck':
      return {
        ...state,
        activeCheckId: null,
      };
    default:
      return state;
  }
}

export type AlignmentDocumentEligibilityReason =
  | 'eligible'
  | 'non_slm'
  | 'unprocessed'
  | 'program_not_supported';

export type AlignmentDocumentEligibility = {
  eligible: boolean;
  reason: AlignmentDocumentEligibilityReason;
  message: string;
};

const SUPPORTED_ALIGNMENT_PROGRAMS = new Set(['bsinfotech', 'bsit']);

function normalizeProgram(value: string | null | undefined): string {
  return (value ?? '').replace(/\s+/g, '').toLowerCase();
}

export function getAlignmentDocumentEligibility(document?: ClientDocument | null): AlignmentDocumentEligibility {
  if (!document) {
    return {
      eligible: false,
      reason: 'non_slm',
      message: 'No eligible document is available for this selection.',
    };
  }

  if (document.sourceType !== 'slm') {
    return {
      eligible: false,
      reason: 'non_slm',
      message: 'This file is not an SLM. Only processed SLM documents are eligible.',
    };
  }

  if (document.processingStatus !== ('PROCESSED' as DocumentProcessingStatus)) {
    return {
      eligible: false,
      reason: 'unprocessed',
      message: 'This SLM is not processed yet. Use a processed SLM only.',
    };
  }

  const normalized = normalizeProgram(document.program);
  if (!SUPPORTED_ALIGNMENT_PROGRAMS.has(normalized)) {
    return {
      eligible: false,
      reason: 'program_not_supported',
      message: 'Not eligible for alignment checks.',
    };
  }

  return {
    eligible: true,
    reason: 'eligible',
    message: 'Eligible for alignment checks.',
  };
}

export type RequestErrorKind =
  | 'duplicate_cooldown'
  | 'no_usable_text'
  | 'program_mismatch'
  | 'not_found'
  | 'auth'
  | 'rate_limited'
  | 'network'
  | 'parse'
  | 'unknown';

export type RequestErrorState = {
  kind: RequestErrorKind;
  title: string;
  message: string;
  retryAfterSeconds?: number | null;
};

function parseRetryAfter(error: ApiError): number | null {
  const retryAfter =
    error.headers?.['retry-after'] ||
    error.headers?.['Retry-After'] ||
    error.headers?.['RETRY-AFTER'] ||
    null;

  if (!retryAfter) {
    return null;
  }

  const parsed = Number(retryAfter);
  return Number.isFinite(parsed) ? Math.max(0, parsed) : null;
}

function hasText(value: string | null | undefined): boolean {
  return typeof value === 'string' && value.trim().length > 0;
}

export function getAlignmentRequestErrorState(error: unknown): RequestErrorState | null {
  if (!isApiError(error)) {
    return {
      kind: 'network',
      title: 'Network / parse error',
      message: 'Could not contact the alignment service. Check your network and try again.',
    };
  }

  const detail = error.detail?.toLowerCase() ?? '';

  if (error.status === 401) {
    return {
      kind: 'auth',
      title: 'Authentication required',
      message: 'You are not authenticated. Please sign in and try again.',
    };
  }

  if (error.status === 404) {
    return {
      kind: 'not_found',
      title: 'Missing or deleted item',
      message: error.detail ?? 'Document or course not found.',
    };
  }

  if (error.status === 422) {
    const message = error.detail ?? 'The selected document and course are not a valid alignment pair.';
    return {
      kind: 'program_mismatch',
      title: 'Program or eligibility mismatch',
      message,
    };
  }

  if (error.status === 409) {
    return {
      kind: 'no_usable_text',
      title: 'No usable text',
      message: error.detail ?? 'The selected document has no usable text for alignment right now.',
    };
  }

  if (error.status === 429) {
    const retryAfterSeconds = parseRetryAfter(error);
    if (detail.includes('cooldown') || detail.includes('already run recently')) {
      return {
        kind: 'duplicate_cooldown',
        title: 'Duplicate check cooldown',
        message:
          error.detail ?? 'This exact check was submitted recently. Wait before rerunning the same pair.',
        retryAfterSeconds,
      };
    }
    return {
      kind: 'rate_limited',
      title: 'Rate limit reached',
      message: error.detail ?? 'Alignment checks are temporarily rate-limited.',
      retryAfterSeconds,
    };
  }

  if (hasText(error.message)) {
    return {
      kind: 'parse',
      title: 'Request error',
      message: error.message,
    };
  }

  return {
    kind: 'unknown',
    title: 'Alignment failed',
    message: 'Unexpected error while running the alignment check.',
  };
}

export type ActiveFailureKind = 'rejection' | 'transient' | 'configuration' | 'unknown';

export type ActiveFailureState = {
  kind: ActiveFailureKind;
  title: string;
  message: string;
};

function normalizeFailureKind(raw: string | null | undefined): ActiveFailureKind {
  const value = (raw ?? '').toLowerCase();
  if (value.includes('coverage') || value.includes('response') || value.includes('schema')) {
    return 'rejection';
  }
  if (value.includes('config') || value.includes('timeout') || value.includes('server')) {
    return 'transient';
  }
  if (value.includes('rate') || value.includes('quota')) {
    return 'transient';
  }
  if (value.includes('llm') || value.includes('model') || value.includes('credential')) {
    return 'configuration';
  }

  return 'unknown';
}

export function getAlignmentFailureState(check: AlignmentCheck | null): ActiveFailureState | null {
  if (!check || check.success) {
    return null;
  }

  const provenanceKind = check.provenance?.failure_kind ?? check.provenance?.error_kind;
  const nestedKind = check.provenance?.failure?.kind;
  const statusHint = (check.provenance as AlignmentProvenance | null)?.failure?.classification;
  const failureKind = normalizeFailureKind(provenanceKind ?? nestedKind ?? statusHint);

  const message =
    check.error_message ||
    check.provenance?.failure?.detail ||
    check.provenance?.error_kind ||
    'Alignment check completed with an unknown failure.';

  if (failureKind === 'configuration') {
    return {
      kind: 'configuration',
      title: 'Configuration issue',
      message,
    };
  }

  if (failureKind === 'transient') {
    return {
      kind: 'transient',
      title: 'Transient failure',
      message,
    };
  }

  if (failureKind === 'rejection') {
    return {
      kind: 'rejection',
      title: 'LLM response rejected',
      message,
    };
  }

  return {
    kind: 'unknown',
    title: 'Alignment check failed',
    message,
  };
}

export function normalizeBoundedStatus(
  status: AlignmentStatus,
  coverageScope: AlignmentCoverageScope,
): AlignmentStatus {
  if (coverageScope === 'bounded' && status === 'not_addressed') {
    return 'not_observed';
  }

  return status;
}

export function getCoverageMetadata(check: AlignmentCheck | null): AlignmentCoverage {
  const direct = check?.coverage;
  if (direct && direct.scope) {
    return direct;
  }

  if (check?.provenance?.coverage) {
    return {
      scope: check.provenance.coverage.scope,
      total_pages: check.provenance.coverage.total_pages,
      evaluated_pages: check.provenance.coverage.evaluated_pages,
      total_chars: check.provenance.coverage.total_chars,
      evaluated_chars: check.provenance.coverage.evaluated_chars,
      strategy: check.provenance.coverage.strategy,
    };
  }

  return {
    scope: 'legacy_unknown',
    total_pages: null,
    evaluated_pages: null,
    total_chars: null,
    evaluated_chars: null,
  };
}

export type CoverageBannerState = {
  kind: 'full' | 'bounded' | 'legacy';
  text: string;
};

export function buildCoverageBanner(coverage: AlignmentCoverage): CoverageBannerState {
  if (coverage.scope === 'full') {
    return {
      kind: 'full',
      text: 'Evaluation scope: full document.',
    };
  }

  if (coverage.scope === 'bounded') {
    return {
      kind: 'bounded',
      text: `Evaluated pages: ${coverage.evaluated_pages ?? 0} / ${coverage.total_pages ?? 0}`,
    };
  }

  return {
    kind: 'legacy',
    text: 'Evaluation scope unavailable',
  };
}

export type AlignmentSummary = {
  total_mapped_objectives: number;
  match: number;
  under_developed: number;
  over_developed: number;
  not_addressed: number;
  not_observed: number;
};

export function buildDisplayedSummary(check: AlignmentCheck): AlignmentSummary {
  const coverage = getCoverageMetadata(check);

  if (!check.objective_results.length) {
    const notAddressed = check.summary.not_addressed;
    const boundedNotObserved = check.summary.not_observed ?? notAddressed;

    return {
      total_mapped_objectives: check.summary.total_mapped_objectives,
      match: check.summary.match,
      under_developed: check.summary.under_developed,
      over_developed: check.summary.over_developed,
      not_addressed: coverage.scope === 'bounded' ? 0 : notAddressed,
      not_observed: coverage.scope === 'bounded' ? boundedNotObserved : check.summary.not_observed ?? 0,
    };
  }

  const base = {
    total_mapped_objectives: check.summary.total_mapped_objectives,
    match: 0,
    under_developed: 0,
    over_developed: 0,
    not_addressed: 0,
    not_observed: 0,
  };

  const derived = check.objective_results.reduce((acc, objective) => {
    const normalized = normalizeBoundedStatus(objective.status, coverage.scope);
    if (normalized === 'match') acc.match += 1;
    else if (normalized === 'under-developed') acc.under_developed += 1;
    else if (normalized === 'over-developed') acc.over_developed += 1;
    else if (normalized === 'not_observed') acc.not_observed += 1;
    else acc.not_addressed += 1;
    return acc;
  }, base);

  if (coverage.scope === 'bounded') {
    derived.not_addressed = 0;
    derived.total_mapped_objectives = derived.match + derived.under_developed + derived.over_developed + derived.not_observed;
  }

  return derived;
}

export function getResultDowngradeNote(
  originalStatus: AlignmentStatus,
  normalizedStatus: AlignmentStatus,
): string | null {
  if (originalStatus === 'not_observed') {
    return 'LLM-claimed evidence was downgraded because it did not match the evaluated pages.';
  }

  if (normalizedStatus === 'not_observed' && originalStatus === 'not_addressed') {
    return 'LLM-claimed evidence was downgraded because it did not match the evaluated pages.';
  }

  return null;
}

export type EvidenceNavigation = {
  pageNumber: number;
  evidence: string | null;
};

export function getEvidenceNavigation(
  pageNumber: number | null | undefined,
  evidence: string | null,
): EvidenceNavigation | null {
  if (!pageNumber || pageNumber <= 0) {
    return null;
  }

  return {
    pageNumber,
    evidence: evidence?.trim() ?? null,
  };
}
