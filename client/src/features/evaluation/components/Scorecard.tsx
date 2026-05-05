import { Outlet } from '@tanstack/react-router';
import { FlagList } from './FlagList';
import { FeedbackPanel } from './FeedbackPanel';

export function Scorecard() {
  return (
    <section style={{ display: 'grid', gap: '1rem' }}>
      <div>
        <div style={{ fontSize: '0.75rem', letterSpacing: '0.16em', textTransform: 'uppercase', color: '#8ba4d6' }}>
          Evaluation
        </div>
        <h1 style={{ margin: '0.35rem 0 0', fontSize: '1.55rem' }}>Scorecard scaffold</h1>
      </div>

      <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit, minmax(12rem, 1fr))' }}>
        {['SME', 'Coordinator', 'GAD', 'ITSO'].map((label) => (
          <article key={label} style={{ borderRadius: '1rem', border: '1px solid rgba(148, 163, 184, 0.14)', background: 'rgba(15, 23, 42, 0.72)', padding: '1rem' }}>
            <div style={{ color: '#8ba4d6', fontSize: '0.78rem', letterSpacing: '0.12em', textTransform: 'uppercase' }}>{label}</div>
            <div style={{ marginTop: '0.5rem', fontSize: '1.4rem', fontWeight: 700 }}>—</div>
          </article>
        ))}
      </div>

      <FlagList />
      <FeedbackPanel />
      <Outlet />
    </section>
  );
}
