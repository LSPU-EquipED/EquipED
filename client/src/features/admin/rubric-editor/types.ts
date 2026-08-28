export type RubricCriterion = {
  rubric_criterion_id: string;
  criterion_code: string;
  title: string;
  description: string;
  scoring_rule: string | null;
  display_order: number;
};

export type RubricDomain = {
  rubric_domain_id: string;
  code: string;
  title: string;
  display_order: number;
  criteria: RubricCriterion[];
};

export type RubricSet = {
  rubric_set_id: string;
  agent_id: string;
  name: string;
  version_number: number;
  status: string;
  domains: RubricDomain[];
};

export type RubricSetListResponse = {
  rubric_sets: RubricSet[];
};

export type CriterionUpdate = {
  description: string;
  scoring_rule: string | null;
};

export type DomainTitleUpdate = {
  title: string;
};

export const AGENT_LABELS: Record<string, string> = {
  sme: 'Subject Matter Expert',
  coordinator: 'Program Coordinator',
  gad: 'GAD',
  itso: 'ITSO',
};
