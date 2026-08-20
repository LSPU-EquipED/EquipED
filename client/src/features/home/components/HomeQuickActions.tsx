import { Link } from '@tanstack/react-router';
import {
  ArrowRight,
  ClipboardList,
  FolderOpen,
  ListChecks,
  Upload,
} from 'lucide-react';

export function HomeQuickActions() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {/* Upload SLM (Primary) */}
      <div className="rounded-sm border border-slate-200 bg-white p-5 flex flex-col justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex size-10 items-center justify-center rounded-sm border border-[#1b3b87]/30 bg-[#1b3b87]/10 text-[#1b3b87] shrink-0">
            <Upload className="size-5" aria-hidden="true" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">Upload SLM</h3>
            <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">
              Submit a learning module for automated evaluation.
            </p>
          </div>
        </div>
        <Link
          to="/upload"
          className="inline-flex h-9 w-full items-center justify-between rounded-sm bg-[#1b3b87] px-3 text-xs font-bold uppercase tracking-wider text-white hover:bg-[#1b3b87]/90 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
        >
          <span>Upload Material</span>
          <ArrowRight className="size-3.5" aria-hidden="true" />
        </Link>
      </div>

      {/* My SLMs */}
      <div className="rounded-sm border border-slate-200 bg-white p-5 flex flex-col justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex size-10 items-center justify-center rounded-sm border border-slate-200 bg-slate-50 text-slate-700 shrink-0">
            <FolderOpen className="size-5" aria-hidden="true" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">My SLMs</h3>
            <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">
              View uploaded modules and start evaluations.
            </p>
          </div>
        </div>
        <Link
          to="/documents"
          className="inline-flex h-9 w-full items-center justify-between rounded-sm border border-slate-200 bg-white px-3 text-xs font-bold uppercase tracking-wider text-slate-700 hover:bg-slate-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
        >
          <span>Open My SLMs</span>
          <ArrowRight className="size-3.5 text-slate-500" aria-hidden="true" />
        </Link>
      </div>

      {/* Evaluations */}
      <div className="rounded-sm border border-slate-200 bg-white p-5 flex flex-col justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex size-10 items-center justify-center rounded-sm border border-slate-200 bg-slate-50 text-slate-700 shrink-0">
            <ClipboardList className="size-5" aria-hidden="true" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">Evaluations</h3>
            <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">
              Review completed scorecards and reports.
            </p>
          </div>
        </div>
        <Link
          to="/evaluations"
          className="inline-flex h-9 w-full items-center justify-between rounded-sm border border-slate-200 bg-white px-3 text-xs font-bold uppercase tracking-wider text-slate-700 hover:bg-slate-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
        >
          <span>View All Evaluations</span>
          <ArrowRight className="size-3.5 text-slate-500" aria-hidden="true" />
        </Link>
      </div>

      {/* Alignment Tools */}
      <div className="rounded-sm border border-slate-200 bg-white p-5 flex flex-col justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex size-10 items-center justify-center rounded-sm border border-slate-200 bg-slate-50 text-slate-700 shrink-0">
            <ListChecks className="size-5" aria-hidden="true" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">Syllabus Alignment</h3>
            <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">
              Check module coverage against syllabus outcomes.
            </p>
          </div>
        </div>
        <Link
          to="/syllabus-alignment"
          className="inline-flex h-9 w-full items-center justify-between rounded-sm border border-slate-200 bg-white px-3 text-xs font-bold uppercase tracking-wider text-slate-700 hover:bg-slate-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
        >
          <span>Check Alignment</span>
          <ArrowRight className="size-3.5 text-slate-500" aria-hidden="true" />
        </Link>
      </div>
    </div>
  );
}
