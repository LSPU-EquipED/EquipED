import { useQuery } from "@tanstack/react-query";
import { isApiError, itsoApi } from "@equiped/api-client";
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
    queryFn: async ({ signal }) => {
      try {
        const result = await evaluationApi.getEvaluationResults(
          evaluationId!,
          signal,
        );
        return { contract: "legacy.v1" as const, result };
      } catch (error) {
        if (
          agent === "itso" &&
          isApiError(error) &&
          error.status === 409 &&
          error.detail === "unsupported_version"
        ) {
          return itsoApi.getAssessment(evaluationId!, signal);
        }
        throw error;
      }
    },
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
