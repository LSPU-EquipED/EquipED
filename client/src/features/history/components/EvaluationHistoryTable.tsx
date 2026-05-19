import { Outlet } from '@tanstack/react-router';

export function EvaluationHistoryTable() {
  return (
    <section className="grid gap-4">
      <div>
        <div className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          History
        </div>
        <h1 className="mt-1.5 text-2xl font-semibold">Evaluation history scaffold</h1>
      </div>

      <div className="rounded-xl border border-border/40 bg-card/70 p-4 shadow-sm">
        <table className="w-full border-collapse">
          <thead>
            <tr className="text-left text-muted-foreground">
              <th className="pb-3">Title / Document ID</th>
              <th className="pb-3">Status</th>
              <th className="pb-3">Date</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="py-3 text-foreground">No records yet</td>
              <td className="py-3 text-muted-foreground">—</td>
              <td className="py-3 text-muted-foreground">—</td>
            </tr>
          </tbody>
        </table>
      </div>

      <Outlet />
    </section>
  );
}
