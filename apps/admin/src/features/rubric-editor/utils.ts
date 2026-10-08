import {
  AGENT_STRATEGY_CAPABILITIES,
  getAgentStrategyCapabilities,
  type CountBandConfig,
  type CurriculumAlignmentConfig,
  type LlmRubricGuidanceConfig,
  type RatioBandConfig,
  type ScoringStrategy,
  type StrategyConfig,
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

export function getRequiredStrategy(
  agentId: string,
  criterionCode: string,
  adapterVersion?: number | null,
): ScoringStrategy | undefined {
  return getAgentStrategyCapabilities(agentId, adapterVersion)?.requiredStrategiesByCriterion?.[
    criterionCode.trim().toUpperCase()
  ];
}

export function getDefaultStrategyConfig(
  strategy: ScoringStrategy,
  agentId: string,
): StrategyConfig {
  const capabilities = AGENT_STRATEGY_CAPABILITIES[agentId];
  switch (strategy) {
    case 'llm_rubric_guidance':
      return DEFAULT_LLM_CONFIG;
    case 'count_band':
      return capabilities?.allowedCountModes?.includes('maximum_count')
        ? DEFAULT_COUNT_MAX_CONFIG
        : DEFAULT_COUNT_MIN_CONFIG;
    case 'ratio_band':
      return capabilities?.allowedRatioModes?.includes('absolute_difference')
        ? DEFAULT_RATIO_DIFF_CONFIG
        : DEFAULT_RATIO_COVERAGE_CONFIG;
    case 'curriculum_alignment':
      return DEFAULT_CURRICULUM_CONFIG;
    case 'objective_gauging':
      return { strategy: 'objective_gauging' };
  }
}

export function normalizeRequiredStrategyConfig(
  agentId: string,
  criterionCode: string,
  config: StrategyConfig,
  adapterVersion?: number | null,
): StrategyConfig {
  const requiredStrategy = getRequiredStrategy(agentId, criterionCode, adapterVersion);
  return requiredStrategy && config.strategy !== requiredStrategy
    ? getDefaultStrategyConfig(requiredStrategy, agentId)
    : config;
}

export function getDefaultStrategyConfigForAgent(agentId: string, adapterVersion?: number | null): StrategyConfig {
  switch (agentId) {
    case 'gad':
      return getDefaultStrategyConfig('count_band', agentId);
    case 'coordinator':
      return getDefaultStrategyConfig(adapterVersion === 3 ? 'llm_rubric_guidance' : 'curriculum_alignment', agentId);
    default:
      return getDefaultStrategyConfig('llm_rubric_guidance', agentId);
  }
}
