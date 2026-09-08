import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Play, Spinner, WarningCircle, X } from '@phosphor-icons/react';
import { getErrorMessage } from '@/shared/api/http';
import { documentsApi } from '@/shared/api/documents.api';
import { Button } from '@/shared/components/Button';
import { Badge } from '@/shared/components/Badge';
import { CANONICAL_PROGRAMS, isLspuSccProgram, normalizeProgram } from '@/shared/constants/programs';
import { TARGET_AGENT_META, type TargetAgent } from '@/shared/types/evaluations';
import type { CurriculumSuggestionItem } from '@/shared/types/documents';
import { useSubmitEvaluation } from '../hooks/useSubmitEvaluation';
import { buildTargetedEvaluationSubmitPayload } from '../utils/setupState';

export interface EvaluationConfirmModalProps {
  documentId: string;
  documentTitle: string;
  detectedProgram: string | null;
  targetAgent: TargetAgent;
  onClose: () => void;
  onSubmitted?: (evaluationId: string) => void;
}


export function EvaluationConfirmModal({
  documentId,
  documentTitle,
  detectedProgram,
  targetAgent,
  onClose,
  onSubmitted,
}: EvaluationConfirmModalProps) {
  const meta = TARGET_AGENT_META[targetAgent];
  const submitEvaluation = useSubmitEvaluation();
  const [program, setProgram] = useState(detectedProgram ?? '');
  const [curriculumId, setCurriculumId] = useState<string | null>(null);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  const programValid = isLspuSccProgram(program);
  const { data: curriculumData, isLoading: isLoadingCurricula } = useQuery({
    queryKey: ['curriculum-suggestion', documentId, program],
    queryFn: () => documentsApi.getCurriculumSuggestion(documentId, program),
    enabled: meta.requiresCurriculum && programValid,
    staleTime: 30000,
  });

  const readyCurricula: CurriculumSuggestionItem[] =
    curriculumData?.curriculumSuggestions ?? [];
  const effectiveCurriculumId =
    curriculumId && readyCurricula.some((c) => c.documentId === curriculumId)
      ? curriculumId
      : null;
  const canSubmit =
    programValid &&
    !submitEvaluation.isPending &&
    (!meta.requiresCurriculum || Boolean(effectiveCurriculumId));

  const handleConfirm = () => {
    if (!canSubmit) return;
    const payload = buildTargetedEvaluationSubmitPayload({
      documentId,
      program,
      targetAgent,
      curriculumId: meta.requiresCurriculum ? effectiveCurriculumId : undefined,
    });
    submitEvaluation.mutate(payload, {
      onSuccess: (result) => {
        onSubmitted?.(result.evaluation_id);
        onClose();
      },
    });
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Confirm ${meta.fullName} evaluation`}
        className="w-full max-w-lg rounded-sm border border-border bg-surface shadow-none"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <p className="text-[11px] font-bold uppercase tracking-wider text-text-muted">
              Confirm Targeted Evaluation
            </p>
            <h2 className="mt-0.5 truncate text-base font-bold text-text" title={documentTitle}>
              {documentTitle}
            </h2>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              <Badge variant="info">{meta.shortLabel}</Badge>
              <span className="text-xs font-semibold text-text">{meta.fullName}</span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close evaluation confirmation"
            className="inline-flex size-8 shrink-0 items-center justify-center rounded-sm text-text-muted hover:bg-surface-subtle hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>

        <div className="space-y-4 px-5 py-4">
          <p className="text-xs leading-relaxed text-text-muted">{meta.requirement}</p>

          <div>
            <label
              htmlFor="targeted-eval-program"
              className="text-xs font-bold uppercase tracking-wider text-text"
            >
              Confirmed Program
            </label>
            <select
              id="targeted-eval-program"
              value={program}
              onChange={(event) => {
                setProgram(event.target.value);
                setCurriculumId(null);
              }}
              className="mt-1.5 h-9 w-full rounded-xs border border-input bg-surface px-2.5 text-sm font-medium text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="">Select program</option>
              {CANONICAL_PROGRAMS.map((option) => (
                <option key={option} value={option}>
                  {option === 'BSCS' ? 'BSCS — Computer Science' : 'BSInfoTech — Information Technology'}
                </option>
              ))}
            </select>
          </div>

          {meta.requiresCurriculum ? (
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-text">
                Curriculum Reference
              </span>
              {isLoadingCurricula ? (
                <p className="mt-1.5 flex items-center gap-2 text-xs text-text-muted">
                  <Spinner className="size-3.5 animate-spin" aria-hidden="true" />
                  Loading verified curricula…
                </p>
              ) : readyCurricula.length === 0 ? (
                <p className="mt-1.5 rounded-xs border border-warning/30 bg-warning-soft px-3 py-2 text-xs font-medium text-warning" role="alert">
                  No verified curriculum found for {normalizeProgram(program) || 'this program'}. Coordinator evaluation requires one.
                </p>
              ) : (
                <div className="mt-1.5 space-y-1.5" role="radiogroup" aria-label="Select curriculum reference">
                  {readyCurricula.map((item) => (
                    <label
                      key={item.documentId}
                      className="flex cursor-pointer items-start gap-2.5 rounded-xs border border-border px-3 py-2 text-xs hover:border-primary/50 has-checked:border-primary has-checked:bg-primary-soft/30"
                    >
                      <input
                        type="radio"
                        name="targeted-eval-curriculum"
                        value={item.documentId}
                        checked={effectiveCurriculumId === item.documentId}
                        onChange={() => setCurriculumId(item.documentId)}
                        className="mt-0.5 accent-primary"
                      />
                      <span className="min-w-0">
                        <span className="block truncate font-semibold text-text">{item.title}</span>
                        <span className="block text-[11px] text-text-muted">
                          {item.program} · {item.matchReason}
                        </span>
                      </span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          ) : null}

          {submitEvaluation.error ? (
            <p className="flex items-center gap-2 rounded-xs border border-destructive/30 bg-destructive-soft px-3 py-2 text-xs font-semibold text-destructive" role="alert">
              <WarningCircle className="size-4 shrink-0" aria-hidden="true" />
              {getErrorMessage(submitEvaluation.error, 'Unable to submit evaluation.')}
            </p>
          ) : null}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-3.5">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={handleConfirm}
            disabled={!canSubmit}
            isLoading={submitEvaluation.isPending}
          >
            <Play className="size-3.5" aria-hidden="true" />
            <span>Run {meta.shortLabel} Evaluation</span>
          </Button>
        </div>
      </div>
    </div>
  );
}
