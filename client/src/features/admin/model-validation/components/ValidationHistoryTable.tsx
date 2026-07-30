import { useState } from 'react';
import type { UseQueryResult } from '@tanstack/react-query';
import type { ModelValidationListResponse } from '../types';
import { HISTORY_COLSPAN } from '../utils/helpers';
import { HistoryRow } from './ValidationDetail';

export function ValidationHistoryTable({
  history,
}: {
  history: UseQueryResult<ModelValidationListResponse>;
}) {
  const [expandedValidationId, setExpandedValidationId] = useState<string | null>(null);

  return (
    <div className="overflow-hidden rounded-sm border border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-4 py-3">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">
          Validation history
        </h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-600">
            <tr>
              <th className="px-4 py-3">SLM</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Criteria</th>
              <th className="px-4 py-3 text-right">Compared</th>
              <th className="px-4 py-3 text-right">Exact</th>
              <th className="px-4 py-3 text-right">Mean error</th>
              <th className="px-4 py-3 text-right">Latency</th>
              <th className="px-4 py-3 text-right">Perplexity</th>
              <th className="px-4 py-3 text-right">Toxicity</th>
              <th className="px-4 py-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {history.isLoading ? (
              <tr>
                <td
                  colSpan={HISTORY_COLSPAN}
                  className="px-4 py-8 text-center font-semibold text-slate-600"
                >
                  Loading validation history…
                </td>
              </tr>
            ) : null}
            {history.isError ? (
              <tr>
                <td
                  colSpan={HISTORY_COLSPAN}
                  className="px-4 py-8 text-center font-semibold text-[#b91c1c]"
                >
                  Unable to load validation history.
                </td>
              </tr>
            ) : null}
            {history.data?.items.map((item) => {
              const compared = item.criterion_scores.filter(
                (score) => score.actual_score != null,
              );
              const exactMatches = compared.filter(
                (score) => score.actual_score === score.expected_score,
              ).length;
              const isExpanded = expandedValidationId === item.validation_id;
              return (
                <HistoryRow
                  key={item.validation_id}
                  item={item}
                  isExpanded={isExpanded}
                  isAnyExpanded={expandedValidationId !== null}
                  comparedCount={compared.length}
                  exactMatches={exactMatches}
                  onToggle={() =>
                    setExpandedValidationId((current) =>
                      current === item.validation_id ? null : item.validation_id,
                    )
                  }
                  onClose={() => setExpandedValidationId(null)}
                />
              );
            })}
            {!history.isLoading && !history.isError && history.data?.items.length === 0 ? (
              <tr>
                <td
                  colSpan={HISTORY_COLSPAN}
                  className="px-4 py-8 text-center font-semibold text-slate-600"
                >
                  No validation runs yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
