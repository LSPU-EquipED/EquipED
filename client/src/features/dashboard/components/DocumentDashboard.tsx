import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link, useLocation, useNavigate } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { ArrowDown, CheckCircle, Folder, Loader2, Search, Upload } from 'lucide-react';
import { dashboardApi } from '@/features/dashboard/api/dashboard.api';
import { getErrorMessage } from '@/shared/api/http';
import { cn } from '@/shared/components/utils';
import type { ClientDocument, DocumentProcessingStatus } from '@/shared/types/documents';

const sourceTypeLabels: Record<ClientDocument['sourceType'], string> = {
  slm: 'SLM',
  syllabus: 'Syllabus',
  rubric_sme: 'SME Rubric',
  rubric_coord: 'Coordinator Rubric',
  rubric_gad: 'GAD Rubric',
  rubric_itso: 'ITSO Rubric',
  curriculum: 'Curriculum',
};

const statusConfig: Record<
  DocumentProcessingStatus,
  { label: string; className: string; icon?: ReactNode }
> = {
  PENDING: {
    label: 'Processing',
    className: 'bg-amber-500 text-white font-semibold text-[10px] tracking-wider uppercase px-2 py-0.5 rounded-sm',
    icon: <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden="true" />,
  },
  PROCESSED: {
    label: 'Ready',
    className: 'bg-emerald-600 text-white font-semibold text-[10px] tracking-wider uppercase px-2 py-0.5 rounded-sm',
  },
  FAILED: {
    label: 'Failed',
    className: 'bg-red-700 text-white font-semibold text-[10px] tracking-wider uppercase px-2 py-0.5 rounded-sm',
  },
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat('en-US', {
    month: '2-digit',
    day: '2-digit',
    year: 'numeric',
  }).format(new Date(value));
}

export function DocumentDashboard() {
  const [search, setSearch] = useState('');
  const navigate = useNavigate();
  const location = useLocation();
  const highlightId = useMemo(() => {
    return new URLSearchParams(location.search).get('highlight');
  }, [location.search]);
  const [flashId, setFlashId] = useState<string | null>(highlightId ?? null);

  const { data, error, isLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: () => dashboardApi.listDocuments(),
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      const hasPending = items.some((d: ClientDocument) => d.processingStatus === 'PENDING');
      return hasPending ? 4000 : false;
    },
  });

  useEffect(() => {
    if (!flashId) return;
    const timer = setTimeout(() => setFlashId(null), 6000);
    return () => clearTimeout(timer);
  }, [flashId]);

  const documents = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    const items = data?.items ?? [];

    if (!normalizedSearch) {
      return items;
    }

    return items.filter((document) => {
      return [document.title, document.program, sourceTypeLabels[document.sourceType]]
        .filter(Boolean)
        .some((value) => value?.toLowerCase().includes(normalizedSearch));
    });
  }, [data?.items, search]);

  const openEvaluationInterface = (documentId: string) => {
    void navigate({
      to: '/documents/$documentId/evaluation',
      params: { documentId },
    });
  };

  return (
    <section className="mx-auto grid w-full max-w-[108rem] gap-7">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Folder className="size-8 fill-foreground text-foreground" aria-hidden="true" />
            <h2 className="text-3xl font-semibold tracking-normal">Documents</h2>
          </div>
          <div className="relative w-full max-w-md">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              className="w-full h-11 border border-slate-200 bg-white pl-11 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-[#1b3b87] rounded-sm transition-shadow placeholder:text-slate-400"
              placeholder="Search title, program, or type"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          <Link
            to="/upload"
            className="inline-flex items-center justify-center bg-[#1b3b87] hover:bg-[#1b3b87]/90 text-white h-11 px-4 rounded-sm text-sm font-semibold tracking-wide uppercase transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]"
          >
            <Upload className="mr-2 size-4" aria-hidden="true" />
            Upload document
          </Link>
        </div>
      </div>

      <div className="border border-slate-200 bg-white rounded-sm">
        {flashId ? (
          <div className="flex items-center gap-2 border-b border-primary/20 bg-primary/5 px-6 py-3 text-sm text-primary">
            <CheckCircle className="size-4" aria-hidden="true" />
            Document uploaded successfully and is now ready in your inventory.
          </div>
        ) : null}

        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-6 py-4 bg-slate-50/50">
          <p className="text-sm font-medium text-slate-600">
            {isLoading && !data
              ? 'Loading documents…'
              : `${data?.total ?? 0} document${(data?.total ?? 0) === 1 ? '' : 's'} available`}
          </p>
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">
            Status reflects upload and preprocessing only.
          </p>
        </div>

        <div className="px-6 py-6">
          {error ? (
            <div className="rounded-sm border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {getErrorMessage(error, 'Unable to load documents.')}
            </div>
          ) : null}

          {!error && !isLoading && documents.length === 0 ? (
            <div className="grid gap-2 rounded-sm border border-dashed border-slate-200 px-6 py-12 text-center">
              <h3 className="text-lg font-semibold text-slate-800">No documents to show</h3>
              <p className="text-sm text-slate-500">
                Upload an SLM or reference document to populate the authenticated inventory.
              </p>
            </div>
          ) : null}

          {!error && documents.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse border-spacing-0">
                <thead className="bg-slate-50 text-slate-600 uppercase text-[11px] tracking-wider font-semibold border-b border-slate-200">
                  <tr>
                    <th className="py-3 px-4 font-semibold text-slate-500 min-w-[22rem]">
                      <span className="inline-flex items-center gap-1">
                        Name <ArrowDown className="size-4 text-slate-400" aria-hidden="true" />
                      </span>
                    </th>
                    <th className="py-3 px-4 font-semibold text-slate-500">Type</th>
                    <th className="py-3 px-4 font-semibold text-slate-500">Program</th>
                    <th className="py-3 px-4 font-semibold text-slate-500">
                      <span className="inline-flex items-center gap-1">
                        Uploaded{' '}
                        <ArrowDown className="size-4 text-slate-400" aria-hidden="true" />
                      </span>
                    </th>
                    <th className="py-3 px-4 font-semibold text-slate-500">Status</th>
                    <th className="py-3 px-4 font-semibold text-slate-500">Pages</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {documents.map((document) => {
                    const isReady = document.processingStatus === 'PROCESSED';
                    const statusMeta = statusConfig[document.processingStatus];
                    const isFlashing = flashId === document.documentId;

                    return (
                      <tr
                        key={document.documentId}
                        className={cn(
                          isFlashing && 'bg-primary/5 ring-1 ring-inset ring-primary/20',
                          isReady &&
                            'group cursor-pointer hover:bg-slate-50/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1b3b87]',
                          !isReady && 'bg-slate-50/20'
                        )}
                        {...(isReady
                          ? {
                              role: 'link',
                              tabIndex: 0,
                              onClick: () => openEvaluationInterface(document.documentId),
                              onKeyDown: (event: React.KeyboardEvent<HTMLTableRowElement>) => {
                                if (event.key === 'Enter' || event.key === ' ') {
                                  event.preventDefault();
                                  openEvaluationInterface(document.documentId);
                                }
                              },
                            }
                          : {})}
                      >
                        <td className="py-3 px-4 text-sm font-semibold text-slate-800 max-w-[22rem] truncate">
                          {isReady ? (
                            <span className="block truncate underline-offset-4 group-hover:underline text-slate-900 group-hover:text-[#1b3b87] transition-colors">
                              {document.title}
                            </span>
                          ) : (
                            <span
                              className="block truncate cursor-not-allowed opacity-60"
                              title={
                                document.processingStatus === 'PENDING'
                                  ? 'Processing in progress — check back shortly.'
                                  : 'Processing failed. The document is not ready for evaluation.'
                              }
                            >
                              {document.title}
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-sm text-slate-600 font-medium">
                          {sourceTypeLabels[document.sourceType]}
                        </td>
                        <td className="py-3 px-4 text-sm text-slate-600 font-medium">
                          {document.program ?? '—'}
                        </td>
                        <td className="py-3 px-4 text-sm text-slate-600 font-medium">
                          {formatDate(document.uploadedAt)}
                        </td>
                        <td className="py-3 px-4 text-sm">
                          <span className={cn('inline-flex items-center', statusMeta.className)}>
                            {statusMeta.icon}
                            {statusMeta.label}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-sm text-slate-600 font-medium">
                          {document.pageCount != null &&
                          !(document.processingStatus === 'FAILED' && document.pageCount === 0)
                            ? document.pageCount
                            : '—'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
