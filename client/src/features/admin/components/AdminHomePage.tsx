import { useNavigate } from '@tanstack/react-router';
import { useMemo } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  FileText,
  Loader2,
  Plus,
  Upload,
  Users,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Skeleton } from '@/shared/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table';
import { useAdminSummary } from '@/features/admin/hooks/useAdminSummary';
import { useAdminMatrix } from '@/features/admin/hooks/useAdminMatrix';
import type { MonitoringMatrixRow } from '@/features/admin/types';

function statusClass(status: string) {
  if (status === 'FAILED') return 'border-destructive/50 text-destructive bg-destructive/10';
  if (status.startsWith('COMPLETED')) return 'border-primary/50 text-primary bg-primary/10';
  return 'border-muted-foreground/30 bg-muted/50';
}

export function AdminHomePage() {
  const navigate = useNavigate();
  const { data: summary, isLoading: summaryLoading, isError: summaryError } = useAdminSummary();
  const { data: matrixData, isLoading: matrixLoading, isError: matrixError } = useAdminMatrix({ page_size: 5 });

  const recentActivity = useMemo(() => {
    return matrixData?.items?.slice(0, 5) ?? [];
  }, [matrixData]);

  return (
    <section className="grid gap-8">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">System</p>
        <h1 className="mt-2 text-2xl font-semibold">Admin Dashboard</h1>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          title="Total SLMs"
          value={summary?.total_documents ?? 0}
          icon={FileText}
          isLoading={summaryLoading}
          isError={summaryError}
        />
        <SummaryCard
          title="Active Evaluations"
          value={summary?.active_evaluations ?? 0}
          icon={Loader2}
          isLoading={summaryLoading}
          isError={summaryError}
        />
        <SummaryCard
          title="Registered Faculty"
          value={summary?.total_faculty ?? 0}
          icon={Users}
          isLoading={summaryLoading}
          isError={summaryError}
        />
        <SummaryCard
          title="Failed Evaluations"
          value={summary?.failed_evaluations ?? 0}
          icon={AlertTriangle}
          isLoading={summaryLoading}
          isError={summaryError}
          variant="destructive"
        />
      </div>

      {/* Quick Actions */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card className="hover:bg-muted/30 transition-colors">
          <CardContent className="flex flex-col gap-3 pt-6">
            <div className="flex items-center gap-3">
              <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Plus className="size-5" />
              </div>
              <div>
                <p className="font-medium">Create Faculty Account</p>
                <p className="text-sm text-muted-foreground">Add a new faculty member to the system.</p>
              </div>
            </div>
            <Button
              variant="outline"
              className="w-full justify-between"
              onClick={() => navigate({ to: '/admin/users' })}
            >
              Go to user management
              <ArrowRight className="size-4" />
            </Button>
          </CardContent>
        </Card>

        <Card className="hover:bg-muted/30 transition-colors">
          <CardContent className="flex flex-col gap-3 pt-6">
            <div className="flex items-center gap-3">
              <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Upload className="size-5" />
              </div>
              <div>
                <p className="font-medium">Upload Reference Document</p>
                <p className="text-sm text-muted-foreground">Ingest syllabi, rubrics, or curricula.</p>
              </div>
            </div>
            <Button
              variant="outline"
              className="w-full justify-between"
              onClick={() => navigate({ to: '/admin/ingest' })}
            >
              Go to ingestion
              <ArrowRight className="size-4" />
            </Button>
          </CardContent>
        </Card>

        <Card className="hover:bg-muted/30 transition-colors">
          <CardContent className="flex flex-col gap-3 pt-6">
            <div className="flex items-center gap-3">
              <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <AlertTriangle className="size-5" />
              </div>
              <div>
                <p className="font-medium">Review Failures</p>
                <p className="text-sm text-muted-foreground">Check failed evaluations in the matrix.</p>
              </div>
            </div>
            <Button
              variant="outline"
              className="w-full justify-between"
              onClick={() => navigate({ to: '/matrix' })}
            >
              Open monitoring matrix
              <ArrowRight className="size-4" />
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity */}
      <div>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Recent Activity</p>
            <h2 className="mt-1 text-lg font-semibold">Latest Evaluations</h2>
          </div>
          <Button variant="ghost" size="sm" onClick={() => navigate({ to: '/matrix' })}>
            View all
            <ArrowRight className="ml-1 size-4" />
          </Button>
        </div>

        <div className="mt-4 overflow-hidden rounded-xl border bg-card shadow-sm">
          {matrixLoading ? (
            <div className="space-y-2 p-4">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : matrixError ? (
            <div className="py-10 text-center">
              <p className="text-sm text-destructive font-medium">Unable to load recent activity.</p>
              <p className="text-xs text-muted-foreground mt-1">Please try refreshing the page.</p>
            </div>
          ) : recentActivity.length === 0 ? (
            <div className="py-10 text-center text-muted-foreground">
              <p>No recent evaluation activity.</p>
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
                  <TableHead className="text-right">Updated</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentActivity.map((row: MonitoringMatrixRow) => (
                  <TableRow key={row.evaluation_id}>
                    <TableCell className="font-medium">{row.document_title || 'Untitled SLM'}</TableCell>
                    <TableCell className="text-muted-foreground">{row.program || '—'}</TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${statusClass(row.evaluation_status)}`}>
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
      </div>
    </section>
  );
}

interface SummaryCardProps {
  title: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
  isLoading: boolean;
  isError: boolean;
  variant?: 'default' | 'destructive';
}

function SummaryCard({ title, value, icon: Icon, isLoading, isError, variant = 'default' }: SummaryCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        <Icon className={`size-4 ${variant === 'destructive' ? 'text-destructive' : 'text-muted-foreground'}`} />
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-8 w-16" />
        ) : isError ? (
          <p className="text-sm text-destructive">Failed to load</p>
        ) : (
          <p className={`text-3xl font-bold ${variant === 'destructive' && value > 0 ? 'text-destructive' : ''}`}>
            {value}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
