import { Outlet } from '@tanstack/react-router';

export function EvaluationHistoryTable() {
  return (
    <section style={{ display: 'grid', gap: '1rem' }}>
      <div>
        <div style={{ fontSize: '0.75rem', letterSpacing: '0.16em', textTransform: 'uppercase', color: '#8ba4d6' }}>
          History
        </div>
        <h1 style={{ margin: '0.35rem 0 0', fontSize: '1.55rem' }}>Evaluation history scaffold</h1>
      </div>

      <div style={{ borderRadius: '1rem', border: '1px solid rgba(148, 163, 184, 0.14)', background: 'rgba(15, 23, 42, 0.72)', padding: '1rem' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ textAlign: 'left', color: '#8ba4d6' }}>
              <th style={{ paddingBottom: '0.75rem' }}>Title</th>
              <th style={{ paddingBottom: '0.75rem' }}>Status</th>
              <th style={{ paddingBottom: '0.75rem' }}>Score</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={{ padding: '0.7rem 0', color: '#e5eefc' }}>No records yet</td>
              <td style={{ padding: '0.7rem 0', color: '#bfd0f7' }}>—</td>
              <td style={{ padding: '0.7rem 0', color: '#bfd0f7' }}>—</td>
            </tr>
          </tbody>
        </table>
      </div>

      <Outlet />
    </section>
  );
}
