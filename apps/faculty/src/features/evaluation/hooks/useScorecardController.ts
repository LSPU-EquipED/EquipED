import { useMemo, useState } from "react";
import { useNavigate, useParams } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { isTargetAgent, TARGET_AGENT_META } from "@equiped/types";
import { useEvaluation } from "./useEvaluationStatus";
import { evaluationApi } from "../api/evaluation.api";
import { sortCriteriaGrouped } from "../utils/scoreHelpers";

export function useScorecardController() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { id } = useParams({ strict: false }) as { id?: string };
  const [selectedDomainId, setSelectedDomainId] = useState<string>("sme");

  const { data: evaluation, isLoading, isError } = useEvaluation(id ?? "");
  const [reviewModalAgent, setReviewModalAgent] = useState<string | null>(null);
  const [showReevaluateModal, setShowReevaluateModal] = useState(false);
  const isTerminal =
    evaluation?.status === "COMPLETED" || evaluation?.status === "FAILED";
  const isFailed = evaluation?.status === "FAILED";
  const isEvaluating =
    evaluation?.status === "SUBMITTED" ||
    evaluation?.status === "PREPROCESSING" ||
    evaluation?.status === "EVALUATING" ||
    evaluation?.status === "SYNTHESIZING";

  const {
    data: results,
    isLoading: isLoadingResults,
    isError: isResultsError,
    refetch: refetchResults,
  } = useQuery({
    queryKey: ["evaluation-results", id],
    queryFn: () => evaluationApi.getEvaluationResults(id!),
    enabled: !!id && isTerminal,
    retry: 2,
    staleTime: 5000,
    refetchInterval: (query) =>
      isTerminal && !query.state.data ? 1500 : false,
  });

  const isPartial = Boolean(
    results?.is_partial || evaluation?.partial_without_curriculum,
  );
  const partialReason = results?.partial_reason || evaluation?.partial_reason;

  const agentLabels: Record<string, string> = useMemo(
    () => ({
      sme: "Subject Matter Expert (SME)",
      coordinator: "Program Coordinator",
      gad: "Gender and Development (GAD)",
      itso: "Innovation and Technology Support Office",
    }),
    [],
  );

  const domainKeys = useMemo(() => {
    const canonical = ["sme", "coordinator", "gad", "itso"];
    if (!results?.domain_scores) return canonical;
    const extras = Object.keys(results.domain_scores).filter(
      (key) => !canonical.includes(key),
    );
    return [...canonical, ...extras];
  }, [results]);

  const singleAgentMeta =
    evaluation && isTargetAgent(evaluation.target_agent)
      ? TARGET_AGENT_META[evaluation.target_agent]
      : null;
  const isSingleAgentRun = singleAgentMeta !== null;

  // Active domain data on the right (auto-falls back to target agent or first available domain with scores)
  const targetAgentKey =
    evaluation && isTargetAgent(evaluation.target_agent)
      ? evaluation.target_agent
      : null;
  const availableDomains = domainKeys.filter(
    (k) => results?.domain_scores[k] != null,
  );
  const effectiveDomainId =
    targetAgentKey && results?.domain_scores[targetAgentKey] != null
      ? targetAgentKey
      : availableDomains.includes(selectedDomainId)
        ? selectedDomainId
        : availableDomains[0] || domainKeys[0] || "sme";
  const activeDomainData = results?.domain_scores[effectiveDomainId];

  const effectiveFormPresentation = results?.forms?.[effectiveDomainId];
  const sortedCriteria = sortCriteriaGrouped(
    activeDomainData?.criteria || [],
    effectiveFormPresentation,
  );

  const handleOpenReview = (domainId: string) => {
    setReviewModalAgent(domainId);
  };

  const handleCloseReview = () => {
    setReviewModalAgent(null);
  };

  const handleOpenReevaluate = () => {
    setShowReevaluateModal(true);
  };

  const handleCloseReevaluate = () => {
    setShowReevaluateModal(false);
  };

  const handleReevaluateSubmitted = (newEvaluationId: string) => {
    setShowReevaluateModal(false);
    void queryClient.invalidateQueries({ queryKey: ["evaluation"] });
    void queryClient.invalidateQueries({
      queryKey: ["evaluation-results"],
    });
    void queryClient.invalidateQueries({
      queryKey: ["evaluation-history"],
    });
    void navigate({
      to: "/evaluations/$id",
      params: { id: newEvaluationId },
    });
  };

  return {
    id,
    evaluation,
    isLoading,
    isError,
    results,
    isLoadingResults,
    isResultsError,
    refetchResults,
    isTerminal,
    isFailed,
    isEvaluating,
    isPartial,
    partialReason,
    agentLabels,
    domainKeys,
    availableDomains,
    setSelectedDomainId,
    singleAgentMeta,
    isSingleAgentRun,
    effectiveDomainId,
    activeDomainData,
    sortedCriteria,
    reviewModalAgent,
    showReevaluateModal,
    handleOpenReview,
    handleCloseReview,
    handleOpenReevaluate,
    handleCloseReevaluate,
    handleReevaluateSubmitted,
  };
}
