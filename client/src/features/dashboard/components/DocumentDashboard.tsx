import { useEffect, useMemo, useState } from 'react';
import { Link } from '@tanstack/react-router';
import { ArrowDown, FileText, Folder, Search, Upload } from 'lucide-react';
import { dashboardApi } from '@/features/dashboard/api/dashboard.api';
import { getErrorMessage } from '@/shared/api/http';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { useFetch } from '@/shared/hooks/useFetch';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table';
import type { ClientDocument } from '@/shared/types/documents';

const sourceTypeLabels: Record<ClientDocument['sourceType'], string> = {
  slm: 'SLM',
  syllabus: 'Syllabus',
  rubric_sme: 'SME Rubric',
  rubric_coord: 'Coordinator Rubric',
  rubric_gad: 'GAD Rubric',
  rubric_itso: 'ITSO Rubric',
  curriculum: 'Curriculum',
};

const processingStatusClasses: Record<ClientDocument['processingStatus'], string> = {
  PROCESSED: 'bg-emerald-100 text-emerald-800',
  PENDING: 'bg-amber-100 text-amber-800',
  FAILED: 'bg-rose-100 text-rose-800',
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
  const { data, error, isLoading, execute } = useFetch(dashboardApi.listDocuments);

  useEffect(() => {
    void execute();
  }, [execute]);

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
          <Button variant="outline" className="h-11 gap-2 px-4" asChild>
            <Link to="/upload">
              <FileText className="size-4" aria-hidden="true" />
              Open upload workspace
            </Link>
          </Button>
          <Button className="h-11 gap-2 px-4" asChild>
            <Link to="/upload">
              <Upload className="size-4" aria-hidden="true" />
              Upload document
            </Link>
          </Button>
        </div>
      </div>

      <Card className="rounded-lg py-0">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b px-6 py-5">
          <p className="text-sm text-muted-foreground">
            {isLoading && !data ? 'Loading documents…' : `${data?.total ?? 0} document${(data?.total ?? 0) === 1 ? '' : 's'} available`}
          </p>
          <p className="text-sm text-muted-foreground">Status reflects upload and preprocessing only.</p>
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
                      Uploaded <ArrowDown className="size-4 text-muted-foreground" aria-hidden="true" />
                    </span>
                  </TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Pages</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {documents.map((document) => (
                  <TableRow key={document.documentId}>
                    <TableCell className="max-w-[22rem] truncate font-medium">{document.title}</TableCell>
                    <TableCell>{sourceTypeLabels[document.sourceType]}</TableCell>
                    <TableCell>{document.program ?? '—'}</TableCell>
                    <TableCell>{formatDate(document.uploadedAt)}</TableCell>
                    <TableCell>
                      <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${processingStatusClasses[document.processingStatus]}`}>
                        {document.processingStatus}
                      </span>
                    </TableCell>
                    <TableCell>{document.pageCount ?? '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : null}
        </CardContent>
      </Card>
    </section>
  );
}
