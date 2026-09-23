import { useNavigate } from '@tanstack/react-router';
import {
  ArrowUpRight,
  Info,
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
      description: 'Provision new faculty accounts and manage roles.',
      icon: Users,
      ariaLabel: 'Create Faculty Account',
      to: '/admin/users',
    },
    {
      id: 'upload-reference',
      title: 'Reference ingestion',
      description: 'Ingest institutional syllabi, curricula, and rubrics.',
      icon: UploadSimple,
      ariaLabel: 'Upload Reference Document',
      to: '/admin/ingest',
    },
    {
      id: 'model-validation',
      title: 'Model validation',
      description: 'Audit evaluations against human expert ground truth.',
      icon: Scan,
      ariaLabel: 'Validate Model',
      to: '/admin/model-validation',
    },
    {
      id: 'monitoring-matrix',
      title: 'Monitoring matrix',
      description: 'Live oversight of multi-agent evaluations and flag counts.',
      icon: Shield,
      ariaLabel: 'Open Matrix',
      to: '/matrix',
    },
  ];

  return (
    <aside aria-label="Administrative launchpads" className="min-w-0 space-y-5 lg:border-l lg:border-border lg:pl-6">
      <section aria-labelledby="admin-launchpads-heading">
        <h2
          id="admin-launchpads-heading"
          className="text-sm font-semibold text-text"
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
                className="group flex w-full items-start gap-3 p-4 text-left transition-colors hover:bg-surface-subtle/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-inset cursor-pointer"
              >
                <div className="flex size-8 shrink-0 items-center justify-center rounded-xs border border-border/80 bg-surface-subtle/70 text-text-muted transition-colors group-hover:border-border-strong group-hover:bg-surface-subtle group-hover:text-text">
                  <Icon className="size-4" aria-hidden="true" />
                </div>
                <div className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold text-text transition-colors group-hover:text-primary">
                    {action.title}
                  </span>
                  <span className="mt-0.5 block text-xs leading-relaxed text-text-muted">
                    {action.description}
                  </span>
                </div>
                <ArrowUpRight
                  className="size-3.5 shrink-0 text-text-muted transition-colors group-hover:text-primary mt-0.5"
                  aria-hidden="true"
                />
              </button>
            );
          })}
        </div>
      </section>

      <div className="border-l-2 border-primary/30 pl-3 text-xs leading-relaxed text-text-muted flex items-start gap-2.5">
        <Info className="size-4 shrink-0 text-text-muted mt-0.5" aria-hidden="true" />
        <span>
          Automated evaluations are advisory. Final decisions remain with institutional reviewers.
        </span>
      </div>
    </aside>
  );
}
