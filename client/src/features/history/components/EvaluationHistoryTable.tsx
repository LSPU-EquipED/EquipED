import { useState } from 'react';
import { Outlet, Link } from '@tanstack/react-router';
import { Loader2, AlertTriangle, ExternalLink } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table';
import { HistoryFilters } from './HistoryFilters';
import { useEvaluationHistory } from '../hooks/useEvaluationHistory';
import type { HistoryEvaluationItem } from '../types';

function statusClass(status: string) {
  if (status === 'FAILED') return 'border-destructive/50 text-destructive bg-destructive/10';
  if (status.startsWith('COMPLETED')) return 'border-primary/50 text-primary bg-primary/10';
  return 'border-muted-foreground/30 bg-muted/50';
}

export function EvaluationHistoryTable() {
  const [status, setStatus] = useState('all');

  const { data, isLoading, isError } = useEvaluationHistory({
    status: status !== 'all' ? status : undefined,
  });

  return (
    <section className="flex flex-col gap-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          History
        </p>
        <h1 className="mt-2 text-2xl font-semibold">Evaluation History</h1>
      </div>

      <HistoryFilters 
        status={status}
        onStatusChange={setStatus}
      />

      <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center items-center py-12 text-muted-foreground gap-2">
            <Loader2 className="size-6 animate-spin" />
            <span>Loading evaluation history...</span>
          </div>
        ) : isError ? (
          <div className="flex justify-center items-center py-12 text-destructive gap-2">
            <AlertTriangle className="size-6" />
            <span>Failed to load evaluation history.</span>
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <p>No evaluation records found</p>
          </div>
        ) : (
          <Table>
            <TableHeader className="bg-muted/50">
              <TableRow>
                <TableHead>Document / SLM Title</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Submitted</TableHead>
                <TableHead>Completed</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((evalRecord: HistoryEvaluationItem) => (
                <TableRow key={evalRecord.evaluation_id}>
                  <TableCell className="font-medium">
                    <div className="flex flex-col">
                      <span>{evalRecord.document_id}</span>
                      <span className="text-xs font-mono text-muted-foreground">{evalRecord.evaluation_id}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${statusClass(evalRecord.status)}`}>
                      {evalRecord.status.replace('_', ' ')}
                    </span>
                  </TableCell>
                  <TableCell className="text-sm">
                    {new Date(evalRecord.submitted_at).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {evalRecord.completed_at ? new Date(evalRecord.completed_at).toLocaleString() : '—'}
                  </TableCell>
                  <TableCell className="text-right">
                    <Link
                      to="/evaluations/$id"
                      params={{ id: evalRecord.evaluation_id }}
                      className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground h-8 px-3 gap-1.5"
                    >
                      <span>View</span>
                      <ExternalLink className="size-3" />
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <Outlet />
    </section>
  );
}
