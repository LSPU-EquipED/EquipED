export function ReportView() {
  return (
    <section style={{ borderRadius: '1rem', border: '1px solid rgba(148, 163, 184, 0.14)', background: 'rgba(15, 23, 42, 0.72)', padding: '1rem', display: 'grid', gap: '0.75rem' }}>
      <div style={{ color: '#8ba4d6', fontSize: '0.78rem', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Report</div>
      <h2 style={{ margin: 0, fontSize: '1.2rem' }}>Printable report scaffold</h2>
      <p style={{ margin: 0, color: '#bfd0f7' }}>This route will eventually combine the scorecard, flags, and summary into a submission-ready report.</p>
    </section>
  );
}
