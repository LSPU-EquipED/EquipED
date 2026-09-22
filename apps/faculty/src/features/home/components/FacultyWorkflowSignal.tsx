import { ChartBar, CheckCircle, FileText } from "@phosphor-icons/react";

export interface FacultyWorkflowSignalProps {
  title: string;
  description: string;
}

/** A small evidence-path visual for low-data states, so empty space still explains the workflow. */
export function FacultyWorkflowSignal({
  title,
  description,
}: FacultyWorkflowSignalProps) {
  const steps = [
    { label: "Module", Icon: FileText },
    { label: "Review", Icon: ChartBar },
    { label: "Decision", Icon: CheckCircle },
  ];

  return (
    <div className="mx-auto flex max-w-[34rem] flex-col items-center gap-4 py-2 text-center">
      <div
        className="flex w-full items-center justify-center"
        aria-hidden="true"
      >
        {steps.map(({ label, Icon }, index) => (
          <div key={label} className="flex min-w-0 items-center">
            <div className="flex flex-col items-center gap-2">
              <span className="flex size-10 items-center justify-center rounded-sm border border-border-strong bg-surface text-primary">
                <Icon className="size-5" weight="regular" />
              </span>
              <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-text-muted">
                {label}
              </span>
            </div>
            {index < steps.length - 1 ? (
              <span className="mx-3 mb-5 h-px w-12 bg-border-strong sm:w-16" />
            ) : null}
          </div>
        ))}
      </div>
      <div className="space-y-1">
        <p className="text-sm font-semibold text-text">{title}</p>
        <p className="mx-auto max-w-[30rem] text-xs leading-relaxed text-text-muted">
          {description}
        </p>
      </div>
    </div>
  );
}
