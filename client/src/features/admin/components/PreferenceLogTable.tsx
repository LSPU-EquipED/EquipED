import { Loader2 } from 'lucide-react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/shared/components/ui/table';
import { usePreferenceLogs } from '../hooks/usePreferenceLogs';
import type { PreferenceLogItem } from '../types';

function actionClass(action: string) {
  return action === 'EDITED' ? 'border-primary/50 text-primary bg-primary/10' : 'border-muted-foreground/30 bg-muted/50';
}

export function PreferenceLogTable() {
  const { data, isLoading, isError } = usePreferenceLogs();

  return (
    <section className="grid gap-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Admin</p>
        <h1 className="mt-2 text-2xl font-semibold">Preference logs</h1>
      </div>

      <div className="overflow-hidden rounded-xl border bg-card shadow-sm">
        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-10 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" /> Loading preference logs...
          </div>
        ) : isError ? (
          <div className="py-10 text-center text-destructive">Failed to load preference logs.</div>
        ) : !data?.items.length ? (
          <div className="py-10 text-center text-muted-foreground">No preference logs yet.</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Evaluation</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((log: PreferenceLogItem) => (
                <TableRow key={log.log_id}>
                  <TableCell className="font-mono text-sm">{log.user_id}</TableCell>
                  <TableCell>
                    <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${actionClass(log.action)}`}>
                      {log.action}
                    </span>
                  </TableCell>
                  <TableCell className="font-mono text-sm">{log.evaluation_id}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{new Date(log.created_at).toLocaleString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </section>
  );
}
