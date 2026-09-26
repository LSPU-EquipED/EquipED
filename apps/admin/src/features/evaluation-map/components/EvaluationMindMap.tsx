import { useId, useMemo, useState } from 'react';
import {
  ArrowUpRight,
  BookOpenText,
  CheckCircle,
  Database,
  FileText,
  GitBranch,
  ListChecks,
  Scales,
  WarningCircle,
} from '@phosphor-icons/react';
import { cn } from '@equiped/ui';
import {
  knowledgeConsumers,
  knowledgeSourceKinds,
  knowledgeSources,
  type KnowledgeSource,
  type KnowledgeSourceKind,
} from '../data/evaluationMapData';
import { useDiagramGeometry } from '../hooks/useDiagramGeometry';

const sourceKindMeta: Record<
  KnowledgeSourceKind,
  {
    label: string;
    icon: typeof Database;
    tone: string;
    softTone: string;
  }
> = {
  rubric: {
    label: 'Rubric',
    icon: ListChecks,
    tone: 'text-primary',
    softTone: 'border-primary/20 bg-primary-soft',
  },
  syllabus: {
    label: 'Syllabus',
    icon: BookOpenText,
    tone: 'text-success',
    softTone: 'border-success/20 bg-success-soft',
  },
  curriculum: {
    label: 'Curriculum',
    icon: FileText,
    tone: 'text-warning',
    softTone: 'border-warning/25 bg-warning-soft',
  },
  policy: {
    label: 'Policy',
    icon: Scales,
    tone: 'text-info',
    softTone: 'border-info/20 bg-info-soft',
  },
};

function RoleBadge({ role }: { role: KnowledgeSource['role'] }) {
  const isReference = role === 'reference';
  const Icon = isReference ? CheckCircle : WarningCircle;

  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center gap-1 rounded-sm border px-1.5 py-0.5 text-[11px] font-semibold leading-4',
        isReference
          ? 'border-success/25 bg-success-soft text-success'
          : 'border-warning/30 bg-warning-soft text-warning',
      )}
    >
      <Icon className="size-3" aria-hidden="true" />
      {isReference ? 'Reference' : 'Review topic'}
    </span>
  );
}

function SourceIcon({ kind, className }: { kind: KnowledgeSourceKind; className?: string }) {
  const Icon = sourceKindMeta[kind].icon;
  return <Icon className={cn('size-4', className)} aria-hidden="true" />;
}

function SourceNode({
  source,
  selected,
  top,
  nodeRef,
  onSelect,
}: {
  source: KnowledgeSource;
  selected: boolean;
  top: number | undefined;
  nodeRef: (el: HTMLButtonElement | null) => void;
  onSelect: () => void;
}) {
  const meta = sourceKindMeta[source.kind];

  return (
    <button
      ref={nodeRef}
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      style={top !== undefined ? { top: `${top}px` } : undefined}
      className={cn(
        'absolute left-0 w-[43%] rounded-md border p-3.5 text-left transition-all duration-200',
        selected
          ? 'z-10 border-l-2 border-primary bg-primary-soft shadow-sm ring-1 ring-primary/15'
          : 'border-border bg-surface hover:border-primary/35 hover:shadow-xs',
      )}
    >
      <span className="flex items-start gap-3">
        <span
          className={cn(
            'flex size-9 shrink-0 items-center justify-center rounded-md border',
            meta.softTone,
            meta.tone,
          )}
        >
          <SourceIcon kind={source.kind} className="size-4.5" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-start justify-between gap-2">
            <span className="text-sm font-semibold leading-5 text-text">{source.title}</span>
            <RoleBadge role={source.role} />
          </span>
          <span className="mt-1 block text-xs leading-5 text-text-muted">{source.scope}</span>
          <span className="mt-1 block text-xs font-medium text-text-muted">{source.evidence}</span>
        </span>
      </span>
    </button>
  );
}

function ConsumerNode({
  label,
  detail,
  top,
  active,
  nodeRef,
}: {
  label: string;
  detail: string;
  top: number | undefined;
  active: boolean;
  nodeRef: (el: HTMLDivElement | null) => void;
}) {
  return (
    <div
      ref={nodeRef}
      style={top !== undefined ? { top: `${top}px` } : undefined}
      className={cn(
        'absolute right-0 w-[43%] rounded-md border px-3.5 py-3 transition-all duration-200',
        active ? 'border-primary/35 bg-primary-soft/55 shadow-xs' : 'border-border bg-surface',
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className={cn(
            'mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md border',
            active
              ? 'border-primary/25 bg-surface text-primary'
              : 'border-border bg-surface-subtle text-text-muted',
          )}
        >
          <GitBranch className="size-4" aria-hidden="true" />
        </span>
        <span className="min-w-0">
          <span className="block text-sm font-semibold text-text">{label}</span>
          <span className="mt-1 block text-xs leading-5 text-text-muted">{detail}</span>
        </span>
      </div>
    </div>
  );
}

export function EvaluationMindMap() {
  const gradientId = useId();
  const [selectedSourceId, setSelectedSourceId] = useState('rubrics');
  const [filterKind, setFilterKind] = useState<'all' | KnowledgeSourceKind>('all');

  const visibleSources = useMemo(
    () => knowledgeSources.filter((source) => filterKind === 'all' || source.kind === filterKind),
    [filterKind],
  );
  const visibleSourceIds = useMemo(() => visibleSources.map((s) => s.id), [visibleSources]);
  const consumerIds = useMemo(() => knowledgeConsumers.map((c) => c.id), []);

  const selectedSource =
    knowledgeSources.find((source) => source.id === selectedSourceId) ?? knowledgeSources[0];
  const selectedConsumers = selectedSource.consumers
    .map((consumerId) => knowledgeConsumers.find((consumer) => consumer.id === consumerId))
    .filter((consumer): consumer is (typeof knowledgeConsumers)[number] => Boolean(consumer));

  const referenceCount = knowledgeSources.filter((source) => source.role === 'reference').length;
  const reviewTopicCount = knowledgeSources.filter((source) => source.role === 'review-topic').length;

  const { registerContainer, registerSource, registerConsumer, anchors, layout } =
    useDiagramGeometry(visibleSourceIds, consumerIds, 496, 16);

  const handleFilterChange = (kind: 'all' | KnowledgeSourceKind) => {
    setFilterKind(kind);
    if (kind !== 'all') {
      const firstMatchingSource = knowledgeSources.find((source) => source.kind === kind);
      if (firstMatchingSource) setSelectedSourceId(firstMatchingSource.id);
    }
  };

  return (
    <section aria-label="Knowledge map workspace" className="mx-auto max-w-[108rem] space-y-6">
      <div className="grid grid-cols-2 overflow-hidden rounded-md border border-border bg-surface sm:grid-cols-4">
        {[
          ['Authoritative sources', knowledgeSources.length.toString(), 'Across local reference types'],
          ['Reference source types', referenceCount.toString(), 'Institutional reference materials'],
          ['Review topics', reviewTopicCount.toString(), 'Curricular and coverage topics'],
          ['Evaluation consumers', knowledgeConsumers.length.toString(), 'Specialist and synthesis paths'],
        ].map(([label, value, detail], index) => (
          <div key={label} className={cn('px-4 py-3.5', index > 0 && 'border-l border-border')}>
            <p className="text-xs font-semibold text-text-muted">{label}</p>
            <p className="mt-1 text-xl font-semibold tabular-nums text-text">{value}</p>
            <p className="mt-0.5 text-xs text-text-muted">{detail}</p>
          </div>
        ))}
      </div>

      <div className="grid min-w-0 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_21rem]">
        <section aria-labelledby="grounding-path-title" className="min-w-0">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Database className="size-5 text-primary" aria-hidden="true" />
                <h2 id="grounding-path-title" className="text-lg font-semibold text-text">
                  Grounding path
                </h2>
              </div>
              <p className="mt-1 text-sm text-text-muted">
                Click a source to highlight the evaluation consumers it supports.
              </p>
            </div>
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter knowledge sources">
              {knowledgeSourceKinds.map((kind) => (
                <button
                  key={kind.value}
                  type="button"
                  aria-pressed={filterKind === kind.value}
                  onClick={() => handleFilterChange(kind.value)}
                  className={cn(
                    'rounded-full border px-2.5 py-1 text-xs font-semibold transition-colors',
                    filterKind === kind.value
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'border-border bg-surface text-text-muted hover:border-primary/35 hover:text-text',
                  )}
                >
                  {kind.label}
                </button>
              ))}
            </div>
          </div>

          {/* Horizontally scrollable container with intrinsic min-width */}
          <div className="mt-4 overflow-x-auto rounded-md border border-border bg-surface-subtle/35 p-5 sm:p-7">
            <div className="relative min-w-[700px]" style={{ minHeight: `${layout.totalHeight + 80}px` }}>
              <div className="flex justify-between text-xs font-semibold text-text-muted">
                <span className="inline-flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-primary" />
                  Authoritative sources
                </span>
                <span className="inline-flex items-center gap-2">
                  Evaluation consumers
                  <span className="size-1.5 rounded-full bg-primary" />
                </span>
              </div>

              {/* Node and SVG canvas container */}
              <div
                ref={registerContainer}
                className="relative mt-8"
                style={{ height: `${layout.totalHeight}px` }}
              >
                <svg
                  className="pointer-events-none absolute inset-0 size-full"
                  role="img"
                  aria-label="Knowledge map connections"
                >
                  <defs>
                    <linearGradient id={gradientId} x1="0" x2="1">
                      <stop offset="0" stopColor="currentColor" stopOpacity="0.15" />
                      <stop offset="0.5" stopColor="currentColor" stopOpacity="0.5" />
                      <stop offset="1" stopColor="currentColor" stopOpacity="0.18" />
                    </linearGradient>
                  </defs>
                  {visibleSources.flatMap((source) => {
                    const sourceAnchor = anchors.sources[source.id];
                    const sourceY = sourceAnchor?.y ?? (layout.sourceTops[source.id] ?? 0) + 44;
                    const sourceX = sourceAnchor?.x ?? 300;

                    return source.consumers.map((consumerId) => {
                      const consumerIndex = knowledgeConsumers.findIndex((c) => c.id === consumerId);
                      if (consumerIndex < 0) return null;
                      const consumerAnchor = anchors.consumers[consumerId];
                      const consumerY =
                        consumerAnchor?.y ?? (layout.consumerTops[consumerId] ?? 0) + 36;
                      const consumerX = consumerAnchor?.x ?? 400;
                      const active = source.id === selectedSource.id;

                      const deltaX = Math.max(40, (consumerX - sourceX) * 0.5);
                      const cp1x = sourceX + deltaX;
                      const cp2x = consumerX - deltaX;

                      return (
                        <path
                          key={`${source.id}-${consumerId}`}
                          d={`M ${sourceX} ${sourceY} C ${cp1x} ${sourceY}, ${cp2x} ${consumerY}, ${consumerX} ${consumerY}`}
                          fill="none"
                          stroke={active ? 'var(--color-primary)' : `url(#${gradientId})`}
                          strokeWidth={active ? 2.4 : 1.3}
                          strokeDasharray={active ? undefined : '5 7'}
                          vectorEffect="non-scaling-stroke"
                          className="text-primary"
                        />
                      );
                    });
                  })}
                </svg>

                {visibleSources.map((source) => (
                  <SourceNode
                    key={source.id}
                    source={source}
                    top={layout.sourceTops[source.id]}
                    selected={source.id === selectedSource.id}
                    nodeRef={registerSource(source.id)}
                    onSelect={() => setSelectedSourceId(source.id)}
                  />
                ))}
                {knowledgeConsumers.map((consumer) => (
                  <ConsumerNode
                    key={consumer.id}
                    label={consumer.label}
                    detail={consumer.detail}
                    top={layout.consumerTops[consumer.id]}
                    active={selectedConsumers.some(
                      (selectedConsumer) => selectedConsumer.id === consumer.id,
                    )}
                    nodeRef={registerConsumer(consumer.id)}
                  />
                ))}

                <div className="absolute left-1/2 top-1/2 hidden -translate-x-1/2 -translate-y-1/2 items-center gap-2 rounded-sm border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-text-muted shadow-xs xl:flex">
                  <GitBranch className="size-3.5 text-primary" aria-hidden="true" />
                  Grounds evaluation
                </div>
              </div>

              <div className="mt-6 flex items-center justify-center gap-4 text-[11px] font-medium text-text-muted">
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-px w-5 bg-primary" />
                  Selected relationship
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="w-5 border-t border-dashed border-text-muted/60" />
                  Other relationships
                </span>
              </div>
            </div>
          </div>
        </section>

        <aside
          aria-labelledby="source-details-title"
          className="min-w-0 rounded-md border border-border bg-surface p-5 lg:sticky lg:top-5"
        >
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-semibold text-text-muted">Selected source</p>
            <RoleBadge role={selectedSource.role} />
          </div>
          <h2 id="source-details-title" className="mt-1 text-lg font-semibold text-text">
            Source details
          </h2>
          <p className="mt-1 text-xs text-text-muted">
            Feeds {selectedConsumers.length} evaluation{' '}
            {selectedConsumers.length === 1 ? 'path' : 'paths'}.
          </p>
          <div className="mt-5 border-b border-border pb-5">
            <div className="flex items-start gap-3">
              <span
                className={cn(
                  'flex size-9 shrink-0 items-center justify-center rounded-md border',
                  sourceKindMeta[selectedSource.kind].softTone,
                  sourceKindMeta[selectedSource.kind].tone,
                )}
              >
                <SourceIcon kind={selectedSource.kind} />
              </span>
              <div className="min-w-0">
                <h3 className="text-base font-semibold text-text">{selectedSource.title}</h3>
                <p className="mt-0.5 text-xs text-text-muted">
                  {sourceKindMeta[selectedSource.kind].label}
                </p>
              </div>
            </div>
            <div className="mt-5 space-y-4">
              <div>
                <p className="text-xs font-semibold text-text-muted">Scope</p>
                <p className="mt-1 text-sm text-text">{selectedSource.scope}</p>
              </div>
              <div>
                <p className="text-xs font-semibold text-text-muted">Evidence criteria</p>
                <p className="mt-1 text-sm text-text">{selectedSource.evidence}</p>
              </div>
              <div>
                <p className="text-xs font-semibold text-text-muted">Reference context</p>
                <p className="mt-1 text-sm text-text">{selectedSource.referenceContext}</p>
              </div>
            </div>
          </div>
          <div
            className={cn(
              'mt-5 rounded-md border p-3 text-sm',
              selectedSource.role === 'reference'
                ? 'border-success/25 bg-success-soft/55 text-text-muted'
                : 'border-warning/30 bg-warning-soft/55 text-text-muted',
            )}
          >
            {selectedSource.role === 'reference' ? (
              <p className="flex items-start gap-2">
                <CheckCircle className="mt-0.5 size-4 shrink-0 text-success" aria-hidden="true" />
                <span>
                  <span className="font-semibold text-text">Illustrative relationship.</span>{' '}
                  Institutional reference mapping for evaluation grounding.
                </span>
              </p>
            ) : (
              <p className="flex items-start gap-2">
                <WarningCircle className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
                <span>
                  <span className="font-semibold text-text">Review this source type.</span> Check
                  institutional curriculum mapping for evaluation alignment.
                </span>
              </p>
            )}
          </div>
          <a
            href="/admin/references"
            className="mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-primary hover:underline"
          >
            Open reference library <ArrowUpRight className="size-4" aria-hidden="true" />
          </a>
        </aside>
      </div>
    </section>
  );
}
