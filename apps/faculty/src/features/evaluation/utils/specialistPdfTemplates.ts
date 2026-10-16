import layouts from '../assets/pdf-templates/layouts.json';
import smeUrl from '../assets/pdf-templates/sme.pdf?url';
import coordinatorUrl from '../assets/pdf-templates/coordinator.pdf?url';
import gadUrl from '../assets/pdf-templates/gad.pdf?url';
import itsoUrl from '../assets/pdf-templates/itso.pdf?url';
import type { CriterionScoreItem, ExportAgentId } from '../types';

export const SPECIALIST_PDF_TEMPLATES = {
  sme: { ...layouts.sme, url: smeUrl },
  coordinator: { ...layouts.coordinator, url: coordinatorUrl },
  gad: { ...layouts.gad, url: gadUrl },
  itso: { ...layouts.itso, url: itsoUrl },
};

// Known equivalent descriptions in the current Coordinator snapshot. Keep these
// explicit: a reused code alone cannot establish that a revised criterion still
// belongs on the printed institutional form.
const COORDINATOR_DESCRIPTION_ALIASES: Readonly<Record<string, string>> = {
  'A-03': 'The material keeps an ongoing record of student progress and allows teacher monitoring.',
  'A-04': 'Positive meaningful feedback and prescriptive intervention guides are provided.',
};

// Prefer saved wording. Pre-snapshot results contain only a title and code;
// require both canonical values before mapping those older results.
function normalizeCriterion(text: string): string {
  return text.normalize('NFKC').toLowerCase().replace(/[\p{P}\p{Z}\s]+/gu, '');
}

export function matchTemplateCriteria(agent: ExportAgentId, criteria: readonly CriterionScoreItem[]) {
  const rows = SPECIALIST_PDF_TEMPLATES[agent].rows;
  const matches = rows.map((row) => {
    const expected = normalizeCriterion(row.text);
    const candidates = criteria.filter((criterion) => {
      if (criterion.description?.trim()) {
        const description = normalizeCriterion(criterion.description);
        const alias = agent === 'coordinator' && COORDINATOR_DESCRIPTION_ALIASES[row.criterionCode];
        return description === expected
          || (alias && criterion.criterion_id === row.criterionCode
            && normalizeCriterion(criterion.criterion_text) === normalizeCriterion(row.title)
            && description === normalizeCriterion(alias));
      }
      return normalizeCriterion(criterion.criterion_text) === expected
        || (criterion.criterion_id === row.criterionCode
          && normalizeCriterion(criterion.criterion_text) === normalizeCriterion(row.title));
    });
    const candidate = candidates.length === 1 ? candidates[0] : null;
    // Ungrounded is an evidence flag, not an absent score. Preserve the stored
    // advisory score and require human review in the form's comments instead.
    return candidate && Number.isInteger(candidate.score)
      && candidate.score >= 1 && candidate.score <= 4 ? candidate : null;
  });
  // Ambiguous duplicate input or a single input matching multiple printed rows
  // must not silently produce a completed institutional form.
  const uniqueMatches = matches.map((match) =>
    match && matches.filter((other) => other === match).length === 1 ? match : null,
  );
  const complete = criteria.length === rows.length && uniqueMatches.every(Boolean);
  return { matches: uniqueMatches, complete };
}
