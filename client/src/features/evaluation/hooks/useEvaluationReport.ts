import { useMemo } from 'react';
import type { EvaluationResultsResponse } from '@/features/evaluation/types';

export function useEvaluationReport(results: EvaluationResultsResponse | null) {
  return useMemo(() => {
    if (!results) return null;
    return {
      document_title: results.document_title,
      program: results.program,
      synthesized_score: results.synthesized_score,
      domain_scores: results.domain_scores,
      flags: results.flags,
    };
  }, [results]);
}
