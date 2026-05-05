export function DashboardPage() {
  return (
    <section style={{ display: 'grid', gap: '1rem' }}>
      <div
        style={{
          borderRadius: '1.25rem',
          border: '1px solid rgba(148, 163, 184, 0.16)',
          background: 'rgba(15, 23, 42, 0.78)',
          padding: '1.25rem',
          boxShadow: '0 18px 48px rgba(2, 6, 23, 0.34)',
        }}
      >
        <div style={{ fontSize: '0.75rem', letterSpacing: '0.16em', textTransform: 'uppercase', color: '#8ba4d6' }}>
          Dashboard
        </div>
        <h1 style={{ margin: '0.4rem 0 0', fontSize: '1.55rem' }}>Scaffold overview</h1>
        <p style={{ margin: '0.6rem 0 0', maxWidth: '60ch', color: '#bfd0f7', lineHeight: 1.6 }}>
          This shell is intentionally small: just enough structure to prove routing, layout, and future data placement.
        </p>
      </div>

      <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit, minmax(14rem, 1fr))' }}>
        {['Uploads queued', 'Evaluations running', 'Feedback pending'].map((label) => (
          <article
            key={label}
            style={{
              borderRadius: '1rem',
              border: '1px solid rgba(148, 163, 184, 0.14)',
              background: 'rgba(15, 23, 42, 0.66)',
              padding: '1rem',
            }}
          >
            <div style={{ color: '#8ba4d6', fontSize: '0.78rem', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
              {label}
            </div>
            <div style={{ marginTop: '0.5rem', fontSize: '1.4rem', fontWeight: 700 }}>—</div>
          </article>
        ))}
      </div>
    </section>
  );
}
