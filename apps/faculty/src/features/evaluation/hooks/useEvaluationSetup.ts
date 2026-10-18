import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { documentsApi, getErrorMessage } from "@equiped/api-client";
import {
  isLspuSccProgram,
  TARGET_AGENT_META,
  type TargetAgent,
} from "@equiped/types";
import { useSubmitEvaluation } from "./useSubmitEvaluation";
import { buildEvaluationSubmitPayload } from "../utils/setupState";

export interface EvaluationSetupOptions {
  documentId: string;
  detectedProgram: string | null;
  targetAgent: TargetAgent;
  onSubmitted?: (evaluationId: string) => void;
  onClose?: () => void;
}

/** The existing admission contract, shared by inline setup and re-evaluation. */
export function useEvaluationSetup({
  documentId,
  detectedProgram,
  targetAgent,
  onSubmitted,
  onClose,
}: EvaluationSetupOptions) {
  const meta = TARGET_AGENT_META[targetAgent];
  const submission = useSubmitEvaluation();
  const [program, setProgramValue] = useState(
    detectedProgram && isLspuSccProgram(detectedProgram)
      ? detectedProgram
      : "BSCS",
  );
  const [curriculumId, setCurriculumId] = useState<string | null>(null);
  const curricula = useQuery({
    queryKey: ["curriculum-suggestion", documentId, program],
    queryFn: () => documentsApi.getCurriculumSuggestion(documentId, program),
    enabled:
      Boolean(documentId) &&
      meta.requiresCurriculum &&
      isLspuSccProgram(program),
    staleTime: 30000,
  });
  const readyCurricula = curricula.data?.curriculumSuggestions ?? [];
  const effectiveCurriculumId =
    curriculumId &&
    readyCurricula.some((item) => item.documentId === curriculumId)
      ? curriculumId
      : null;
  const canSubmit =
    Boolean(documentId) &&
    !submission.isPending &&
    isLspuSccProgram(program) &&
    (!meta.requiresCurriculum || Boolean(effectiveCurriculumId));
  const submit = () => {
    if (!canSubmit) return;
    submission.mutate(
      buildEvaluationSubmitPayload({
        documentId,
        program,
        targetAgent,
        curriculumId: meta.requiresCurriculum
          ? effectiveCurriculumId
          : undefined,
      }),
      {
        onSuccess: (result) => {
          onSubmitted?.(result.evaluation_id);
          onClose?.();
        },
      },
    );
  };
  return {
    meta,
    program,
    curriculumId: effectiveCurriculumId,
    readyCurricula,
    setProgram: (value: string) => {
      setProgramValue(value);
      setCurriculumId(null);
    },
    setCurriculumId,
    isLoadingCurricula: curricula.isLoading,
    isCurriculaError: curricula.isError && !curricula.data,
    retryCurricula: () => void curricula.refetch(),
    canSubmit,
    isPending: submission.isPending,
    submit,
    error: submission.error
      ? getErrorMessage(submission.error, "Unable to submit evaluation.")
      : null,
  };
}
export type EvaluationSetupState = ReturnType<typeof useEvaluationSetup>;
