import {
  AGENT_STRATEGY_CAPABILITIES,
  type CountBandMode,
  type LlmScoreDescriptor,
  type RatioBandMode,
  type ScoringStrategy,
  type ShortSampleConfig,
  type StrategyConfig,
} from '../types';
import {
  DEFAULT_COUNT_MAX_CONFIG,
  DEFAULT_COUNT_MIN_CONFIG,
  DEFAULT_CURRICULUM_CONFIG,
  DEFAULT_LLM_CONFIG,
  DEFAULT_RATIO_COVERAGE_CONFIG,
  DEFAULT_RATIO_DIFF_CONFIG,
} from '../utils';

interface StrategyConfigEditorProps {
  agentId: string;
  value: StrategyConfig;
  onChange: (config: StrategyConfig) => void;
  disabled?: boolean;
}

export function StrategyConfigEditor({
  agentId,
  value,
  onChange,
  disabled = false,
}: StrategyConfigEditorProps) {
  const agentCaps = AGENT_STRATEGY_CAPABILITIES[agentId] ?? {
    allowedStrategies: ['llm_rubric_guidance'],
    maxCriteria: 20,
    description: '',
  };

  const hasDescriptors =
    value.strategy === 'llm_rubric_guidance' && Boolean(value.level_descriptors?.length);

  const hasShortSample = value.strategy === 'ratio_band' && Boolean(value.short_sample);

  const handleStrategyChange = (newStrategy: ScoringStrategy) => {
    switch (newStrategy) {
      case 'llm_rubric_guidance':
        onChange(DEFAULT_LLM_CONFIG);
        break;
      case 'count_band':
        onChange(
          agentCaps.allowedCountModes?.includes('maximum_count')
            ? DEFAULT_COUNT_MAX_CONFIG
            : DEFAULT_COUNT_MIN_CONFIG,
        );
        break;
      case 'ratio_band':
        onChange(
          agentCaps.allowedRatioModes?.includes('absolute_difference')
            ? DEFAULT_RATIO_DIFF_CONFIG
            : DEFAULT_RATIO_COVERAGE_CONFIG,
        );
        break;
      case 'curriculum_alignment':
        onChange(DEFAULT_CURRICULUM_CONFIG);
        break;
    }
  };

  return (
    <div className="grid gap-4 rounded-sm border border-slate-200 bg-slate-50/50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3">
        <div>
          <label
            htmlFor="strategy-select"
            className="text-xs font-bold uppercase tracking-wider text-slate-800"
          >
            Scoring Strategy
          </label>
          <p className="text-[11px] text-slate-500 font-medium">
            Evaluation algorithm and measurement shape for this criterion.
          </p>
        </div>

        {agentCaps.allowedStrategies.length > 1 ? (
          <select
            id="strategy-select"
            value={value.strategy}
            onChange={(e) => handleStrategyChange(e.target.value as ScoringStrategy)}
            disabled={disabled}
            className="h-8 rounded-sm border border-slate-300 bg-white px-2 text-xs font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] disabled:opacity-60"
          >
            {agentCaps.allowedStrategies.map((strat) => (
              <option key={strat} value={strat}>
                {strat === 'llm_rubric_guidance' && 'LLM Rubric Guidance'}
                {strat === 'count_band' && 'Count Band (Discrete Count)'}
                {strat === 'ratio_band' && 'Ratio Band (Percentage / Difference)'}
                {strat === 'curriculum_alignment' && 'Curriculum Alignment'}
              </option>
            ))}
          </select>
        ) : (
          <span className="rounded-sm bg-slate-200 px-2 py-1 text-xs font-bold uppercase tracking-wider text-slate-700">
            {value.strategy === 'curriculum_alignment'
              ? 'Curriculum Alignment'
              : value.strategy === 'llm_rubric_guidance'
                ? 'LLM Rubric Guidance'
                : value.strategy}
          </span>
        )}
      </div>

      {/* LLM Rubric Guidance Form */}
      {value.strategy === 'llm_rubric_guidance' && (
        <div className="grid gap-4">
          <div>
            <label
              htmlFor="llm-guidance"
              className="block text-xs font-bold uppercase tracking-wider text-slate-700"
            >
              Evaluation Guidance <span className="text-[#b91c1c]">*</span>
            </label>
            <p className="text-[11px] text-slate-500 mb-1">
              Instructions provided to the LLM evaluator to assess score and extract evidence.
            </p>
            <textarea
              id="llm-guidance"
              rows={4}
              value={value.guidance}
              onChange={(e) => onChange({ ...value, guidance: e.target.value })}
              disabled={disabled}
              placeholder="Enter guidance for the LLM evaluating this criterion..."
              className="w-full rounded-sm border border-slate-300 bg-white p-2.5 text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] disabled:opacity-60"
            />
          </div>

          <div className="grid gap-3 rounded-sm border border-slate-200 bg-white p-3">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={hasDescriptors}
                disabled={disabled}
                onChange={(e) => {
                  const checked = e.target.checked;
                  if (checked) {
                    const existing = value.level_descriptors ?? [];
                    const d4 = existing.find((d) => d.score === 4)?.descriptor ?? '';
                    const d3 = existing.find((d) => d.score === 3)?.descriptor ?? '';
                    const d2 = existing.find((d) => d.score === 2)?.descriptor ?? '';
                    const d1 = existing.find((d) => d.score === 1)?.descriptor ?? '';
                    onChange({
                      ...value,
                      level_descriptors: [
                        { score: 4, descriptor: d4 || 'Exemplary achievement.' },
                        { score: 3, descriptor: d3 || 'Proficient achievement.' },
                        { score: 2, descriptor: d2 || 'Developing achievement.' },
                        { score: 1, descriptor: d1 || 'Beginning or unaddressed.' },
                      ],
                    });
                  } else {
                    onChange({ ...value, level_descriptors: null });
                  }
                }}
                className="size-4 rounded border-slate-300 text-[#1b3b87] focus:ring-[#1b3b87]"
              />
              <span className="text-xs font-bold uppercase tracking-wider text-slate-700">
                Include Exact 1–4 Score Level Descriptors
              </span>
            </label>

            {hasDescriptors && (
              <div className="grid gap-3 pt-2">
                {[4, 3, 2, 1].map((score) => {
                  const desc =
                    value.level_descriptors?.find((d) => d.score === score)?.descriptor ?? '';
                  return (
                    <div key={score} className="grid grid-cols-[3.5rem_1fr] items-start gap-2">
                      <span className="mt-1 text-xs font-bold text-slate-700">Score {score}:</span>
                      <textarea
                        rows={2}
                        value={desc}
                        disabled={disabled}
                        onChange={(e) => {
                          const updatedList: LlmScoreDescriptor[] = [4, 3, 2, 1].map((s) => ({
                            score: s,
                            descriptor:
                              s === score
                                ? e.target.value
                                : (value.level_descriptors?.find((d) => d.score === s)
                                    ?.descriptor ?? ''),
                          }));
                          onChange({ ...value, level_descriptors: updatedList });
                        }}
                        placeholder={`Descriptor for score ${score}...`}
                        className="w-full rounded-sm border border-slate-300 bg-white p-2 text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] disabled:opacity-60"
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Count Band Form */}
      {value.strategy === 'count_band' && (
        <div className="grid gap-4">
          <div className="flex flex-wrap items-center gap-4">
            <div>
              <label
                htmlFor="count-mode"
                className="block text-xs font-bold uppercase tracking-wider text-slate-700"
              >
                Threshold Mode
              </label>
              <select
                id="count-mode"
                value={value.mode}
                disabled={disabled || (agentCaps.allowedCountModes?.length ?? 0) <= 1}
                onChange={(e) => {
                  const nextMode = e.target.value as CountBandMode;
                  if (nextMode === 'minimum_count') {
                    onChange(DEFAULT_COUNT_MIN_CONFIG);
                  } else {
                    onChange(DEFAULT_COUNT_MAX_CONFIG);
                  }
                }}
                className="mt-1 h-8 rounded-sm border border-slate-300 bg-white px-2 text-xs font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
              >
                <option value="minimum_count">Minimum Count (Higher is Better)</option>
                <option value="maximum_count">Maximum Count (Adverse - Lower is Better)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label
                htmlFor="count-t4"
                className="block text-xs font-bold uppercase tracking-wider text-slate-700"
              >
                Score 4 Threshold
              </label>
              <input
                id="count-t4"
                type="number"
                min={0}
                value={value.threshold_4}
                disabled={disabled}
                onChange={(e) =>
                  onChange({ ...value, threshold_4: parseInt(e.target.value || '0', 10) })
                }
                className="mt-1 w-full h-8 rounded-sm border border-slate-300 bg-white px-2.5 text-xs font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
              />
              <span className="text-[10px] text-slate-500 font-medium">
                {value.mode === 'minimum_count' ? 'Count ≥ T4' : 'Count ≤ T4'}
              </span>
            </div>

            <div>
              <label
                htmlFor="count-t3"
                className="block text-xs font-bold uppercase tracking-wider text-slate-700"
              >
                Score 3 Threshold
              </label>
              <input
                id="count-t3"
                type="number"
                min={0}
                value={value.threshold_3}
                disabled={disabled}
                onChange={(e) =>
                  onChange({ ...value, threshold_3: parseInt(e.target.value || '0', 10) })
                }
                className="mt-1 w-full h-8 rounded-sm border border-slate-300 bg-white px-2.5 text-xs font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
              />
              <span className="text-[10px] text-slate-500 font-medium">
                {value.mode === 'minimum_count' ? 'Count ≥ T3' : 'Count ≤ T3'}
              </span>
            </div>

            <div>
              <label
                htmlFor="count-t2"
                className="block text-xs font-bold uppercase tracking-wider text-slate-700"
              >
                Score 2 Threshold
              </label>
              <input
                id="count-t2"
                type="number"
                min={0}
                value={value.threshold_2}
                disabled={disabled}
                onChange={(e) =>
                  onChange({ ...value, threshold_2: parseInt(e.target.value || '0', 10) })
                }
                className="mt-1 w-full h-8 rounded-sm border border-slate-300 bg-white px-2.5 text-xs font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
              />
              <span className="text-[10px] text-slate-500 font-medium">
                {value.mode === 'minimum_count' ? 'Count ≥ T2' : 'Count ≤ T2'}
              </span>
            </div>
          </div>

          <div className="rounded-sm border border-slate-200 bg-white p-2.5 text-[11px] text-slate-600">
            <span className="font-bold text-slate-800">Scoring Mapping: </span>
            {value.mode === 'minimum_count' ? (
              <span>
                Score 4 if count ≥ {value.threshold_4}; Score 3 if count ≥ {value.threshold_3};
                Score 2 if count ≥ {value.threshold_2}; Score 1 otherwise. (Rule: T4 &gt; T3 &gt; T2
                &gt; 0)
              </span>
            ) : (
              <span>
                Score 4 if count ≤ {value.threshold_4}; Score 3 if count ≤ {value.threshold_3};
                Score 2 if count ≤ {value.threshold_2}; Score 1 otherwise. (Rule: 0 ≤ T4 &lt; T3
                &lt; T2)
              </span>
            )}
          </div>
        </div>
      )}

      {/* Ratio Band Form */}
      {value.strategy === 'ratio_band' && (
        <div className="grid gap-4">
          <div>
            <label
              htmlFor="ratio-mode"
              className="block text-xs font-bold uppercase tracking-wider text-slate-700"
            >
              Ratio Mode
            </label>
            <select
              id="ratio-mode"
              value={value.mode}
              disabled={disabled || (agentCaps.allowedRatioModes?.length ?? 0) <= 1}
              onChange={(e) => {
                const nextMode = e.target.value as RatioBandMode;
                if (nextMode === 'coverage_percentage') {
                  onChange(DEFAULT_RATIO_COVERAGE_CONFIG);
                } else {
                  onChange(DEFAULT_RATIO_DIFF_CONFIG);
                }
              }}
              className="mt-1 h-8 rounded-sm border border-slate-300 bg-white px-2 text-xs font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
            >
              <option value="coverage_percentage">
                Coverage Percentage (0–100%, Higher is Better)
              </option>
              <option value="absolute_difference">
                Absolute Difference (Adverse Diff, Lower is Better)
              </option>
            </select>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label
                htmlFor="ratio-t4"
                className="block text-xs font-bold uppercase tracking-wider text-slate-700"
              >
                Score 4 Threshold {value.mode === 'coverage_percentage' ? '(%)' : ''}
              </label>
              <input
                id="ratio-t4"
                type="number"
                step="any"
                value={value.threshold_4}
                disabled={disabled}
                onChange={(e) =>
                  onChange({ ...value, threshold_4: parseFloat(e.target.value || '0') })
                }
                className="mt-1 w-full h-8 rounded-sm border border-slate-300 bg-white px-2.5 text-xs font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
              />
              <span className="text-[10px] text-slate-500 font-medium">
                {value.mode === 'coverage_percentage' ? 'Ratio ≥ T4' : 'Diff ≤ T4'}
              </span>
            </div>

            <div>
              <label
                htmlFor="ratio-t3"
                className="block text-xs font-bold uppercase tracking-wider text-slate-700"
              >
                Score 3 Threshold {value.mode === 'coverage_percentage' ? '(%)' : ''}
              </label>
              <input
                id="ratio-t3"
                type="number"
                step="any"
                value={value.threshold_3}
                disabled={disabled}
                onChange={(e) =>
                  onChange({ ...value, threshold_3: parseFloat(e.target.value || '0') })
                }
                className="mt-1 w-full h-8 rounded-sm border border-slate-300 bg-white px-2.5 text-xs font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
              />
              <span className="text-[10px] text-slate-500 font-medium">
                {value.mode === 'coverage_percentage' ? 'Ratio ≥ T3' : 'Diff ≤ T3'}
              </span>
            </div>

            <div>
              <label
                htmlFor="ratio-t2"
                className="block text-xs font-bold uppercase tracking-wider text-slate-700"
              >
                Score 2 Threshold {value.mode === 'coverage_percentage' ? '(%)' : ''}
              </label>
              <input
                id="ratio-t2"
                type="number"
                step="any"
                value={value.threshold_2}
                disabled={disabled}
                onChange={(e) =>
                  onChange({ ...value, threshold_2: parseFloat(e.target.value || '0') })
                }
                className="mt-1 w-full h-8 rounded-sm border border-slate-300 bg-white px-2.5 text-xs font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
              />
              <span className="text-[10px] text-slate-500 font-medium">
                {value.mode === 'coverage_percentage' ? 'Ratio ≥ T2' : 'Diff ≤ T2'}
              </span>
            </div>
          </div>

          {/* Short Sample Override (coverage_percentage only) */}
          {value.mode === 'coverage_percentage' && (
            <div className="grid gap-3 rounded-sm border border-slate-200 bg-white p-3">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={hasShortSample}
                  disabled={disabled}
                  onChange={(e) => {
                    const checked = e.target.checked;
                    if (checked) {
                      const sampleConfig: ShortSampleConfig = {
                        min_units: value.short_sample?.min_units ?? 3,
                        max_issues_4: value.short_sample?.max_issues_4 ?? 0,
                        max_issues_3: value.short_sample?.max_issues_3 ?? 1,
                        max_issues_2: value.short_sample?.max_issues_2 ?? 2,
                      };
                      onChange({ ...value, short_sample: sampleConfig });
                    } else {
                      onChange({ ...value, short_sample: null });
                    }
                  }}
                  className="size-4 rounded border-slate-300 text-[#1b3b87] focus:ring-[#1b3b87]"
                />
                <span className="text-xs font-bold uppercase tracking-wider text-slate-700">
                  Enable Short-Sample Override (Small unit count fallback)
                </span>
              </label>

              {hasShortSample && value.short_sample && (
                <div className="grid grid-cols-1 sm:grid-cols-4 gap-2.5 pt-2">
                  <div>
                    <label
                      htmlFor="sample-min-units"
                      className="block text-[11px] font-bold uppercase text-slate-600"
                    >
                      Min Units
                    </label>
                    <input
                      id="sample-min-units"
                      type="number"
                      min={1}
                      value={value.short_sample.min_units}
                      disabled={disabled}
                      onChange={(e) =>
                        onChange({
                          ...value,
                          short_sample: {
                            ...value.short_sample!,
                            min_units: parseInt(e.target.value || '1', 10),
                          },
                        })
                      }
                      className="mt-1 w-full h-8 rounded-sm border border-slate-300 bg-white px-2 text-xs font-bold text-slate-800"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="sample-max-4"
                      className="block text-[11px] font-bold uppercase text-slate-600"
                    >
                      Max Issues (4)
                    </label>
                    <input
                      id="sample-max-4"
                      type="number"
                      min={0}
                      value={value.short_sample.max_issues_4}
                      disabled={disabled}
                      onChange={(e) =>
                        onChange({
                          ...value,
                          short_sample: {
                            ...value.short_sample!,
                            max_issues_4: parseInt(e.target.value || '0', 10),
                          },
                        })
                      }
                      className="mt-1 w-full h-8 rounded-sm border border-slate-300 bg-white px-2 text-xs font-bold text-slate-800"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="sample-max-3"
                      className="block text-[11px] font-bold uppercase text-slate-600"
                    >
                      Max Issues (3)
                    </label>
                    <input
                      id="sample-max-3"
                      type="number"
                      min={0}
                      value={value.short_sample.max_issues_3}
                      disabled={disabled}
                      onChange={(e) =>
                        onChange({
                          ...value,
                          short_sample: {
                            ...value.short_sample!,
                            max_issues_3: parseInt(e.target.value || '0', 10),
                          },
                        })
                      }
                      className="mt-1 w-full h-8 rounded-sm border border-slate-300 bg-white px-2 text-xs font-bold text-slate-800"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="sample-max-2"
                      className="block text-[11px] font-bold uppercase text-slate-600"
                    >
                      Max Issues (2)
                    </label>
                    <input
                      id="sample-max-2"
                      type="number"
                      min={0}
                      value={value.short_sample.max_issues_2}
                      disabled={disabled}
                      onChange={(e) =>
                        onChange({
                          ...value,
                          short_sample: {
                            ...value.short_sample!,
                            max_issues_2: parseInt(e.target.value || '0', 10),
                          },
                        })
                      }
                      className="mt-1 w-full h-8 rounded-sm border border-slate-300 bg-white px-2 text-xs font-bold text-slate-800"
                    />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Curriculum Alignment Form */}
      {value.strategy === 'curriculum_alignment' && (
        <div className="grid gap-3">
          <div>
            <label
              htmlFor="curriculum-guidance"
              className="block text-xs font-bold uppercase tracking-wider text-slate-700"
            >
              Curriculum Alignment Guidance (Optional)
            </label>
            <p className="text-[11px] text-slate-500 mb-1">
              Instructions for comparing module learning objectives with syllabus roadmap items.
            </p>
            <textarea
              id="curriculum-guidance"
              rows={3}
              value={value.guidance ?? ''}
              onChange={(e) =>
                onChange({
                  ...value,
                  guidance: e.target.value.trim() ? e.target.value : null,
                })
              }
              disabled={disabled}
              placeholder="Optional alignment scoring guidance..."
              className="w-full rounded-sm border border-slate-300 bg-white p-2.5 text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] disabled:opacity-60"
            />
          </div>
        </div>
      )}
    </div>
  );
}
