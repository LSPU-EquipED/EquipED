import { Outlet } from '@tanstack/react-router';

export function AgentPromptEditor() {
  return (
    <section style={{ display: 'grid', gap: '1rem' }}>
      <div>
        <div style={{ fontSize: '0.75rem', letterSpacing: '0.16em', textTransform: 'uppercase', color: '#8ba4d6' }}>
          Admin
        </div>
        <h1 style={{ margin: '0.35rem 0 0', fontSize: '1.55rem' }}>Prompt editor scaffold</h1>
      </div>

      <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'minmax(0, 1.2fr) minmax(16rem, 0.8fr)' }}>
        <section style={{ borderRadius: '1rem', border: '1px solid rgba(148, 163, 184, 0.14)', background: 'rgba(15, 23, 42, 0.72)', padding: '1rem', display: 'grid', gap: '0.75rem' }}>
          <div style={{ color: '#8ba4d6', fontSize: '0.78rem', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Prompt text</div>
          <textarea defaultValue="Provisional prompt content will live here." rows={10} style={{ width: '100%', borderRadius: '0.85rem', border: '1px solid rgba(148, 163, 184, 0.2)', background: 'rgba(8, 15, 30, 0.95)', color: '#e5eefc', padding: '0.9rem', resize: 'vertical' }} />
          <button type="button" style={{ width: 'fit-content', borderRadius: '999px', border: 'none', background: '#60a5fa', color: '#081120', padding: '0.7rem 1rem', fontWeight: 700 }}>
            Save scaffold
          </button>
        </section>

        <section style={{ borderRadius: '1rem', border: '1px solid rgba(148, 163, 184, 0.14)', background: 'rgba(15, 23, 42, 0.72)', padding: '1rem' }}>
          <div style={{ color: '#8ba4d6', fontSize: '0.78rem', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Version history</div>
          <p style={{ margin: '0.5rem 0 0', color: '#bfd0f7' }}>Prompt versions will appear here once version tracking is wired.</p>
        </section>
      </div>

      <Outlet />
    </section>
  );
}
