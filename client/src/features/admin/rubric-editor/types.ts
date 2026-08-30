export type ScoringStrategy =
  | 'llm_rubric_guidance'
  | 'count_band'
  | 'ratio_band'
  | 'curriculum_alignment';

export type LlmScoreDescriptor = {
  score: number;
  descriptor: string;
};

export type LlmRubricGuidanceConfig = {
  strategy: 'llm_rubric_guidance';
  guidance: string;
  level_descriptors?: LlmScoreDescriptor[] | null;
};

export type CountBandMode = 'minimum_count' | 'maximum_count';

export type CountBandConfig = {
  strategy: 'count_band';
  mode: CountBandMode;
  threshold_4: number;
  threshold_3: number;
  threshold_2: number;
};

export type ShortSampleConfig = {
  min_units: number;
  max_issues_4: number;
  max_issues_3: number;
  max_issues_2: number;
};

export type RatioBandMode = 'coverage_percentage' | 'absolute_difference';

export type RatioBandConfig = {
  strategy: 'ratio_band';
  mode: RatioBandMode;
  threshold_4: number;
  threshold_3: number;
  threshold_2: number;
  short_sample?: ShortSampleConfig | null;
};

export type CurriculumAlignmentConfig = {
  strategy: 'curriculum_alignment';
  guidance?: string | null;
};

export type StrategyConfig =
  | LlmRubricGuidanceConfig
  | CountBandConfig
  | RatioBandConfig
  | CurriculumAlignmentConfig;

export type RubricCriterion = {
  rubric_criterion_id: string;
  rubric_domain_id?: string | null;
  criterion_code: string;
  title: string;
  description: string;
  scoring_rule?: string | null;
  scoring_strategy?: string | null;
  strategy_config?: StrategyConfig | null;
  display_order: number;
};

export type RubricDomain = {
  rubric_domain_id: string;
  rubric_set_id?: string | null;
  code: string;
  title: string;
  display_order: number;
  criteria: RubricCriterion[];
};

export type RubricRevisionStatus = 'draft' | 'published' | 'retired';

export type RubricSet = {
  rubric_set_id: string;
  agent_id: string;
  name: string;
  version_number: number;
  status: RubricRevisionStatus | string;
  adapter_key?: string | null;
  adapter_version?: number | null;
  published_at?: string | null;
  published_by?: string | null;
  created_at?: string | null;
  created_by?: string | null;
  retired_at?: string | null;
  retired_by?: string | null;
  is_active?: boolean | null;
  domains: RubricDomain[];
};

export type RubricSetListResponse = {
  rubric_sets: RubricSet[];
  activations?: Record<string, string>;
};

export type RubricRevisionsResponse = {
  revisions: RubricSet[];
  active_pointers: Record<string, string>;
};

export type RubricActivationOut = {
  agent_id: string;
  rubric_set_id: string;
  updated_by?: string | null;
  updated_at: string;
};

export type ValidationSeverity = 'error' | 'warning' | 'info';

export type ValidationIssue = {
  path: string;
  code: string;
  message: string;
  severity: ValidationSeverity;
};

export type ValidationReport = {
  is_valid: boolean;
  issues: ValidationIssue[];
  estimated_prompt_chars: number;
  criteria_count: number;
};

export type DomainReorderItem = {
  rubric_domain_id: string;
  criterion_ids: string[];
};

export type RubricReorderRequest = {
  domains: DomainReorderItem[];
};

export type RubricPublishRequest = {
  activate?: boolean;
};

export type RubricDomainCreate = {
  code: string;
  title: string;
};

export type RubricDomainUpdate = {
  code?: string;
  title?: string;
};

export type RubricCriterionCreate = {
  criterion_code: string;
  title: string;
  description: string;
  scoring_rule?: string | null;
  strategy_config: StrategyConfig;
};

export type RubricCriterionUpdate = {
  criterion_code?: string;
  title?: string;
  description?: string;
  scoring_rule?: string | null;
  strategy_config?: StrategyConfig;
};

export type RubricCriterionMoveRequest = {
  destination_domain_id: string;
};

export type CriterionUpdate = {
  description?: string;
  scoring_rule?: string | null;
  title?: string;
  criterion_code?: string;
  strategy_config?: StrategyConfig;
};

export type DomainTitleUpdate = {
  title?: string;
  code?: string;
};

export const AGENT_LABELS: Record<string, string> = {
  sme: 'Subject Matter Expert',
  coordinator: 'Program Coordinator',
  gad: 'GAD',
  itso: 'ITSO',
};

export const AGENT_ORDER = ['sme', 'coordinator', 'gad', 'itso'] as const;
export type AgentId = (typeof AGENT_ORDER)[number];

export const AGENT_STRATEGY_CAPABILITIES: Record<
  string,
  {
    allowedStrategies: ScoringStrategy[];
    allowedCountModes?: CountBandMode[];
    allowedRatioModes?: RatioBandMode[];
    maxCriteria: number;
    description: string;
  }
> = {
  sme: {
    allowedStrategies: ['llm_rubric_guidance', 'count_band', 'ratio_band'],
    allowedCountModes: ['minimum_count'],
    allowedRatioModes: ['coverage_percentage'],
    maxCriteria: 20,
    description:
      'Supports LLM guidance, count thresholds (minimum), and coverage ratios with optional short sample overrides.',
  },
  gad: {
    allowedStrategies: ['count_band', 'ratio_band'],
    allowedCountModes: ['maximum_count'],
    allowedRatioModes: ['absolute_difference'],
    maxCriteria: 10,
    description:
      'Supports maximum adverse instance counts and absolute difference ratio bands for gender representation.',
  },
  itso: {
    allowedStrategies: ['llm_rubric_guidance'],
    maxCriteria: 10,
    description:
      'Supports LLM rubric guidance with evidence extraction for intellectual property and privacy compliance.',
  },
  coordinator: {
    allowedStrategies: ['curriculum_alignment'],
    maxCriteria: 1,
    description: 'Supports exactly 1 criterion for curriculum objective alignment scoring.',
  },
};
