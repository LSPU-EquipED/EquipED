interface UploadHeaderProps {
  title: string;
}

export function UploadHeader({ title }: UploadHeaderProps) {
  return (
    <div className="flex min-h-16 flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3 sm:px-6 bg-slate-50/50">
      <div className="min-w-0">
        <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">
          Document Workspace
        </p>
        <h2 className="truncate text-sm font-bold text-slate-900 mt-0.5">
          {title.trim() || 'Untitled document upload'}
        </h2>
      </div>
      <div className="rounded-sm bg-slate-100 border border-slate-200 px-3 py-1 text-xs font-bold uppercase tracking-wide text-slate-500">
        Upload only • evaluation later
      </div>
    </div>
  );
}
