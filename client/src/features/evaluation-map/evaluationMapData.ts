export type MapNodeKind = 'reference' | 'process' | 'output';

export type EvaluationMapNode = {
  id: string;
  kind: MapNodeKind;
  title: string;
  detail: string;
  x: number;
  y: number;
  status?: string;
};

export type EvaluationMapEdge = {
  from: string;
  to: string;
};

export const evaluationMapNodes: EvaluationMapNode[] = [
  { id: 'slm', kind: 'reference', title: 'SLM document', detail: 'Direct, owner-scoped evaluation input; never embedded.', x: 24, y: 86 },
  { id: 'rubrics', kind: 'reference', title: 'Institutional rubrics', detail: 'Versioned criteria and 1–4 scoring rules for each domain.', x: 24, y: 190 },
  { id: 'program', kind: 'reference', title: 'Confirmed program', detail: 'Faculty-confirmed BSIT, BSCS, or BSIS context.', x: 24, y: 294 },
  { id: 'roadmap', kind: 'reference', title: 'Program roadmap', detail: 'Course placement, tech stack, and competency stage.', x: 24, y: 398 },
  { id: 'policies', kind: 'reference', title: 'Local policy library', detail: 'Residency-gated IP, privacy, and academic-rights clauses.', x: 24, y: 502 },
  { id: 'citations', kind: 'reference', title: 'SLM citation signals', detail: 'Local bibliography, in-text citation, and DOI patterns.', x: 24, y: 606 },
  { id: 'syllabus', kind: 'reference', title: 'Selected syllabus', detail: 'Retrieval-ready Course Contents from one shared syllabus.', x: 24, y: 710 },
  { id: 'job', kind: 'reference', title: 'Job & ownership data', detail: 'Lifecycle, faculty, program, document, and partial-state data.', x: 24, y: 814 },

  { id: 'prepare', kind: 'process', title: 'Prepare evaluation context', detail: 'Parse SLM, confirm metadata, and freeze shared read-only context.', x: 414, y: 74 },
  { id: 'sme', kind: 'process', title: 'SME engine scoring', detail: 'Extract evidence baskets, deduplicate facts, then apply code-owned scoring.', x: 414, y: 178 },
  { id: 'gad', kind: 'process', title: 'GAD grounded review', detail: 'Evaluate gender responsiveness with rubric-grounded evidence.', x: 414, y: 282 },
  { id: 'itso', kind: 'process', title: 'ITSO evidence review', detail: 'Run deterministic local prechecks and bounded policy retrieval.', x: 414, y: 386 },
  { id: 'coordinator', kind: 'process', title: 'Coordinator review', detail: 'Curriculum-grounded review enriched by confirmed roadmap facts.', x: 414, y: 490, status: 'Skipped in current partial flow' },
  { id: 'parallel', kind: 'process', title: 'Parallel specialist run', detail: 'Supervisor runs available agents in parallel and preserves attribution.', x: 414, y: 594 },
  { id: 'synthesize', kind: 'process', title: 'Synthesize & persist', detail: 'Normalize available weights, aggregate scores, flags, and provenance.', x: 414, y: 698 },
  { id: 'align', kind: 'process', title: 'Compare SLM topics', detail: 'Extract substantive topics and compare against syllabus Course Contents.', x: 414, y: 802 },
  { id: 'publish', kind: 'process', title: 'Assemble review artifact', detail: 'Format persisted results without exposing raw chunk identifiers.', x: 414, y: 906 },

  { id: 'sme-output', kind: 'output', title: 'SME scorecard', detail: 'Content quality scores, evidence, flags, and rationale.', x: 804, y: 42 },
  { id: 'gad-output', kind: 'output', title: 'GAD review', detail: 'Gender sensitivity criteria, evidence, and advisory flags.', x: 804, y: 142 },
  { id: 'itso-output', kind: 'output', title: 'ITSO review', detail: 'IP and citation findings with bounded evidence state.', x: 804, y: 242 },
  { id: 'coordinator-output', kind: 'output', title: 'Coordinator review', detail: 'Curriculum alignment result when valid curriculum context exists.', x: 804, y: 342, status: 'Unavailable in current partial flow' },
  { id: 'scorecard', kind: 'output', title: 'Overall scorecard', detail: 'Weighted domain result; successful weights normalize when partial.', x: 804, y: 442 },
  { id: 'report', kind: 'output', title: 'Evaluation PDF report', detail: 'Privacy-safe advisory report with honest partial-state labels.', x: 804, y: 542 },
  { id: 'matrix', kind: 'output', title: 'Monitoring matrix', detail: 'Admin oversight of status, scores, flags, and feedback state.', x: 804, y: 642 },
  { id: 'syllabus-output', kind: 'output', title: 'Syllabus alignment report', detail: 'Independent aligned/outside-syllabus topic review.', x: 804, y: 742 },
];

export const evaluationMapEdges: EvaluationMapEdge[] = [
  { from: 'slm', to: 'prepare' },
  { from: 'rubrics', to: 'prepare' },
  { from: 'program', to: 'prepare' },
  { from: 'prepare', to: 'sme' },
  { from: 'prepare', to: 'gad' },
  { from: 'prepare', to: 'itso' },
  { from: 'prepare', to: 'coordinator' },
  { from: 'rubrics', to: 'sme' },
  { from: 'rubrics', to: 'gad' },
  { from: 'rubrics', to: 'itso' },
  { from: 'rubrics', to: 'coordinator' },
  { from: 'policies', to: 'itso' },
  { from: 'citations', to: 'itso' },
  { from: 'program', to: 'coordinator' },
  { from: 'roadmap', to: 'coordinator' },
  { from: 'sme', to: 'sme-output' },
  { from: 'gad', to: 'gad-output' },
  { from: 'itso', to: 'itso-output' },
  { from: 'coordinator', to: 'coordinator-output' },
  { from: 'sme', to: 'parallel' },
  { from: 'gad', to: 'parallel' },
  { from: 'itso', to: 'parallel' },
  { from: 'parallel', to: 'synthesize' },
  { from: 'synthesize', to: 'scorecard' },
  { from: 'synthesize', to: 'publish' },
  { from: 'publish', to: 'report' },
  { from: 'job', to: 'publish' },
  { from: 'synthesize', to: 'matrix' },
  { from: 'job', to: 'matrix' },
  { from: 'slm', to: 'align' },
  { from: 'syllabus', to: 'align' },
  { from: 'align', to: 'syllabus-output' },
];

export function getActiveMapIds(outputId: string) {
  const activeNodes = new Set<string>([outputId]);
  const activeEdges = new Set<string>();
  const pending = [outputId];

  while (pending.length > 0) {
    const current = pending.pop();
    for (const edge of evaluationMapEdges) {
      if (edge.to !== current) continue;
      const edgeId = `${edge.from}:${edge.to}`;
      activeEdges.add(edgeId);
      if (!activeNodes.has(edge.from)) {
        activeNodes.add(edge.from);
        pending.push(edge.from);
      }
    }
  }

  return { activeNodes, activeEdges };
}
