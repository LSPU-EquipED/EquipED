import { useState } from 'react';
import { Loader2, AlertTriangle } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table';
import { MatrixFilters } from './MatrixFilters';
import { useMonitoringMatrix } from '../hooks/useMonitoringMatrix';
import type { MonitoringMatrixRow } from '../types';

function statusClass(status: string) {
  if (status === 'FAILED') return 'border-destructive/50 text-destructive bg-destructive/10';
  if (status.startsWith('COMPLETED')) return 'border-primary/50 text-primary bg-primary/10';
  return 'border-muted-foreground/30 bg-muted/50';
}

export function MonitoringTable() {
  const [program, setProgram] = useState('all');
  const [status, setStatus] = useState('all');

  const { data, isLoading, isError } = useMonitoringMatrix({
    program: program !== 'all' ? program : undefined,
    status: status !== 'all' ? status : undefined,
  });

  return (
    <section className="flex flex-col gap-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          Matrix
        </p>
        <h1 className="mt-2 text-2xl font-semibold">Monitoring Matrix</h1>
      </div>

      <MatrixFilters
        program={program}
        status={status}
        onProgramChange={setProgram}
        onStatusChange={setStatus}
      />

      <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center items-center py-12 text-muted-foreground gap-2">
            <Loader2 className="size-6 animate-spin" />
            <span>Loading matrix data...</span>
          </div>
        ) : isError ? (
          <div className="flex justify-center items-center py-12 text-destructive gap-2">
            <AlertTriangle className="size-6" />
            <span>Failed to load matrix data.</span>
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <p>No evaluation records yet</p>
          </div>
        ) : (
          <Table>
            <TableHeader className="bg-muted/50">
              <TableRow>
                <TableHead>SLM Title</TableHead>
                <TableHead>Program</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Score</TableHead>
                <TableHead className="text-right">Flags</TableHead>
                <TableHead className="text-right">Last Updated</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((row: MonitoringMatrixRow) => (
                <TableRow key={row.evaluation_id}>
                  <TableCell className="font-medium">
                    {row.document_title || 'Untitled SLM'}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{row.program || '—'}</TableCell>
                  <TableCell>
                    <span
                      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${statusClass(row.evaluation_status)}`}
                    >
                      {row.evaluation_status.replace('_', ' ')}
                    </span>
                  </TableCell>
                  <TableCell className="text-right font-mono font-medium">
                    {row.synthesized_score != null ? row.synthesized_score.toFixed(2) : '—'}
                  </TableCell>
                  <TableCell className="text-right">
                    {row.flag_count > 0 ? (
                      <span className="inline-flex items-center justify-center min-w-5 h-5 rounded-full bg-orange-100 text-orange-700 text-xs font-bold px-1.5">
                        {row.flag_count}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right text-muted-foreground text-sm">
                    {new Date(row.last_updated).toLocaleDateString()}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </section>
  );
}
