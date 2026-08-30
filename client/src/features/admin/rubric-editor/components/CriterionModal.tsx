import { useState } from 'react';
import { Loader2, X } from 'lucide-react';
import { StrategyConfigEditor } from './StrategyConfigEditor';
import { getRubricOperationError } from '../hooks/useRubrics';
import type { RubricCriterion, StrategyConfig } from '../types';
import { getDefaultStrategyConfigForAgent } from '../utils';

interface CriterionModalProps {
  isOpen: boolean;
  onClose: () => void;
  agentId: string;
  domainTitle: string;
  criterion?: RubricCriterion | null;
  onSave: (data: {
    criterion_code: string;
    title: string;
    description: string;
    scoring_rule: string | null;
    strategy_config: StrategyConfig;
  }) => Promise<void> | void;
  isPending: boolean;
  error?: unknown;
}

function CriterionModalContent({
  onClose,
  agentId,
  domainTitle,
  criterion,
  onSave,
  isPending,
  error,
}: Omit<CriterionModalProps, 'isOpen'>) {
  const isEditing = Boolean(criterion);

  const [criterionCode, setCriterionCode] = useState(criterion?.criterion_code ?? '');
  const [title, setTitle] = useState(criterion?.title ?? '');
  const [description, setDescription] = useState(criterion?.description ?? '');
  const [scoringRule, setScoringRule] = useState(criterion?.scoring_rule ?? '');
  const [strategyConfig, setStrategyConfig] = useState<StrategyConfig>(
    criterion?.strategy_config ?? getDefaultStrategyConfigForAgent(agentId),
  );
  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);

    const cleanCode = criterionCode.trim().toUpperCase();
    const cleanTitle = title.trim();
    const cleanDesc = description.trim();
    const cleanRule = scoringRule.trim() ? scoringRule.trim() : null;

    if (!cleanCode) {
      setLocalError('Criterion ID is required (e.g. OP-01, GAD-02).');
      return;
    }
    if (!cleanTitle) {
      setLocalError('Criterion title is required.');
      return;
    }
    if (!cleanDesc) {
      setLocalError('Description is required.');
      return;
    }
    if (strategyConfig.strategy === 'llm_rubric_guidance' && !strategyConfig.guidance.trim()) {
      setLocalError('Evaluation guidance is required for LLM-scored criteria.');
      return;
    }

    try {
      await onSave({
        criterion_code: cleanCode,
        title: cleanTitle,
        description: cleanDesc,
        scoring_rule: cleanRule,
        strategy_config: strategyConfig,
      });
    } catch {
      // Error handled by query or parent
    }
  };

  const errorMessage = localError || (error ? getRubricOperationError(error) : null);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="criterion-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs"
    >
      <div className="relative w-full max-w-2xl max-h-[90vh] flex flex-col rounded-sm border border-border bg-surface shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border p-4 bg-surface-subtle">
          <div>
            <h2
              id="criterion-modal-title"
              className="text-sm font-bold uppercase tracking-wider text-text"
            >
              {isEditing ? 'Edit Criterion' : 'Add New Criterion'}
            </h2>
            <p className="text-xs text-text-muted font-medium">
              Domain: <strong className="text-text">{domainTitle}</strong>
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="inline-flex size-8 items-center justify-center rounded-sm text-text-muted hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Close criterion dialog"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-5 grid gap-4">
          {errorMessage && (
            <div
              role="alert"
              className="rounded-sm border border-destructive/30 bg-destructive-soft p-3 text-xs font-semibold text-destructive"
            >
              {errorMessage}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label
                htmlFor="criterion-code"
                className="block text-xs font-bold uppercase tracking-wider text-text"
              >
                Criterion ID <span className="text-destructive">*</span>
              </label>
              <input
                id="criterion-code"
                type="text"
                value={criterionCode}
                onChange={(e) => setCriterionCode(e.target.value)}
                disabled={isPending}
                placeholder="e.g. OP-01"
                maxLength={50}
                className="mt-1 w-full h-8 rounded-sm border border-input bg-surface px-2.5 text-xs font-bold text-text uppercase focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            <div className="sm:col-span-2">
              <label
                htmlFor="criterion-title"
                className="block text-xs font-bold uppercase tracking-wider text-text"
              >
                Title <span className="text-destructive">*</span>
              </label>
              <input
                id="criterion-title"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={isPending}
                placeholder="e.g. Topic Coherence"
                maxLength={200}
                className="mt-1 w-full h-8 rounded-sm border border-input bg-surface px-2.5 text-xs font-semibold text-text focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>

          <div>
            <label
              htmlFor="criterion-description"
              className="block text-xs font-bold uppercase tracking-wider text-text"
            >
              Description / Prompt Entry <span className="text-destructive">*</span>
            </label>
            <textarea
              id="criterion-description"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={isPending}
              placeholder="What this criterion measures in the module..."
              maxLength={4000}
              className="mt-1 w-full rounded-sm border border-input bg-surface p-2 text-xs font-medium text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div>
            <label
              htmlFor="criterion-scoring-rule"
              className="block text-xs font-bold uppercase tracking-wider text-text"
            >
              Scoring Rule Text (Human Reference)
            </label>
            <textarea
              id="criterion-scoring-rule"
              rows={2}
              value={scoringRule}
              onChange={(e) => setScoringRule(e.target.value)}
              disabled={isPending}
              placeholder="Human-readable scoring criteria summary for faculty..."
              maxLength={4000}
              className="mt-1 w-full rounded-sm border border-input bg-surface p-2 text-xs font-medium text-text placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          {/* Strategy Editor */}
          <StrategyConfigEditor
            agentId={agentId}
            value={strategyConfig}
            onChange={setStrategyConfig}
            disabled={isPending}
          />

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 border-t border-border pt-4 mt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isPending}
              className="h-9 px-3 rounded-sm border border-border bg-surface text-xs font-bold uppercase tracking-wider text-text hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="inline-flex h-9 items-center justify-center gap-1.5 px-4 rounded-sm bg-primary text-xs font-bold uppercase tracking-wider text-primary-foreground hover:bg-primary-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            >
              {isPending && <Loader2 className="size-3.5 animate-spin" />}
              {isEditing ? 'Save Changes' : 'Add Criterion'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function CriterionModal(props: CriterionModalProps) {
  if (!props.isOpen) return null;

  return (
    <CriterionModalContent
      key={`${props.agentId}-${props.domainTitle}-${props.criterion?.rubric_criterion_id || 'new'}`}
      {...props}
    />
  );
}
