export function FeedbackPanel() {
  return (
    <section style={{ borderRadius: '1rem', border: '1px solid rgba(148, 163, 184, 0.14)', background: 'rgba(15, 23, 42, 0.72)', padding: '1rem', display: 'grid', gap: '0.75rem' }}>
      <div style={{ color: '#8ba4d6', fontSize: '0.78rem', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Feedback</div>
      <div style={{ color: '#bfd0f7' }}>Accept / Reject / Edit controls are deferred until feedback wiring lands.</div>
      <button type="button" style={{ width: 'fit-content', borderRadius: '999px', border: 'none', background: '#60a5fa', color: '#081120', padding: '0.7rem 1rem', fontWeight: 700 }}>
        Provisional action
      </button>
    </section>
  );
}
