import { Search, Upload } from 'lucide-react';
import { Link } from '@tanstack/react-router';

interface DocumentActionBarProps {
  search: string;
  setSearch: (val: string) => void;
}

export function DocumentActionBar({ search, setSearch }: DocumentActionBarProps) {
  return (
    <div className="flex items-center gap-4 border-b border-slate-200 bg-slate-50/50 px-6 md:px-8 py-3">
      <div className="relative flex-1">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500"
          aria-hidden="true"
        />
        <input
          type="text"
          className="w-full h-10 border border-slate-200 bg-white pl-9 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-[#1b3b87] rounded-sm placeholder:text-slate-600 font-medium"
          placeholder="Search title, course, program…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search documents"
        />
      </div>
      <Link
        to="/upload"
        className="inline-flex items-center gap-2 bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white h-10 px-4 rounded-sm text-xs font-bold tracking-wider uppercase transition-colors shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
      >
        <Upload className="size-3.5" aria-hidden="true" />
        Upload SLM
      </Link>
    </div>
  );
}
