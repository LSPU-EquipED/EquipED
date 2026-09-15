import { useNavigate } from '@tanstack/react-router';
import {
  CaretRight,
  Scan,
  Shield,
  UploadSimple,
  Users,
} from '@phosphor-icons/react';
import { Button } from '@/shared/components/Button';

export function AdminQuickActions() {
  const navigate = useNavigate();

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {/* Quick Action: Create Faculty Account */}
      <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex size-9 items-center justify-center rounded-sm bg-primary-soft border border-primary/20 text-primary shrink-0">
            <Users className="size-4.5" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-text tracking-tight">Create Faculty Account</h2>
            <p className="text-xs text-text-muted mt-1 leading-relaxed">
              Provision new faculty accounts and manage roles.
            </p>
          </div>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="md"
          aria-label="Create Faculty Account"
          className="group w-full justify-between font-semibold text-xs sm:text-sm h-10 px-3.5 border-border hover:border-primary/50 hover:bg-primary-soft hover:text-primary active:bg-primary-soft/80 transition-colors focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          onClick={() => navigate({ to: '/admin/users' })}
        >
          <span className="truncate whitespace-nowrap">Create Faculty</span>
          <CaretRight className="size-4 shrink-0 text-text-muted group-hover:text-primary transition-colors" aria-hidden="true" />
        </Button>
      </div>

      {/* Quick Action: Upload Reference Document */}
      <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex size-9 items-center justify-center rounded-sm bg-primary-soft border border-primary/20 text-primary shrink-0">
            <UploadSimple className="size-4.5" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-text tracking-tight">Upload Reference Document</h2>
            <p className="text-xs text-text-muted mt-1 leading-relaxed">
              Ingest institutional syllabi, curricula, and approved policy rubrics.
            </p>
          </div>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="md"
          aria-label="Upload Reference Document"
          className="group w-full justify-between font-semibold text-xs sm:text-sm h-10 px-3.5 border-border hover:border-primary/50 hover:bg-primary-soft hover:text-primary active:bg-primary-soft/80 transition-colors focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          onClick={() => navigate({ to: '/admin/ingest' })}
        >
          <span className="truncate whitespace-nowrap">Upload Reference</span>
          <CaretRight className="size-4 shrink-0 text-text-muted group-hover:text-primary transition-colors" aria-hidden="true" />
        </Button>
      </div>

      {/* Quick Action: Model Validation */}
      <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex size-9 items-center justify-center rounded-sm bg-primary-soft border border-primary/20 text-primary shrink-0">
            <Scan className="size-4.5" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-text tracking-tight">Model Validation</h2>
            <p className="text-xs text-text-muted mt-1 leading-relaxed">
              Audit LLM evaluations against human expert ground-truth benchmarks.
            </p>
          </div>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="md"
          aria-label="Validate Model"
          className="group w-full justify-between font-semibold text-xs sm:text-sm h-10 px-3.5 border-border hover:border-primary/50 hover:bg-primary-soft hover:text-primary active:bg-primary-soft/80 transition-colors focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          onClick={() => navigate({ to: '/admin/model-validation' })}
        >
          <span className="truncate whitespace-nowrap">Validate Model</span>
          <CaretRight className="size-4 shrink-0 text-text-muted group-hover:text-primary transition-colors" aria-hidden="true" />
        </Button>
      </div>

      {/* Quick Action: Monitoring Matrix */}
      <div className="rounded-md border border-border bg-surface p-5 flex flex-col justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex size-9 items-center justify-center rounded-sm bg-primary-soft border border-primary/20 text-primary shrink-0">
            <Shield className="size-4.5" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-text tracking-tight">Monitoring Matrix</h2>
            <p className="text-xs text-text-muted mt-1 leading-relaxed">
              Live oversight of multi-agent evaluations, flag counts, and failures.
            </p>
          </div>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="md"
          aria-label="Open Matrix"
          className="group w-full justify-between font-semibold text-xs sm:text-sm h-10 px-3.5 border-border hover:border-primary/50 hover:bg-primary-soft hover:text-primary active:bg-primary-soft/80 transition-colors focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          onClick={() => navigate({ to: '/matrix' })}
        >
          <span className="truncate whitespace-nowrap">Open Matrix</span>
          <CaretRight className="size-4 shrink-0 text-text-muted group-hover:text-primary transition-colors" aria-hidden="true" />
        </Button>
      </div>
    </div>
  );
}
