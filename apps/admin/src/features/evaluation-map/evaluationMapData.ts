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
  // ── Column 1: References & Data Input (x: 20, 8 nodes) ────────────────
  { id: 'slm', kind: 'reference', title: 'SLM document', detail: 'Direct input; never embedded.', x: 20, y: 52 },
  { id: 'rubrics', kind: 'reference', title: 'Institutional rubrics', detail: 'Published 1–4 criteria & rules.', x: 20, y: 128 },
  { id: 'program', kind: 'reference', title: 'Confirmed program', detail: 'Canonical BSCS or BSInfoTech.', x: 20, y: 204 },
  { id: 'roadmap', kind: 'reference', title: 'Program roadmap', detail: 'Placement, stack & competencies.', x: 20, y: 280 },
  { id: 'policies', kind: 'reference', title: 'Local policy library', detail: 'IP, privacy & academic clauses.', x: 20, y: 356 },
  { id: 'citations', kind: 'reference', title: 'Citation signals', detail: 'Local bibliography & DOI patterns.', x: 20, y: 432 },
  { id: 'syllabus', kind: 'reference', title: 'Selected syllabus', detail: 'Course contents from syllabus.', x: 20, y: 508 },
  { id: 'job', kind: 'reference', title: 'Job & ownership', detail: 'Faculty, program & partial-state.', x: 20, y: 584 },

  // ── Column 2: Specialist Agent Processes (x: 370, 9 nodes) ───────────
  { id: 'prepare', kind: 'process', title: 'Prepare context', detail: 'Parse SLM & freeze shared context.', x: 370, y: 48 },
  { id: 'sme', kind: 'process', title: 'SME content engine', detail: 'Evidence extraction & domain scoring.', x: 370, y: 116 },
  { id: 'gad', kind: 'process', title: 'GAD grounded review', detail: 'Evaluate gender responsiveness.', x: 370, y: 184 },
  { id: 'itso', kind: 'process', title: 'ITSO evidence review', detail: 'Local prechecks & policy retrieval.', x: 370, y: 252 },
  { id: 'coordinator', kind: 'process', title: 'Coordinator review', detail: 'Curriculum-grounded review.', x: 370, y: 320, status: 'Skipped in partial flow' },
  { id: 'parallel', kind: 'process', title: 'Parallel specialist run', detail: 'Supervisor runs agents in parallel.', x: 370, y: 388 },
  { id: 'synthesize', kind: 'process', title: 'Synthesize & persist', detail: 'Aggregate scores, flags & provenance.', x: 370, y: 456 },
  { id: 'align', kind: 'process', title: 'Compare SLM topics', detail: 'Compare against syllabus contents.', x: 370, y: 524 },
  { id: 'publish', kind: 'process', title: 'Assemble artifact', detail: 'Format persisted results.', x: 370, y: 592 },

  // ── Column 3: Accredited Review Outputs (x: 720, 8 nodes) ─────────────
  { id: 'sme-output', kind: 'output', title: 'SME scorecard', detail: 'Content quality scores & evidence.', x: 720, y: 52 },
  { id: 'gad-output', kind: 'output', title: 'GAD review', detail: 'Gender sensitivity criteria & flags.', x: 720, y: 128 },
  { id: 'itso-output', kind: 'output', title: 'ITSO review', detail: 'IP & citation findings.', x: 720, y: 204 },
  { id: 'coordinator-output', kind: 'output', title: 'Coordinator review', detail: 'Curriculum alignment result.', x: 720, y: 280, status: 'Unavailable in partial flow' },
  { id: 'scorecard', kind: 'output', title: 'Overall scorecard', detail: 'Layer 4 weighted synthesis.', x: 720, y: 356 },
  { id: 'report', kind: 'output', title: 'Evaluation PDF report', detail: 'Privacy-safe advisory report.', x: 720, y: 432 },
  { id: 'matrix', kind: 'output', title: 'Monitoring matrix', detail: 'Institutional compliance matrix.', x: 720, y: 508 },
  { id: 'syllabus-output', kind: 'output', title: 'Syllabus report', detail: 'Independent topic review.', x: 720, y: 584 },
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
