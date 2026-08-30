import type {
  CountBandConfig,
  CurriculumAlignmentConfig,
  LlmRubricGuidanceConfig,
  RatioBandConfig,
  StrategyConfig,
} from './types';

export const DEFAULT_LLM_CONFIG: LlmRubricGuidanceConfig = {
  strategy: 'llm_rubric_guidance',
  guidance: '',
  level_descriptors: null,
};

export const DEFAULT_COUNT_MIN_CONFIG: CountBandConfig = {
  strategy: 'count_band',
  mode: 'minimum_count',
  threshold_4: 4,
  threshold_3: 3,
  threshold_2: 2,
};

export const DEFAULT_COUNT_MAX_CONFIG: CountBandConfig = {
  strategy: 'count_band',
  mode: 'maximum_count',
  threshold_4: 0,
  threshold_3: 1,
  threshold_2: 3,
};

export const DEFAULT_RATIO_COVERAGE_CONFIG: RatioBandConfig = {
  strategy: 'ratio_band',
  mode: 'coverage_percentage',
  threshold_4: 90.0,
  threshold_3: 75.0,
  threshold_2: 60.0,
  short_sample: null,
};

export const DEFAULT_RATIO_DIFF_CONFIG: RatioBandConfig = {
  strategy: 'ratio_band',
  mode: 'absolute_difference',
  threshold_4: 2.0,
  threshold_3: 5.0,
  threshold_2: 10.0,
  short_sample: null,
};

export const DEFAULT_CURRICULUM_CONFIG: CurriculumAlignmentConfig = {
  strategy: 'curriculum_alignment',
  guidance: '',
};

export function getDefaultStrategyConfigForAgent(agentId: string): StrategyConfig {
  switch (agentId) {
    case 'sme':
      return DEFAULT_LLM_CONFIG;
    case 'gad':
      return DEFAULT_COUNT_MAX_CONFIG;
    case 'itso':
      return DEFAULT_LLM_CONFIG;
    case 'coordinator':
      return DEFAULT_CURRICULUM_CONFIG;
    default:
      return DEFAULT_LLM_CONFIG;
  }
}
