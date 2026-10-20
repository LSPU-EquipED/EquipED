import { useQuery } from "@tanstack/react-query";
import { itsoApi } from "@equiped/api-client";
import type { AssessmentRead, TargetAgent } from "@equiped/types";
import { evaluationApi } from "../api/evaluation.api";

export function useEvaluationResults(
  evaluationId?: string | null,
  status?: string,
  agent?: TargetAgent | "all",
) {
  const query = useQuery<AssessmentRead>({
    queryKey: [
      "evaluation-results",
      evaluationId,
      agent === "itso" ? "assessment" : "legacy",
    ],
    queryFn: ({ signal }) =>
      agent === "itso"
        ? itsoApi.getAssessment(evaluationId!, signal)
        : evaluationApi
            .getEvaluationResults(evaluationId!)
            .then((result) => ({ contract: "legacy.v1" as const, result })),
    enabled: Boolean(
      evaluationId &&
      (status === "COMPLETED" || (status === "FAILED" && agent === "itso")),
    ),
    staleTime: 5000,
    retry: false,
    // A 202 is a pending projection, never a completed empty assessment.
    refetchInterval: (q) =>
      q.state.data && "detail" in q.state.data && q.state.dataUpdateCount < 150
        ? 2000
        : false,
  });
  const response = query.data;
  return {
    ...query,
    data:
      response && "contract" in response && response.contract === "legacy.v1"
        ? response.result
        : undefined,
    assessment:
      response &&
      "contract" in response &&
      response.contract === "itso_evidence.v1"
        ? response
        : undefined,
    isAssessmentPending: Boolean(response && "detail" in response),
    isLoading: query.isLoading || Boolean(response && "detail" in response),
  };
}
