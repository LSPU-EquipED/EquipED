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

export function isPartialResult(partial: boolean | null | undefined): boolean {
  return Boolean(partial);
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
export function getCriterionCategory(criterion: {
  criterion_id: string;
  criterion_text: string;
  category?: string | null;
}): string {
  if (criterion.category) return criterion.category;

  const text = criterion.criterion_text.toLowerCase();
  const id = criterion.criterion_id.toUpperCase();

  if (id.startsWith('GAD') || text.includes('gender') || text.includes('inclusive') || text.includes('stereotype')) {
    if (text.includes('language') || text.includes('term') || text.includes('pronoun') || text.includes('non-sexist')) {
      return 'Gender-Fair Language & Principles';
    }
    if (text.includes('role') || text.includes('representation') || text.includes('career') || text.includes('illustration') || text.includes('character')) {
      return 'Representation & Social Roles';
    }
    if (text.includes('exercise') || text.includes('task') || text.includes('activity') || text.includes('assessment')) {
      return 'Equitable Instructional Activities';
    }
    return 'Gender Sensitivity & Inclusivity';
  }

  if (id.startsWith('SME') || text.includes('content') || text.includes('accuracy') || text.includes('bloom') || text.includes('taxonomy')) {
    if (text.includes('exercise') || text.includes('assessment') || text.includes('exam') || text.includes('quiz') || text.includes('rubric') || text.includes('formative')) {
      return 'Assessment & Formative Exercises';
    }
    if (text.includes('topic') || text.includes('depth') || text.includes('accuracy') || text.includes('rigor') || text.includes('concept')) {
      return 'Discipline Depth & Rigor';
    }
    return 'Instructional Clarity & Accuracy';
  }

  if (id.startsWith('COORD') || text.includes('syllabus') || text.includes('curriculum') || text.includes('prerequisite')) {
    if (text.includes('syllabus') || text.includes('ilo') || text.includes('outcome')) {
      return 'Syllabus Topic & Outcome Coverage';
    }
    return 'Curriculum Roadmap Alignment';
  }

  if (id.startsWith('ITSO') || text.includes('citation') || text.includes('copyright') || text.includes('patent') || text.includes('ip')) {
    if (text.includes('citation') || text.includes('reference') || text.includes('source') || text.includes('attribution')) {
      return 'Citation & Attribution Standards';
    }
    return 'Intellectual Property & Copyright';
  }

  return 'Core Quality Standards';
}
