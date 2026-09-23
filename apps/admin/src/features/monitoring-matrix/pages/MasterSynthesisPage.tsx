import { useState } from 'react';
import { Link, useParams } from '@tanstack/react-router';
import {
  ArrowLeft,
  Calendar,
  Printer,
  WarningCircle,
} from '@phosphor-icons/react';
import { Badge, Button, Skeleton, getEvaluationStatusVariant } from '@equiped/ui';
import { SpecialistInspectionPanel } from '../components/SpecialistInspectionPanel';
import { SynthesisOverviewRail } from '../components/SynthesisOverviewRail';
import { useMasterSynthesisDetail } from '../hooks/useMasterSynthesisDetail';
import type { TargetDomainId } from '../utils';

export function MasterSynthesisPage() {
  const { documentId } = useParams({ strict: false }) as { documentId?: string };
  const { data, isLoading, isError, refetch } = useMasterSynthesisDetail(documentId ?? '');

  const [activeTab, setActiveTab] = useState<TargetDomainId>('sme');

  const activePillar = data?.pillars?.[activeTab];

  const handlePrint = () => {
    window.print();
  };

  if (isLoading) {
    return (
      <div className="px-4 sm:px-7 py-6 sm:py-8 max-w-[108rem] mx-auto space-y-6" data-testid="master-synthesis-loading">
        <div className="flex items-center justify-between border-b border-border pb-4">
          <div className="space-y-2">
            <Skeleton className="h-4 w-36" />
            <Skeleton className="h-8 w-72" />
            <Skeleton className="h-4 w-48" />
          </div>
          <Skeleton className="h-9 w-44" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-[22rem_minmax(0,1fr)] gap-6">
          <div className="space-y-4">
            <Skeleton className="h-40 w-full rounded-md" />
            <Skeleton className="h-96 w-full rounded-md" />
          </div>
          <div className="space-y-4">
            <Skeleton className="h-48 w-full rounded-md" />
            <Skeleton className="h-80 w-full rounded-md" />
          </div>
        </div>
        <Skeleton className="h-48 w-full rounded-md" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="px-4 sm:px-6 py-12 max-w-4xl mx-auto" data-testid="master-synthesis-error">
        <div className="rounded-md border border-destructive/20 bg-destructive-soft p-6 text-center space-y-4">
          <WarningCircle className="size-10 text-destructive mx-auto" aria-hidden="true" />
          <h2 className="text-lg font-bold text-destructive">Unable to Load Master Synthesis Scorecard</h2>
          <p className="text-sm text-text-muted max-w-md mx-auto">
            The requested document synthesis record could not be retrieved. Please check network connectivity or verify the document ID.
          </p>
          <div className="flex justify-center gap-3 pt-2">
            <Link
              to="/matrix"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xs border border-border bg-surface text-xs font-semibold text-text hover:bg-surface-subtle cursor-pointer"
            >
              <ArrowLeft className="size-4" />
              <span>Back to Monitoring Matrix</span>
            </Link>
            <Button type="button" variant="primary" size="sm" onClick={() => refetch()}>
              Retry
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[108rem] space-y-4 px-4 py-5 sm:px-7 sm:py-6" data-testid="master-synthesis-scorecard">
      {/* ── Executive Header: Navigation & Document Metadata ── */}
      <header className="space-y-3 border-b border-border pb-4">
        {/* Top Row: Title & Badges (Left) vs Back & Export Actions (Right) */}
        <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
          <div className="min-w-0 flex-1 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              {data.program ? (
                <span className="inline-flex items-center rounded-xs border border-primary/20 bg-primary-soft px-2 py-0.5 text-[11px] font-semibold text-primary">
                  {data.program}
                </span>
              ) : null}
              {data.course_code ? (
                <span className="inline-flex items-center rounded-xs border border-border bg-surface-subtle px-2 py-0.5 text-[11px] font-semibold text-text">
                  Course: {data.course_code}
                </span>
              ) : null}
              <Badge variant={getEvaluationStatusVariant(data.evaluation_status)} withDot>
                {data.evaluation_status.replace(/_/g, ' ')}
              </Badge>
            </div>

            <h1 className="break-words text-xl font-semibold leading-tight text-text [overflow-wrap:anywhere] sm:text-2xl">
              {data.document_title || 'Untitled SLM Module'}
            </h1>

            <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted">
              <span className="flex items-center gap-1">
                <Calendar className="size-3.5 text-text-muted shrink-0" aria-hidden="true" />
                <span>Last Updated: {data.last_updated ? new Date(data.last_updated).toLocaleString() : '—'}</span>
              </span>
            </p>
          </div>

          <div className="flex shrink-0 items-center gap-2 self-start sm:self-center">
            <Link
              to="/matrix"
              className="inline-flex h-9 items-center gap-1.5 rounded-xs border border-border bg-surface px-3 text-xs font-semibold text-text transition-colors hover:bg-surface-subtle focus-visible:outline-2 focus-visible:outline-ring"
              data-testid="back-to-matrix-link"
            >
              <ArrowLeft className="size-3.5" aria-hidden="true" />
              <span className="hidden sm:inline">Back to Monitoring Matrix</span>
            </Link>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handlePrint}
              className="h-9 gap-1.5 text-xs font-semibold"
              data-testid="export-pdf-button"
            >
              <Printer className="size-4" aria-hidden="true" />
              <span className="hidden sm:inline">Export PDF</span>
            </Button>
          </div>
        </div>

      </header>

      {/* ── Two-Column Workbench Split ─────────────────────────────────── */}
      <div className="grid min-w-0 items-start gap-5 lg:grid-cols-[20rem_minmax(0,1fr)] xl:grid-cols-[22rem_minmax(0,1fr)]">
        {/* ── LEFT COLUMN: Master Synthesis Rail (Overview & Navigation) ── */}
        <SynthesisOverviewRail
          data={data}
          activePillarId={activeTab}
          onSelectPillar={setActiveTab}
        />

        {/* ── RIGHT COLUMN: Specialist Inspection Canvas ────────────────── */}
        <SpecialistInspectionPanel
          activePillarId={activeTab}
          pillar={activePillar}
          flags={data.flags}
        />
      </div>
    </div>
  );
}

export default MasterSynthesisPage;
