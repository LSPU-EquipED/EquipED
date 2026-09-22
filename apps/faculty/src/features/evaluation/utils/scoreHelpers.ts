import type { CriterionScoreItem, EvaluationFormPresentation } from '../types';

// Canonical helpers shared by the interactive scorecard and the PDF export.
//
// Keeping these rules in one place guarantees the on-screen scorecard, the
// synthesized scorecard PDF, and the per-agent export PDF all render the
// same numbers and the same adjectival buckets. The numbers here mirror the
// server's `score_to_adjectival` thresholds and the canonical 1-4 agent
// scale defined in `server/modules/synthesis/schemas.py`.

export const CANONICAL_MAX_SCORE = 4;
export const SCORE_SCALE_LABEL = '1-4 scale';

// Adjectival thresholds. Values are inclusive lower bounds.
const ADJECTIVAL_THRESHOLDS: ReadonlyArray<readonly [number, string]> = [
  [3.5, 'Very Satisfactory'],
  [2.5, 'Satisfactory'],
  [1.5, 'Needs Improvement'],
  [0, 'Poor'],
];

// Narrative / evidence bounds applied to PDF exports. These keep tables
// paginating safely and stop oversized model outputs from blowing up a page.
export const EXPORT_NARRATIVE_MAX_CHARS = 600;
export const EXPORT_CRITERION_NOTE_MAX_CHARS = 280;
export const EXPORT_FLAG_REASON_MAX_CHARS = 220;

// The PDF adds page breaks when content draws within this distance of the
// page-bottom guard. Chosen empirically so a single criterion block always
// fits on the page it starts on.
export const PDF_PAGE_BOTTOM_MM = 255;
export const PDF_PAGE_TOP_RESUME_MM = 18;

// Raw chunk identifiers look like `chunk_id "abc-123"` or `chunk_id abc-123`.
// They are internal RAG identifiers and must never appear in exported
// narrative. Match them conservatively, including surrounding brackets
// and quoted-string variants.
const CHUNK_ID_PATTERNS: ReadonlyArray<RegExp> = [
  // Bracketed / parenthesized forms, e.g. [chunk_id: foo-1] or (chunk_id=bar-2).
  /\[chunk[_-]?id[^\]]*\]/gi,
  /\(chunk[_-]?id[^)]*\)/gi,
  // Bare `chunk_id: foo-1` or `chunk_id="foo-1"` forms.
  /\bchunk[_-]?id\s*[:=]\s*['"]?[\w\-./]+['"]?/gi,
  // Bare `chunk_id foo-1` form (no separator) - we still strip the id token
  // but keep trailing prose by stopping at the first whitespace after the id.
  /\bchunk[_-]?id\s+['"][^'"]+['"]/gi,
  /\bchunk[_-]?id\s+\S+/gi,
];

export function formatScore(value: number): string {
  if (!Number.isFinite(value)) return '-';
  const fixed = value.toFixed(2);
  return fixed.endsWith('.00') ? String(Math.round(value)) : fixed;
}

// Canonical adjectival rating for a 1-4 subtotal/average. The same bucket
// rules as `score_to_adjectival` on the server.
export function adjectivalRating(score: number | null | undefined): string {
  if (score == null || !Number.isFinite(score)) return 'Not available';
  for (const [threshold, label] of ADJECTIVAL_THRESHOLDS) {
    if (score >= threshold) return label;
  }
  return 'Not available';
}

// 0-100 monitoring percentage derived from a canonical 1-4 score. This is a
// derived display value only; the underlying stored scores are 1-4.
export function monitoringPercentage(subtotal: number, maxScore: number = CANONICAL_MAX_SCORE): number {
  if (!Number.isFinite(subtotal) || !Number.isFinite(maxScore) || maxScore <= 0) {
    return 0;
  }
  return Math.round((subtotal / maxScore) * 100);
}

/**
 * Harmonized adjectival rating badge classes across the evaluation workspace.
 */
export function getAdjectivalRatingClasses(rating: string | undefined): string {
  switch (rating) {
    case 'Very Satisfactory':
      return 'bg-success-soft text-success border-success/30';
    case 'Satisfactory':
      return 'bg-info-soft text-info border-info/30';
    case 'Needs Improvement':
      return 'bg-warning-soft text-warning border-warning/30';
    case 'Poor':
    case 'Unsatisfactory':
      return 'bg-destructive-soft text-destructive border-destructive/30';
    default:
      return 'bg-surface-subtle text-text-muted border-border';
  }
}

// Strip raw chunk-id tokens from narrative / justification strings. Falls
// back to the input unchanged when there is nothing to clean.
export function cleanJustification(text: string | null | undefined): string {
  if (!text) return '';
  let cleaned = text;
  for (const pattern of CHUNK_ID_PATTERNS) {
    cleaned = cleaned.replace(pattern, ' ');
  }
  return cleaned
    .replace(/\s{2,}/g, ' ')
    .replace(/\s+([,.;:!?])/g, '$1')
    .trim();
}

// Format raw quoted SLM evidence: parses JSON string arrays (e.g. ["item 1", "item 2"]),
// unescapes literal \n and quotes, and cleans RAG chunk tokens.
export function formatEvidenceText(raw: string | null | undefined): string {
  if (!raw) return '';
  let text = raw.trim();

  // Parse JSON-serialized string arrays if present
  if (text.startsWith('[') && text.endsWith(']')) {
    try {
      const parsed = JSON.parse(text);
      if (Array.isArray(parsed)) {
        text = parsed
          .map((item) => (typeof item === 'string' ? item : JSON.stringify(item)))
          .join('\n\n');
      }
    } catch {
      // If parsing fails, strip outer bracket artifacts
      text = text.replace(/^\[\s*"?/, '').replace(/"?\s*\]$/, '');
    }
  }

  // Unescape literal escaped newlines and escaped quotes
  text = text.replace(/\\n/g, '\n').replace(/\\r/g, '').replace(/\\"/g, '"');

  return cleanJustification(text);
}

// Bound narrative length for export. Trims on a word boundary when possible
// and appends an ellipsis if the text was cut.
export function boundNarrative(text: string | null | undefined, maxChars: number): string {
  const cleaned = cleanJustification(text);
  if (!cleaned) return '';
  if (cleaned.length <= maxChars) return cleaned;
  const slice = cleaned.slice(0, maxChars);
  const lastSpace = slice.lastIndexOf(' ');
  const trimmed = lastSpace > maxChars * 0.6 ? slice.slice(0, lastSpace) : slice;
  return `${trimmed.trimEnd()}…`;
}

// Render a canonical 1-4 score, e.g. "3.50/4", with the canonical scale
// label so the PDF never mislabels a value as a percentage.
export function formatCanonicalScore(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return `${formatScore(value)}/4`;
}

export function formatMonitoringPercent(subtotal: number, maxScore: number = CANONICAL_MAX_SCORE): string {
  return `${monitoringPercentage(subtotal, maxScore)}%`;
}

// Format a value that is already on the 0-100 monitoring scale. Used
// for the server's `synthesized_score`, which is computed against
// `(subtotal / 4) * 100` and therefore arrives as a percentage rather
// than a 1-4 score. We never coerce a percentage back to a /4 label.
export function formatPercentValue(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return `${formatScore(value)}%`;
}

// Derive the canonical 1-4 and 0-100 display values for the overall
// scorecard header. This is the single source of truth for the rules:
//
//   * The canonical 1-4 score comes from the persisted
//     `overall_score`. It is NEVER substituted with `synthesized_score`,
//     which is a 0-100 monitoring percentage and would be misleading
//     with a `/4` label.
//   * The monitoring value is always a percentage. We prefer the
//     percentage derived from the canonical 1-4 score, and only fall
//     back to the server's precomputed `synthesized_score` (which is
//     also a percentage) when the canonical score is missing.
//
// Used by `Scorecard.tsx` so the UI and the PDF banner stay in sync.
export interface OverallScoreDisplay {
  /** Canonical 1-4 score, rendered as `<n>/4`. */
  canonicalText: string;
  /** 0-100 monitoring value, rendered as `<n>%`. */
  monitoringText: string;
  /** True when the canonical 1-4 score is available. */
  hasCanonical: boolean;
}

export function overallScoreDisplay(input: {
  overallScore?: number | null;
  synthesizedScore?: number | null;
}): OverallScoreDisplay {
  const { overallScore, synthesizedScore } = input;
  if (typeof overallScore === 'number' && Number.isFinite(overallScore)) {
    return {
      canonicalText: formatCanonicalScore(overallScore),
      monitoringText: `${monitoringPercentage(overallScore, CANONICAL_MAX_SCORE)}%`,
      hasCanonical: true,
    };
  }
  // No canonical 1-4 score: fall back to the server's precomputed
  // percentage, but never label it as a /4 value.
  return {
    canonicalText: '—',
    monitoringText: formatPercentValue(synthesizedScore),
    hasCanonical: false,
  };
}


export function agentDisplayLabel(agentId: string | null | undefined): string {
  switch ((agentId || '').toLowerCase()) {
    case 'sme':
      return 'Subject Matter Expert (SME)';
    case 'coordinator':
      return 'Program Coordinator';
    case 'gad':
      return 'Gender and Development (GAD)';
    case 'itso':
      return 'Innovation and Technology Support Office (ITSO)';
    default:
      return (agentId || 'agent').toUpperCase();
  }
}

export function agentShortLabel(agentId: string | null | undefined): string {
  switch ((agentId || '').toLowerCase()) {
    case 'sme':
      return 'SME';
    case 'coordinator':
      return 'Coordinator';
    case 'gad':
      return 'GAD';
    case 'itso':
      return 'ITSO';
    default:
      return (agentId || 'agent').toUpperCase();
  }
}

// Canonical 1-4 score tier for UI badges. Mirrors the adjectival buckets.
export function scoreTier(score: number | null | undefined): 'strong' | 'moderate' | 'weak' | 'unknown' {
  if (score == null || !Number.isFinite(score)) return 'unknown';
  if (score >= 3) return 'strong';
  if (score >= 2) return 'moderate';
  return 'weak';
}

/**
 * Sort criteria so they are grouped by rubric domain/category and ordered within their group,
 * rather than interleaved/alternating across domains with matching display_order indices.
 */
export function sortCriteriaGrouped(
  criteria: readonly CriterionScoreItem[],
  formPresentation?: EvaluationFormPresentation | null,
): CriterionScoreItem[] {
  if (!criteria || criteria.length <= 1) {
    return criteria ? [...criteria] : [];
  }

  // 1. If dynamic form snapshot presentation is available, use official domain and criterion display order
  if (formPresentation?.domains && formPresentation.domains.length > 0) {
    const criterionDomainMeta = new Map<
      string,
      { domainOrder: number; criterionOrder: number }
    >();

    formPresentation.domains.forEach((domain, domainIndex) => {
      const domainOrder = domain.display_order ?? domainIndex;
      domain.criteria.forEach((crit, critIndex) => {
        const criterionOrder = crit.display_order ?? critIndex;
        if (crit.rubric_criterion_id) {
          criterionDomainMeta.set(crit.rubric_criterion_id, {
            domainOrder,
            criterionOrder,
          });
        }
        if (crit.criterion_code) {
          criterionDomainMeta.set(crit.criterion_code.toUpperCase(), {
            domainOrder,
            criterionOrder,
          });
        }
      });
    });

    return [...criteria].sort((a, b) => {
      const metaA =
        (a.rubric_criterion_id && criterionDomainMeta.get(a.rubric_criterion_id)) ||
        (a.criterion_id && criterionDomainMeta.get(a.criterion_id.toUpperCase()));
      const metaB =
        (b.rubric_criterion_id && criterionDomainMeta.get(b.rubric_criterion_id)) ||
        (b.criterion_id && criterionDomainMeta.get(b.criterion_id.toUpperCase()));

      if (metaA && metaB) {
        if (metaA.domainOrder !== metaB.domainOrder) {
          return metaA.domainOrder - metaB.domainOrder;
        }
        if (metaA.criterionOrder !== metaB.criterionOrder) {
          return metaA.criterionOrder - metaB.criterionOrder;
        }
      } else if (metaA && !metaB) {
        return -1;
      } else if (!metaA && metaB) {
        return 1;
      }

      if (a.display_order != null && b.display_order != null && a.display_order !== b.display_order) {
        return a.display_order - b.display_order;
      }
      return a.criterion_id.localeCompare(b.criterion_id, undefined, {
        numeric: true,
      });
    });
  }

  // 2. Fallback when form presentation is not provided (e.g. test mocks, legacy):
  // Group by category/domain prefix (e.g. "OP" from "OP-01", "A" from "A-01") preserving
  // original domain appearance order from the backend.
  const extractPrefix = (criterion: CriterionScoreItem): string => {
    const id = criterion.criterion_id || '';
    const match = id.match(/^([A-Za-z]+)/);
    if (match) return match[1].toUpperCase();
    return id.replace(/[-_]?\d+$/, '').toUpperCase() || id;
  };

  const groupFirstSeen = new Map<string, number>();
  criteria.forEach((criterion, idx) => {
    const prefix = extractPrefix(criterion);
    if (!groupFirstSeen.has(prefix)) {
      groupFirstSeen.set(prefix, idx);
    }
  });

  return [...criteria].sort((a, b) => {
    const prefixA = extractPrefix(a);
    const prefixB = extractPrefix(b);

    if (prefixA !== prefixB) {
      const orderA = groupFirstSeen.get(prefixA) ?? 0;
      const orderB = groupFirstSeen.get(prefixB) ?? 0;
      return orderA - orderB;
    }

    if (a.display_order != null && b.display_order != null && a.display_order !== b.display_order) {
      return a.display_order - b.display_order;
    }

    return a.criterion_id.localeCompare(b.criterion_id, undefined, {
      numeric: true,
    });
  });
}
