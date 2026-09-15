import { useMemo, useState } from 'react';
import { Link, useParams } from '@tanstack/react-router';
import {
  ArrowLeft,
  Calendar,
  Certificate,
  CheckCircle,
  Clock,
  Printer,
  SealCheck,
  ShieldCheck,
  Warning,
  WarningCircle,
} from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/Card';
import { Skeleton } from '@/shared/components/Skeleton';
import { cn } from '@/shared/components/utils';
import { TYPOGRAPHY } from '@/shared/constants/theme';
import { useMasterSynthesisDetail } from '../hooks/useMasterSynthesisDetail';
import type { MasterSynthesisPillar } from '../types';
import {
  formatDomainScore,
  getRatingVariant,
  getStatusVariant,
  TARGET_DOMAIN_ORDER,
  type TargetDomainId,
} from '../utils';

interface PillarConfig {
  id: TargetDomainId;
  label: string;
  roleTitle: string;
  weightPercent: string;
  weightDecimal: number;
  description: string;
}

const PILLAR_CONFIGS: Record<TargetDomainId, PillarConfig> = {
  sme: {
    id: 'sme',
    label: 'Content Accuracy',
    roleTitle: 'Subject Matter Expert (SME)',
    weightPercent: '35%',
    weightDecimal: 0.35,
    description: 'Evaluation of domain terminology, concept depth, pedagogical validity, and topical accuracy.',
  },
  coordinator: {
    id: 'coordinator',
    label: 'Curriculum Alignment',
    roleTitle: 'Program Coordinator (PC)',
    weightPercent: '30%',
    weightDecimal: 0.30,
    description: 'Alignment with institutional syllabus, course learning outcomes (CLOs), and credit schedule.',
  },
  gad: {
    id: 'gad',
    label: 'Gender & Inclusivity',
    roleTitle: 'GAD Specialist',
    weightPercent: '20%',
    weightDecimal: 0.20,
    description: 'Gender-fair language, non-discriminatory framing, cultural sensitivity, and Universal Design.',
  },
  itso: {
    id: 'itso',
    label: 'Citations & IP',
    roleTitle: 'ITSO Specialist',
    weightPercent: '15%',
    weightDecimal: 0.15,
    description: 'Copyright compliance, fair use citations, intellectual property attribution, and plagiarism prevention.',
  },
};

export function MasterSynthesisPage() {
  const { documentId } = useParams({ strict: false }) as { documentId?: string };
  const { data, isLoading, isError, refetch } = useMasterSynthesisDetail(documentId ?? '');

  const [activeTab, setActiveTab] = useState<TargetDomainId>('sme');
  const [certified, setCertified] = useState(false);

  // Completed pillars count
  const completedPillarsCount = useMemo(() => {
    if (!data?.pillars) return 0;
    return TARGET_DOMAIN_ORDER.filter((key) => {
      const p = data.pillars[key];
      return p && (p.status === 'COMPLETED' || (p.subtotal !== null && p.subtotal !== undefined));
    }).length;
  }, [data]);

  const activePillar: MasterSynthesisPillar | undefined = data?.pillars?.[activeTab];
  const activePillarConfig = PILLAR_CONFIGS[activeTab];
  // Flags for the active pillar
  const flags = data?.flags;
  const activePillarFlags = useMemo(() => {
    if (!flags) return [];
    return flags.filter(
      (f) => f.agent_id?.toLowerCase() === activeTab || f.agent_id?.toLowerCase() === activePillarConfig.id,
    );
  }, [flags, activeTab, activePillarConfig.id]);

  const handlePrint = () => {
    window.print();
  };

  if (isLoading) {
    return (
      <div className="px-4 sm:px-6 py-8 max-w-[108rem] mx-auto space-y-8" data-testid="master-synthesis-loading">
        <div className="flex items-center gap-3">
          <Skeleton className="h-9 w-32" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <Skeleton className="h-8 w-3/4" />
            <Skeleton className="h-5 w-1/2" />
          </div>
          <Skeleton className="h-28 w-full rounded-md" />
        </div>
        <Skeleton className="h-32 w-full rounded-md" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Skeleton className="h-44 rounded-md" />
          <Skeleton className="h-44 rounded-md" />
          <Skeleton className="h-44 rounded-md" />
          <Skeleton className="h-44 rounded-md" />
        </div>
        <Skeleton className="h-72 w-full rounded-md" />
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
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xs border border-border bg-surface text-xs font-semibold text-text hover:bg-surface-subtle"
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
    <div className="px-4 sm:px-6 py-8 max-w-[108rem] mx-auto space-y-8" data-testid="master-synthesis-scorecard">
      {/* ── Top Bar & Breadcrumb Navigation ────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border pb-4">
        <Link
          to="/matrix"
          className="inline-flex items-center gap-2 text-xs font-semibold text-text-muted hover:text-text transition-colors"
          data-testid="back-to-matrix-link"
        >
          <ArrowLeft className="size-4" />
          <span>Back to Monitoring Matrix</span>
        </Link>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-text-muted">Doc ID: {data.document_id}</span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handlePrint}
            className="gap-1.5 h-8 text-xs font-semibold"
            data-testid="export-pdf-button"
          >
            <Printer className="size-4" />
            <span>Export Accreditation PDF</span>
          </Button>
        </div>
      </div>

      {/* ── Executive Header: Document Metadata ──────────────────────────── */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2.5">
          {data.program ? (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-xs text-xs font-bold uppercase tracking-wider bg-primary-soft text-primary border border-primary/20">
              {data.program}
            </span>
          ) : null}
          {data.course_code ? (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-xs text-xs font-bold uppercase tracking-wider bg-surface-subtle text-text border border-border">
              Course: {data.course_code}
            </span>
          ) : null}
          <Badge variant={getStatusVariant(data.evaluation_status)} withDot>
            {data.evaluation_status.replace(/_/g, ' ')}
          </Badge>
        </div>

        <h1 className={cn(TYPOGRAPHY.display, 'text-2xl sm:text-3xl text-text font-extrabold tracking-tight')}>
          {data.document_title || 'Untitled SLM Module'}
        </h1>
        <p className="text-xs text-text-muted flex items-center gap-2">
          <Calendar className="size-3.5 text-text-muted shrink-0" />
          <span>Last Updated: {data.last_updated ? new Date(data.last_updated).toLocaleString() : '—'}</span>
        </p>
      </div>

      {/* ── Overall Composite Score Banner ─────────────────────────────── */}
      <Card
        className="border border-border bg-linear-to-r from-surface to-surface-subtle/80 shadow-xs"
        data-testid="composite-score-banner"
      >
        <CardContent className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-center">
            {/* Left side: Synthesized Score & Rating */}
            <div className="md:col-span-5 space-y-1.5 border-b md:border-b-0 md:border-r border-border pb-4 md:pb-0 md:pr-6">
              <span className="text-[11px] font-bold uppercase tracking-wider text-text-muted">
                Master Synthesized Score
              </span>
              <div className="flex items-baseline gap-3">
                <span className="text-4xl sm:text-5xl font-extrabold tabular-nums tracking-tight text-text">
                  {data.synthesized_score !== null && data.synthesized_score !== undefined
                    ? data.synthesized_score.toFixed(2)
                    : '—'}
                </span>
                <span className="text-base font-semibold text-text-muted">/ 4.00</span>
                {data.adjectival_rating ? (
                  <Badge variant={getRatingVariant(data.adjectival_rating)} className="text-xs px-2.5 py-1 font-bold">
                    {data.adjectival_rating}
                  </Badge>
                ) : null}
              </div>
              <p className="text-xs text-text-muted">
                Governed by weighted multi-pillar specialist evaluation matrix.
              </p>
            </div>

            {/* Middle: Pillar Progress & Convergence */}
            <div className="md:col-span-4 space-y-2 border-b md:border-b-0 md:border-r border-border pb-4 md:pb-0 md:pr-6">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-text">Pillar Convergence</span>
                <span
                  className={cn(
                    'inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold',
                    completedPillarsCount === 4
                      ? 'bg-success-soft text-success border border-success/30'
                      : 'bg-warning-soft text-warning border border-warning/30',
                  )}
                  data-testid="pillar-progress-pill"
                >
                  {completedPillarsCount}/4 Pillars Complete
                </span>
              </div>
              <div className="w-full bg-border rounded-full h-2.5 overflow-hidden">
                <div
                  className={cn(
                    'h-full transition-all duration-500',
                    completedPillarsCount === 4 ? 'bg-success' : 'bg-primary',
                  )}
                  style={{ width: `${(completedPillarsCount / 4) * 100}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-[11px] text-text-muted">
                <span>Verification State:</span>
                <span className="font-semibold text-text">
                  {completedPillarsCount === 4 ? 'All specialists converged' : `${4 - completedPillarsCount} desk(s) pending`}
                </span>
              </div>
            </div>

            {/* Right: Accreditation Eligibility */}
            <div className="md:col-span-3 flex flex-col items-start md:items-end justify-center space-y-1.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-text-muted">
                Accreditation Status
              </span>
              {data.can_certify ? (
                <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs bg-success-soft border border-success/30 text-success text-xs font-bold">
                  <ShieldCheck className="size-4" />
                  <span>Eligible for Certification</span>
                </div>
              ) : (
                <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs bg-surface-subtle border border-border text-text-muted text-xs font-semibold">
                  <Clock className="size-4" />
                  <span>Pending All 4 Desks</span>
                </div>
              )}
              <span className="text-[11px] text-text-muted">
                {data.flags?.length ?? 0} compliance flag(s) logged
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ── 4-Pillar Executive Strip ────────────────────────────────────── */}
      <section className="space-y-3" aria-label="4-Pillar Executive Strip">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-text flex items-center gap-2">
            <span>Executive Pillar Breakdown</span>
            <span className="text-xs font-normal text-text-muted">(Weighted 4-Pillar Governance Model)</span>
          </h2>
          <span className="text-xs text-text-muted">Click any pillar card to inspect detailed criteria below</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4" data-testid="four-pillar-executive-strip">
          {TARGET_DOMAIN_ORDER.map((domainId) => {
            const cfg = PILLAR_CONFIGS[domainId];
            const pillar = data.pillars?.[domainId];
            const isSelected = activeTab === domainId;
            const evaluator = pillar?.evaluator;

            return (
              <div
                key={domainId}
                onClick={() => setActiveTab(domainId)}
                className={cn(
                  'rounded-md border p-4 cursor-pointer transition-all bg-surface flex flex-col justify-between gap-3 relative',
                  isSelected
                    ? 'border-primary ring-2 ring-primary/20 shadow-sm'
                    : 'border-border hover:border-text-muted/40 hover:bg-surface-subtle/50',
                )}
                data-testid={`pillar-card-${domainId}`}
              >
                {/* Header: Title & Weight */}
                <div className="space-y-1">
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-xs font-extrabold text-text truncate" title={cfg.label}>
                      {cfg.label}
                    </span>
                    <span className="text-[10px] font-bold px-1.5 py-0.2 rounded-xs bg-surface-subtle text-primary border border-primary/20 shrink-0">
                      {cfg.weightPercent}
                    </span>
                  </div>
                  <p className="text-[11px] text-text-muted truncate">{cfg.roleTitle}</p>
                </div>

                {/* Score & Status */}
                <div className="flex items-baseline justify-between border-t border-b border-border/60 py-2">
                  <span className="text-xs text-text-muted font-medium">Subtotal Score:</span>
                  <div className="text-right">
                    <span className="text-lg font-bold tabular-nums text-text">
                      {pillar?.subtotal !== null && pillar?.subtotal !== undefined
                        ? formatDomainScore(pillar.subtotal)
                        : '—'}
                    </span>
                    <span className="text-xs text-text-muted"> / 4.00</span>
                  </div>
                </div>

                {/* Evaluator Attribution Signature Chip */}
                <div className="pt-1">
                  {evaluator && evaluator.name ? (
                    <div
                      className="rounded-xs border border-border bg-surface-subtle/80 p-2 space-y-1"
                      data-testid={`evaluator-chip-${domainId}`}
                    >
                      <div className="flex items-center gap-1.5 text-[11px] font-bold text-text truncate">
                        <CheckCircle className="size-3.5 text-success shrink-0" aria-hidden="true" />
                        <span className="truncate">Evaluated by: {evaluator.name}</span>
                      </div>
                      <p className="text-[10px] text-text-muted truncate pl-5">
                        {evaluator.department || 'Specialist Desk'}
                      </p>
                    </div>
                  ) : (
                    <div
                      className="rounded-xs border border-dashed border-border bg-surface-subtle/40 p-2 flex items-center gap-1.5 text-[11px] font-semibold text-text-muted"
                      data-testid={`awaiting-review-${domainId}`}
                    >
                      <Clock className="size-3.5 text-text-muted shrink-0" aria-hidden="true" />
                      <span>Awaiting Review</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── Tabbed / Accordion Pillar Inspection ────────────────────────── */}
      <section className="space-y-4" aria-label="Detailed Pillar Inspection">
        {/* Tab Headers */}
        <div className="flex flex-wrap items-center gap-2 border-b border-border pb-2">
          {TARGET_DOMAIN_ORDER.map((domainId) => {
            const cfg = PILLAR_CONFIGS[domainId];
            const isSelected = activeTab === domainId;

            return (
              <button
                key={domainId}
                type="button"
                onClick={() => setActiveTab(domainId)}
                className={cn(
                  'px-4 py-2 text-xs font-bold rounded-xs border transition-colors flex items-center gap-2',
                  isSelected
                    ? 'bg-primary text-white border-primary shadow-xs'
                    : 'bg-surface text-text border-border hover:bg-surface-subtle',
                )}
                data-testid={`tab-button-${domainId}`}
              >
                <span>{cfg.label}</span>
                <span
                  className={cn(
                    'text-[10px] px-1.5 py-0.2 rounded-xs',
                    isSelected ? 'bg-white/20 text-white' : 'bg-surface-subtle text-text-muted',
                  )}
                >
                  {cfg.weightPercent}
                </span>
              </button>
            );
          })}
        </div>

        {/* Tab Body: Detailed View */}
        <div className="space-y-6" data-testid={`tab-content-${activeTab}`}>
          {/* Pillar Banner Overview */}
          <Card className="border border-border bg-surface">
            <CardContent className="p-5 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-3">
                <div>
                  <h3 className="text-base font-bold text-text flex items-center gap-2">
                    <span>{activePillarConfig.label}</span>
                    <span className="text-xs font-semibold text-text-muted">({activePillarConfig.roleTitle})</span>
                  </h3>
                  <p className="text-xs text-text-muted mt-1">{activePillarConfig.description}</p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <span className="text-[11px] uppercase font-bold text-text-muted block">Domain Score</span>
                    <span className="text-xl font-bold tabular-nums text-text">
                      {activePillar?.subtotal !== null && activePillar?.subtotal !== undefined
                        ? formatDomainScore(activePillar.subtotal)
                        : '—'}
                      <span className="text-xs text-text-muted font-normal"> / 4.00</span>
                    </span>
                  </div>
                  <Badge variant={getStatusVariant(activePillar?.status ?? 'PENDING')}>
                    {activePillar?.status ?? 'PENDING'}
                  </Badge>
                </div>
              </div>

              {/* Evaluator Attribution Card */}
              {activePillar?.evaluator ? (
                <div className="rounded-xs bg-surface-subtle border border-border p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="size-8 rounded-full bg-success-soft border border-success/30 flex items-center justify-center text-success">
                      <CheckCircle className="size-4" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-text">
                        Evaluated by: {activePillar.evaluator.name}
                      </p>
                      <p className="text-[11px] text-text-muted">
                        Department: {activePillar.evaluator.department || 'CID Specialist Desk'}
                        {activePillar.evaluator.email ? ` • ${activePillar.evaluator.email}` : ''}
                      </p>
                    </div>
                  </div>
                  <span className="text-[11px] font-semibold text-success bg-success-soft px-2 py-0.5 rounded-xs border border-success/20 self-start sm:self-auto">
                    Verified Evaluation Sign-off
                  </span>
                </div>
              ) : (
                <div className="rounded-xs bg-surface-subtle/50 border border-dashed border-border p-3 text-xs text-text-muted flex items-center gap-2">
                  <Clock className="size-4 text-text-muted" />
                  <span>This specialist evaluation is currently pending review. Criteria breakdown will appear upon completion.</span>
                </div>
              )}

              {/* Specialist Qualitative Summary */}
              {activePillar?.summary ? (
                <div className="space-y-1.5 pt-1">
                  <span className="text-xs font-bold uppercase tracking-wider text-text-muted">
                    Specialist Executive Summary & Observations
                  </span>
                  <p className="text-xs sm:text-sm text-text bg-surface-subtle/60 border border-border p-3 rounded-xs leading-relaxed">
                    {activePillar.summary}
                  </p>
                </div>
              ) : null}
            </CardContent>
          </Card>

          {/* Criteria Inspection List */}
          <div className="space-y-3">
            <h4 className="text-sm font-bold text-text">Detailed Rubric Criteria Assessment</h4>
            {activePillar?.criteria && activePillar.criteria.length > 0 ? (
              <div className="space-y-3">
                {activePillar.criteria.map((crit, idx) => (
                  <Card key={crit.criterion_id || idx} className="border border-border bg-surface shadow-none">
                    <CardContent className="p-4 space-y-2.5">
                      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
                        <div className="space-y-1">
                          <span className="text-[10px] font-mono font-bold uppercase px-1.5 py-0.2 rounded-xs bg-surface-subtle text-text-muted border border-border">
                            {crit.criterion_id}
                          </span>
                          <h5 className="text-sm font-bold text-text">{crit.criterion_text}</h5>
                          {crit.description ? (
                            <p className="text-xs text-text-muted">{crit.description}</p>
                          ) : null}
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <span className="text-xs text-text-muted font-medium">Score:</span>
                          <span className="inline-flex items-center px-2.5 py-1 rounded-xs font-bold text-xs bg-primary-soft text-primary border border-primary/20">
                            {crit.score} / 4
                          </span>
                        </div>
                      </div>

                      {crit.justification ? (
                        <div className="pt-2 border-t border-border/60 text-xs text-text space-y-1">
                          <span className="font-semibold text-text-muted block text-[11px]">Justification:</span>
                          <p className="leading-relaxed bg-surface-subtle/50 p-2.5 rounded-xs border border-border/40">
                            {crit.justification}
                          </p>
                        </div>
                      ) : null}

                      {crit.evidence ? (
                        <div className="text-xs text-text space-y-1">
                          <span className="font-semibold text-text-muted block text-[11px]">Evidence Excerpt:</span>
                          <blockquote className="border-l-2 border-primary/50 pl-3 py-1 font-mono text-[11px] text-text-muted bg-surface-subtle/30 italic">
                            "{crit.evidence}"
                          </blockquote>
                        </div>
                      ) : null}
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center border border-dashed border-border rounded-md bg-surface-subtle/30 text-text-muted text-xs">
                No specific criteria items recorded for this pillar yet.
              </div>
            )}
          </div>

          {/* Flags for Active Pillar */}
          {activePillarFlags.length > 0 ? (
            <div className="space-y-3 pt-2">
              <h4 className="text-sm font-bold text-text flex items-center gap-2">
                <Warning className="size-4 text-warning" />
                <span>Specialist Compliance Flags ({activePillarFlags.length})</span>
              </h4>
              <div className="space-y-2">
                {activePillarFlags.map((flag) => (
                  <div
                    key={flag.flag_id}
                    className="p-3 rounded-xs border border-warning/30 bg-warning-soft text-xs text-warning space-y-1"
                  >
                    <div className="flex items-center justify-between font-bold">
                      <span>Flag ID: {flag.flag_id.slice(0, 8)}</span>
                      {flag.criterion_id ? <span>Ref: {flag.criterion_id}</span> : null}
                    </div>
                    <p className="text-text">{flag.message || flag.justification || 'Flagged for review'}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </section>

      {/* ── Institutional Accreditation Signatory Governance Block ─────── */}
      <Card
        className="border border-border bg-surface shadow-xs print:border-none print:shadow-none"
        data-testid="accreditation-signatory-block"
      >
        <CardHeader className="py-3 px-6 bg-surface-subtle border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Certificate className="size-5 text-primary" aria-hidden="true" />
            <CardTitle className="text-sm font-bold uppercase tracking-wider text-text">
              Institutional Accreditation Signatory & Governance File
            </CardTitle>
          </div>
          <Badge variant={data.can_certify ? 'success' : 'neutral'} withDot>
            {data.can_certify ? 'Accreditation Ready' : 'Pending Pillar Convergence'}
          </Badge>
        </CardHeader>
        <CardContent className="p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
            {/* Left: Accreditation Overview Statement */}
            <div className="space-y-3 text-xs text-text-muted leading-relaxed">
              <p>
                This Master Synthesis Scorecard compiles and weights formal assessments from the 4 institutional
                curriculum review desks: Subject Matter Expert (35%), Program Coordinator (30%), Gender & Development
                (20%), and Innovation & Technology Support Office (15%).
              </p>
              <div className="flex flex-wrap items-center gap-4 text-[11px] font-mono pt-1">
                <span>Document: {data.document_title || 'Untitled SLM'}</span>
                <span>•</span>
                <span>Synthesized Score: {data.synthesized_score?.toFixed(2) ?? '—'} / 4.00</span>
                <span>•</span>
                <span>Certification Code: CID-ACC-{data.document_id.slice(0, 8).toUpperCase()}</span>
              </div>
            </div>

            {/* Right: Formal Signatory Block */}
            <div className="border border-border rounded-md p-5 bg-surface-subtle/50 space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block">
                    Accreditation Signatory Line
                  </span>
                  <p className="text-sm font-extrabold text-text">Director, Center for Instructional Development</p>
                  <p className="text-xs text-text-muted">Office of Academic Affairs & Accreditation Governance</p>
                </div>
                <div className="size-10 rounded-full border border-primary/20 bg-primary/10 flex items-center justify-center text-primary shrink-0">
                  <SealCheck className="size-5" />
                </div>
              </div>

              <div className="pt-4 border-t border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                <span className="text-text-muted">
                  Date: <strong className="text-text">{new Date().toLocaleDateString()}</strong>
                </span>
                {certified ? (
                  <span className="inline-flex items-center gap-1 text-success font-bold bg-success-soft px-2.5 py-1 rounded-xs border border-success/30">
                    <CheckCircle className="size-3.5" />
                    <span>Certified for Accreditation</span>
                  </span>
                ) : (
                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    disabled={!data.can_certify}
                    onClick={() => setCertified(true)}
                    className="h-8 text-xs font-semibold"
                    data-testid="certify-button"
                  >
                    <SealCheck className="size-4" />
                    <span>{data.can_certify ? 'Certify Module' : 'Awaiting 4/4 Verification'}</span>
                  </Button>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default MasterSynthesisPage;
