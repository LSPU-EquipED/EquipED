export type KnowledgeSourceKind = 'rubric' | 'syllabus' | 'curriculum' | 'policy';
export type KnowledgeSourceRole = 'reference' | 'review-topic';

export type KnowledgeConsumer = {
  id: string;
  label: string;
  detail: string;
};

export type KnowledgeSource = {
  id: string;
  kind: KnowledgeSourceKind;
  title: string;
  detail: string;
  scope: string;
  evidence: string;
  role: KnowledgeSourceRole;
  referenceContext: string;
  consumers: string[];
};

export const knowledgeConsumers: KnowledgeConsumer[] = [
  {
    id: 'sme',
    label: 'SME review',
    detail: 'Content accuracy and instructional alignment',
  },
  {
    id: 'coordinator',
    label: 'Coordinator review',
    detail: 'Curriculum and syllabus mapping',
  },
  {
    id: 'gad',
    label: 'GAD review',
    detail: 'Gender responsiveness guidelines',
  },
  {
    id: 'itso',
    label: 'ITSO review',
    detail: 'Intellectual property and citation policy',
  },
  {
    id: 'synthesis',
    label: 'Master synthesis',
    detail: 'Synthesized scores and monitoring review',
  },
];

export const knowledgeSources: KnowledgeSource[] = [
  {
    id: 'rubrics',
    kind: 'rubric',
    title: 'Published rubric sets',
    detail: 'Reference scoring criteria and descriptors across specialist dimensions.',
    scope: 'SME, Coordinator, GAD, and ITSO',
    evidence: 'Reference criteria across 4 dimensions',
    role: 'reference',
    referenceContext: 'Curated reference criteria',
    consumers: ['sme', 'coordinator', 'gad', 'itso', 'synthesis'],
  },
  {
    id: 'syllabus',
    kind: 'syllabus',
    title: 'Course syllabi',
    detail: 'Course outcomes, topic sequences, and learning activities.',
    scope: 'Course and program scoped',
    evidence: 'Course syllabus reference',
    role: 'reference',
    referenceContext: 'Curated reference document',
    consumers: ['coordinator', 'synthesis'],
  },
  {
    id: 'curriculum',
    kind: 'curriculum',
    title: 'Degree curricula',
    detail: 'Program roadmaps that connect courses to institutional competencies.',
    scope: 'BSCS and BSInfoTech',
    evidence: 'Program curriculum structure',
    role: 'review-topic',
    referenceContext: 'Pending curriculum review',
    consumers: ['coordinator', 'synthesis'],
  },
  {
    id: 'policy',
    kind: 'policy',
    title: 'Institutional policies',
    detail: 'Local policy guidance for intellectual property, privacy, and compliance.',
    scope: 'ITSO policy areas',
    evidence: 'Policy clauses and guidelines',
    role: 'reference',
    referenceContext: 'Curated reference document',
    consumers: ['itso'],
  },
];

export const knowledgeSourceKinds: Array<{
  value: 'all' | KnowledgeSourceKind;
  label: string;
}> = [
  { value: 'all', label: 'All sources' },
  { value: 'rubric', label: 'Rubrics' },
  { value: 'syllabus', label: 'Syllabi' },
  { value: 'curriculum', label: 'Curricula' },
  { value: 'policy', label: 'Policies' },
];
