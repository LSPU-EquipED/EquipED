export function LoginForm() {
  return (
    <section style={{ maxWidth: '28rem', display: 'grid', gap: '1rem' }}>
      <div>
        <div style={{ fontSize: '0.75rem', letterSpacing: '0.16em', textTransform: 'uppercase', color: '#8ba4d6' }}>
          Sign in
        </div>
        <h1 style={{ margin: '0.35rem 0 0', fontSize: '1.55rem' }}>Auth scaffold</h1>
      </div>

      <div style={{ borderRadius: '1rem', border: '1px solid rgba(148, 163, 184, 0.14)', background: 'rgba(15, 23, 42, 0.72)', padding: '1rem', display: 'grid', gap: '0.9rem' }}>
        <label style={{ display: 'grid', gap: '0.4rem' }}>
          <span style={{ color: '#bfd0f7' }}>Email</span>
          <input type="email" placeholder="name@lspu.edu.ph" style={{ borderRadius: '0.75rem', border: '1px solid rgba(148, 163, 184, 0.2)', background: 'rgba(8, 15, 30, 0.95)', color: '#e5eefc', padding: '0.75rem 0.9rem' }} />
        </label>

        <label style={{ display: 'grid', gap: '0.4rem' }}>
          <span style={{ color: '#bfd0f7' }}>Password</span>
          <input type="password" placeholder="••••••••" style={{ borderRadius: '0.75rem', border: '1px solid rgba(148, 163, 184, 0.2)', background: 'rgba(8, 15, 30, 0.95)', color: '#e5eefc', padding: '0.75rem 0.9rem' }} />
        </label>

        <button type="button" style={{ width: 'fit-content', borderRadius: '999px', border: 'none', background: '#60a5fa', color: '#081120', padding: '0.75rem 1.1rem', fontWeight: 700 }}>
          Continue
        </button>
      </div>
    </section>
  );
}
