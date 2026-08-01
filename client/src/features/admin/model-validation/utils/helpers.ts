import type {
  ModelValidationAgentCriteria,
  ModelValidationCriterionScore,
  ModelValidationItem,
} from '../types';

export const terminalStatuses = new Set(['COMPLETED', 'FAILED']);

export const criterionKey = (agentId: string, criterionId: string) => `${agentId}:${criterionId}`;

/**
 * True when every criterion of every active agent group returned by the
 * criterion catalog has an integer score in the 1–4 scale. Validity follows
 * the catalog (SME/GAD/ITSO for curriculum-retired runs), never a fixed
 * agent count, so missing groups can't block or unblock submission.
 */
export function areAllCriterionScoresComplete(
  criterionDefinitions: ModelValidationAgentCriteria[],
  expectedScores: Record<string, string>,
): boolean {
  if (criterionDefinitions.length === 0) {
    return false;
  }

  return criterionDefinitions.every(
    (agent) =>
      agent.criteria.length > 0 &&
      agent.criteria.every((criterion) => {
        const score = Number(expectedScores[criterionKey(agent.agent_id, criterion.criterion_id)]);
        return Number.isInteger(score) && score >= 1 && score <= 4;
      }),
  );
}

export const validationAgents = [
  { id: 'sme', label: 'Subject Matter Expert' },
  { id: 'coordinator', label: 'Program Coordinator' },
  { id: 'gad', label: 'GAD Evaluator' },
  { id: 'itso', label: 'IT Security Officer' },
] as const;

export type ValidationAgentId = (typeof validationAgents)[number]['id'];

export const agentLabel = (id: string) =>
  validationAgents.find((agent) => agent.id === id)?.label ?? id.toUpperCase();

export const HISTORY_COLSPAN = 10;

export function statusClass(status: ModelValidationItem['status']) {
  if (status === 'COMPLETED') return 'bg-[#3b963e] text-white';
  if (status === 'FAILED') return 'bg-[#b91c1c] text-white';
  if (status === 'EVALUATING' || status === 'SYNTHESIZING') return 'bg-[#1b3b87] text-white';
  return 'bg-[#f2c811] text-slate-900';
}

export type GroupedCriteria = {
  agentId: string;
  agentName: string;
  criteria: ModelValidationCriterionScore[];
};

export function groupCriteriaByAgent(scores: ModelValidationCriterionScore[]): GroupedCriteria[] {
  const buckets = new Map<string, ModelValidationCriterionScore[]>();
  for (const score of scores) {
    const list = buckets.get(score.agent_id) ?? [];
    list.push(score);
    buckets.set(score.agent_id, list);
  }
  const ordered: GroupedCriteria[] = [];
  for (const agent of validationAgents) {
    const items = buckets.get(agent.id);
    if (items && items.length > 0) {
      ordered.push({
        agentId: agent.id,
        agentName: agent.label,
        criteria: [...items].sort((a, b) => a.criterion_id.localeCompare(b.criterion_id)),
      });
      buckets.delete(agent.id);
    }
  }
  for (const [agentId, criteria] of buckets.entries()) {
    ordered.push({
      agentId,
      agentName: agentLabel(agentId),
      criteria: [...criteria].sort((a, b) => a.criterion_id.localeCompare(b.criterion_id)),
    });
  }
  return ordered;
}

export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}
