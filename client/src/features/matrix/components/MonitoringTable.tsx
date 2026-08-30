import { useState } from 'react';
import { Loader2, AlertTriangle } from 'lucide-react';
import { MatrixFilters } from './MatrixFilters';
import { useMonitoringMatrix } from '../hooks/useMonitoringMatrix';
import { formatRevisionContext, getStatusVariant, getRatingVariant } from '../utils';
import type { MonitoringMatrixRow } from '../types';
import { Badge } from '@/shared/components/Badge';
import { TABLE_STYLES } from '@/shared/constants/theme';
import { cn } from '@/shared/components/utils';

export function MonitoringTable() {
  const [program, setProgram] = useState('all');
  const [status, setStatus] = useState('all');

  const { data, isLoading, isError } = useMonitoringMatrix({
    program: program !== 'all' ? program : undefined,
    status: status !== 'all' ? status : undefined,
  });

  return (
    <section className="flex flex-col gap-6">
      <MatrixFilters
        program={program}
        status={status}
        onProgramChange={setProgram}
        onStatusChange={setStatus}
      />

      <div className={TABLE_STYLES.wrapper}>
        {isLoading ? (
          <div className="flex justify-center items-center py-12 text-text-muted font-medium text-sm gap-2">
            <Loader2 className="size-6 animate-spin text-primary" />
            <span>Loading matrix data...</span>
          </div>
        ) : isError ? (
          <div className="flex justify-center items-center py-12 text-destructive font-semibold text-sm gap-2 bg-destructive-soft">
            <AlertTriangle className="size-6 text-destructive" />
            <span>Failed to load matrix data.</span>
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="text-center py-12 text-text-muted font-medium text-sm">
            <p>No evaluation records yet</p>
          </div>
        ) : (
          <table className={TABLE_STYLES.table}>
            <thead className={TABLE_STYLES.thead}>
              <tr>
                <th className={TABLE_STYLES.th}>SLM Title</th>
                <th className={TABLE_STYLES.th}>Program</th>
                <th className={TABLE_STYLES.th}>Status</th>
                <th className={TABLE_STYLES.th}>Form Revision</th>
                <th className={cn(TABLE_STYLES.th, 'text-right')}>Score</th>
                <th className={TABLE_STYLES.th}>Rating</th>
                <th className={cn(TABLE_STYLES.th, 'text-right')}>Flags</th>
                <th className={cn(TABLE_STYLES.th, 'text-right')}>Last Updated</th>
              </tr>
            </thead>
            <tbody className={TABLE_STYLES.tbody}>
              {data.items.map((row: MonitoringMatrixRow) => (
                <tr key={row.evaluation_id ?? row.matrix_id} className={TABLE_STYLES.tr}>
                  <td className={cn(TABLE_STYLES.td, 'font-semibold text-text')}>
                    {row.document_title || 'Untitled SLM'}
                  </td>
                  <td className={cn(TABLE_STYLES.td, 'text-text-muted font-medium')}>
                    {row.program || '—'}
                  </td>
                  <td className={TABLE_STYLES.td}>
                    <Badge variant={getStatusVariant(row.evaluation_status)}>
                      {row.evaluation_status.replace('_', ' ')}
                    </Badge>
                  </td>
                  <td className={cn(TABLE_STYLES.td, 'text-text-muted font-medium')}>
                    {formatRevisionContext(row.domain_scores)}
                  </td>
                  <td className={cn(TABLE_STYLES.tdData, 'text-right font-medium')}>
                    {row.synthesized_score != null ? row.synthesized_score.toFixed(2) : '—'}
                  </td>
                  <td className={TABLE_STYLES.td}>
                    {row.adjectival_rating ? (
                      <Badge variant={getRatingVariant(row.adjectival_rating)}>
                        {row.adjectival_rating}
                      </Badge>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </td>
                  <td className={cn(TABLE_STYLES.td, 'text-right')}>
                    {row.flag_count > 0 ? (
                      <span className="inline-flex items-center justify-center min-w-5 h-5 rounded-full bg-warning-soft text-warning border border-warning/20 text-xs font-bold px-1.5 tabular-nums">
                        {row.flag_count}
                      </span>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </td>
                  <td className={cn(TABLE_STYLES.tdData, 'text-right text-text-muted font-medium')}>
                    {new Date(row.last_updated).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
