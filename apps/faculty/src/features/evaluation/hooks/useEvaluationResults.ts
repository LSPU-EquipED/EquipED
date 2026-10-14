import { useQuery } from "@tanstack/react-query";
import { evaluationApi } from "../api/evaluation.api";

export function useEvaluationResults(
  evaluationId?: string | null,
  status?: string,
) {
  return useQuery({
    queryKey: ["evaluation-results", evaluationId],
    queryFn: () => evaluationApi.getEvaluationResults(evaluationId!),
    enabled: Boolean(evaluationId && status === "COMPLETED"),
    staleTime: 5000,
  });
}
