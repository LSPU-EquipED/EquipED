import { cn } from '@equiped/ui';
import type { ModelValidationCriterionDefinition } from '../types';
import type { ModelValidationFormState } from '../hooks/useModelValidationFormState';

type CriterionScoreFieldProps = {
  criterion: ModelValidationCriterionDefinition;
  domainTitle?: string;
  scoreKey: string;
  form: Pick<
    ModelValidationFormState,
    'expectedScores' | 'setExpectedScores' | 'registerScoreInput' | 'handleScoreKeyDown'
  >;
};

export function CriterionScoreField({
  criterion,
  domainTitle,
  scoreKey,
  form,
}: CriterionScoreFieldProps) {
  const { expectedScores, setExpectedScores, registerScoreInput, handleScoreKeyDown } = form;
  const val = expectedScores[scoreKey] ?? '';
  return (
    <label className="grid grid-cols-[minmax(0,1fr)_6.5rem] items-center gap-3 p-3.5 hover:bg-surface-subtle/40 transition-colors cursor-pointer">
      <span className="min-w-0">
        <span className="block text-xs font-semibold text-text">
          {criterion.criterion_code} · {criterion.title}
        </span>
        <span className="mt-0.5 block text-[11px] text-text-muted leading-relaxed">
          {criterion.domain_title ?? domainTitle} — {criterion.description}
        </span>
      </span>
      <div className="flex items-center justify-end gap-1.5">
        <input
          ref={(node) => {
            registerScoreInput(scoreKey, node);
          }}
          type="text"
          inputMode="numeric"
          pattern="[1-4]"
          maxLength={1}
          autoComplete="off"
          placeholder="1–4"
          value={val}
          onChange={(event) => {
            const nextScore = event.target.value;
            if (!/^[1-4]?$/.test(nextScore)) return;
            setExpectedScores((current) => ({
              ...current,
              [scoreKey]: nextScore,
            }));
          }}
          onWheel={(event) => {
            event.currentTarget.blur();
          }}
          onKeyDown={(event) => handleScoreKeyDown(event, scoreKey)}
          onFocus={(event) => event.currentTarget.select()}
          className={cn(
            'h-9 w-16 rounded-sm border bg-surface px-2.5 text-sm font-bold tabular-nums text-center transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            val ? 'border-primary text-primary bg-primary-soft/30' : 'border-input text-text',
          )}
          required
          aria-label={`Expected score for ${criterion.criterion_code} ${criterion.title}`}
        />
      </div>
    </label>
  );
}
