import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link, useLocation, useNavigate } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { ArrowDown, CheckCircle, Folder, Loader2, Search, Upload } from 'lucide-react';
import { dashboardApi } from '@/features/dashboard/api/dashboard.api';
import { getErrorMessage } from '@/shared/api/http';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip';
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
    label: 'Processing…',
    className: 'bg-amber-100 text-amber-800',
    icon: <Loader2 className="mr-1 size-3 animate-spin" aria-hidden="true" />,
  },
  PROCESSED: {
    label: 'Ready',
    className: 'bg-emerald-100 text-emerald-800',
  },
  FAILED: {
    label: 'Processing failed',
    className: 'bg-rose-100 text-rose-800',
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
            <Input
              className="h-12 rounded-lg bg-card pl-11 text-base"
              placeholder="Search title, program, or type"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          <Button className="h-11 gap-2 px-4" asChild>
            <Link to="/upload">
              <Upload className="size-4" aria-hidden="true" />
              Upload document
            </Link>
          </Button>
        </div>
      </div>

      <Card className="rounded-lg py-0">
        {flashId ? (
          <div className="flex items-center gap-2 border-b border-primary/20 bg-primary/5 px-6 py-3 text-sm text-primary">
            <CheckCircle className="size-4" aria-hidden="true" />
            Document uploaded successfully and is now ready in your inventory.
          </div>
        ) : null}

        <div className="flex flex-wrap items-center justify-between gap-3 border-b px-6 py-5">
          <p className="text-sm text-muted-foreground">
            {isLoading && !data
              ? 'Loading documents…'
              : `${data?.total ?? 0} document${(data?.total ?? 0) === 1 ? '' : 's'} available`}
          </p>
          <p className="text-sm text-muted-foreground">
            Status reflects upload and preprocessing only.
          </p>
        </div>

        <CardContent className="px-6 py-7">
          {error ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {getErrorMessage(error, 'Unable to load documents.')}
            </div>
          ) : null}

          {!error && !isLoading && documents.length === 0 ? (
            <div className="grid gap-2 rounded-lg border border-dashed border-border px-6 py-12 text-center">
              <h3 className="text-lg font-semibold">No documents to show</h3>
              <p className="text-sm text-muted-foreground">
                Upload an SLM or reference document to populate the authenticated inventory.
              </p>
            </div>
          ) : null}

          {!error && documents.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="min-w-[22rem]">
                    <span className="inline-flex items-center gap-1">
                      Name <ArrowDown className="size-4 text-muted-foreground" aria-hidden="true" />
                    </span>
                  </TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Program</TableHead>
                  <TableHead>
                    <span className="inline-flex items-center gap-1">
                      Uploaded{' '}
                      <ArrowDown className="size-4 text-muted-foreground" aria-hidden="true" />
                    </span>
                  </TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Pages</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {documents.map((document) => {
                  const isReady = document.processingStatus === 'PROCESSED';
                  const statusMeta = statusConfig[document.processingStatus];
                  const isFlashing = flashId === document.documentId;

                  return (
                    <TableRow
                      key={document.documentId}
                      className={cn(
                        isFlashing && 'bg-primary/5 ring-1 ring-inset ring-primary/20',
                        isReady &&
                          'group cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
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
                      <TableCell className="max-w-[22rem] truncate font-medium">
                        {isReady ? (
                          <span className="block truncate underline-offset-4 group-hover:underline">
                            {document.title}
                          </span>
                        ) : (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="block truncate cursor-not-allowed opacity-80">
                                {document.title}
                              </span>
                            </TooltipTrigger>
                            <TooltipContent side="top">
                              {document.processingStatus === 'PENDING'
                                ? 'Processing in progress — check back shortly.'
                                : 'Processing failed. The document is not ready for evaluation.'}
                            </TooltipContent>
                          </Tooltip>
                        )}
                      </TableCell>
                      <TableCell>{sourceTypeLabels[document.sourceType]}</TableCell>
                      <TableCell>{document.program ?? '—'}</TableCell>
                      <TableCell>{formatDate(document.uploadedAt)}</TableCell>
                      <TableCell>
                        <span
                          className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${statusMeta.className}`}
                        >
                          {statusMeta.icon}
                          {statusMeta.label}
                        </span>
                      </TableCell>
                      <TableCell>
                        {document.pageCount != null &&
                        !(document.processingStatus === 'FAILED' && document.pageCount === 0)
                          ? document.pageCount
                          : '—'}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          ) : null}
        </CardContent>
      </Card>
    </section>
  );
}
