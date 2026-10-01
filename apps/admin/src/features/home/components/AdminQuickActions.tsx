import { useNavigate } from '@tanstack/react-router';
import {
  ArrowUpRight,
  Scan,
  Shield,
  UploadSimple,
  Users,
} from '@phosphor-icons/react';

export function AdminQuickActions() {
  const navigate = useNavigate();

  const actions = [
    {
      id: 'create-faculty',
      title: 'User management',
      description: 'Manage faculty accounts and access.',
      icon: Users,
      ariaLabel: 'Create Faculty Account',
      to: '/admin/users',
    },
    {
      id: 'upload-reference',
      title: 'Reference ingestion',
      description: 'Add syllabi, curricula, and rubrics.',
      icon: UploadSimple,
      ariaLabel: 'Upload Reference Document',
      to: '/admin/ingest',
    },
    {
      id: 'model-validation',
      title: 'Model validation',
      description: 'Compare model scores with expert reviews.',
      icon: Scan,
      ariaLabel: 'Validate Model',
      to: '/admin/model-validation',
    },
    {
      id: 'monitoring-matrix',
      title: 'Monitoring matrix',
      description: 'Review specialist scores and flagged findings.',
      icon: Shield,
      ariaLabel: 'Open Matrix',
      to: '/matrix',
    },
  ];

  return (
    <aside aria-label="Administrative launchpads" className="min-w-0 lg:border-l lg:border-border lg:pl-6">
      <section aria-labelledby="admin-launchpads-heading">
        <h2
          id="admin-launchpads-heading"
          className="text-base font-semibold leading-6 text-text"
        >
          Administration
        </h2>
        <div className="mt-3 divide-y divide-border border-y border-border overflow-hidden">
          {actions.map((action) => {
            const Icon = action.icon;
            return (
              <button
                key={action.id}
                type="button"
                aria-label={action.ariaLabel}
                onClick={() => navigate({ to: action.to })}
                className="group flex w-full items-start gap-3 px-4 py-5 text-left transition-colors hover:bg-surface-subtle/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset cursor-pointer"
              >
                <div className="flex size-9 shrink-0 items-center justify-center rounded-xs border border-border/80 bg-surface-subtle/70 text-text-muted transition-colors group-hover:border-border-strong group-hover:bg-surface-subtle group-hover:text-primary">
                  <Icon className="size-4" aria-hidden="true" />
                </div>
                <div className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold leading-5 text-text transition-colors group-hover:text-primary">
                    {action.title}
                  </span>
                  <span className="mt-1 block text-xs leading-5 text-text-muted">
                    {action.description}
                  </span>
                </div>
                <ArrowUpRight
                  className="size-3.5 shrink-0 text-text-muted transition-colors group-hover:text-primary mt-1"
                  aria-hidden="true"
                />
              </button>
            );
          })}
        </div>
      </section>
    </aside>
  );
}
