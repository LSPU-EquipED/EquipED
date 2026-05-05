import { Outlet } from '@tanstack/react-router';
import { Sidebar } from './Sidebar';

export function AppShell() {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'grid',
        gridTemplateColumns: '18rem minmax(0, 1fr)',
        background: '#0b1020',
        color: '#e5eefc',
      }}
    >
      <Sidebar />

      <div style={{ display: 'flex', minWidth: 0, flexDirection: 'column' }}>
        <header
          style={{
            borderBottom: '1px solid rgba(148, 163, 184, 0.16)',
            background: 'rgba(15, 23, 42, 0.82)',
            padding: '1rem 1.5rem',
            backdropFilter: 'blur(14px)',
          }}
        >
          <div style={{ fontSize: '0.75rem', letterSpacing: '0.16em', textTransform: 'uppercase', color: '#8ba4d6' }}>
            EquipEd shell
          </div>
          <div style={{ marginTop: '0.35rem', fontSize: '1.1rem', fontWeight: 600 }}>
            Provisional routes are wired and navigable.
          </div>
        </header>

        <main style={{ flex: 1, minWidth: 0, padding: '1.5rem' }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
