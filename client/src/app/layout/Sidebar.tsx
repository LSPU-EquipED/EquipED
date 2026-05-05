import { Link } from '@tanstack/react-router';

const navLinkBase = {
  display: 'block',
  borderRadius: '0.85rem',
  padding: '0.8rem 0.95rem',
  textDecoration: 'none',
  transition: 'background-color 160ms ease, color 160ms ease, transform 160ms ease',
};

const navActiveStyle = {
  ...navLinkBase,
  background: 'rgba(96, 165, 250, 0.18)',
  color: '#f8fbff',
};

const navInactiveStyle = {
  ...navLinkBase,
  color: '#bfd0f7',
};

export function Sidebar() {
  return (
    <aside
      style={{
        borderRight: '1px solid rgba(148, 163, 184, 0.16)',
        background: 'linear-gradient(180deg, #0f172a 0%, #111827 100%)',
        padding: '1.25rem',
      }}
    >
      <div style={{ marginBottom: '1.25rem' }}>
        <div style={{ fontSize: '1.05rem', fontWeight: 700, letterSpacing: '0.04em' }}>EquipEd</div>
        <div style={{ marginTop: '0.35rem', color: '#8ba4d6', fontSize: '0.88rem' }}>
          client shell scaffold
        </div>
      </div>

      <nav aria-label="Primary" style={{ display: 'grid', gap: '0.4rem' }}>
        <Link to="/dashboard" activeOptions={{ exact: true }} activeProps={{ style: navActiveStyle }} inactiveProps={{ style: navInactiveStyle }}>
          Dashboard
        </Link>
        <Link to="/upload" activeOptions={{ exact: true }} activeProps={{ style: navActiveStyle }} inactiveProps={{ style: navInactiveStyle }}>
          Upload
        </Link>
        <Link to="/evaluations" activeOptions={{ exact: false }} activeProps={{ style: navActiveStyle }} inactiveProps={{ style: navInactiveStyle }}>
          Evaluations
        </Link>
        <Link to="/matrix" activeOptions={{ exact: true }} activeProps={{ style: navActiveStyle }} inactiveProps={{ style: navInactiveStyle }}>
          Matrix
        </Link>
        <Link to="/admin/prompts" activeOptions={{ exact: false }} activeProps={{ style: navActiveStyle }} inactiveProps={{ style: navInactiveStyle }}>
          Admin
        </Link>
      </nav>

      <div
        style={{
          marginTop: '1.5rem',
          borderRadius: '1rem',
          border: '1px solid rgba(148, 163, 184, 0.14)',
          background: 'rgba(15, 23, 42, 0.72)',
          padding: '1rem',
          color: '#c9d8f6',
          fontSize: '0.9rem',
        }}
      >
        Role gating is provisional; admin and matrix routes will redirect until auth is wired.
      </div>
    </aside>
  );
}
