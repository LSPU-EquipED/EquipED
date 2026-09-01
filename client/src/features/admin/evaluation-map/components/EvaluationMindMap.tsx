import { useMemo, useState } from 'react';
import {
  BookOpenText,
  CheckCircle,
  CaretRight,
  Database,
  FileArrowDown,
  FilePdf,
  GitBranch,
  GitFork,
  Info,
  Package,
  ShieldCheck,
  Sparkle,
} from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { cn } from '@/shared/components/utils';
import {
  evaluationMapEdges,
  evaluationMapNodes,
  getActiveMapIds,
  type EvaluationMapNode,
  type MapNodeKind,
} from '../evaluationMapData';

const nodeWidth = 240;
const nodeHeight = 58;
const canvasWidth = 980;
const canvasHeight = 670;

const kindMeta: Record<
  MapNodeKind,
  { label: string; layer: string; icon: typeof Database }
> = {
  reference: { label: 'References & Ingestion', layer: 'Layer 1', icon: Database },
  process: { label: 'Specialist Processes', layer: 'Layer 2–3', icon: GitBranch },
  output: { label: 'Accredited Outputs', layer: 'Layer 4', icon: FileArrowDown },
};

const outputIcons: Record<string, typeof Package> = {
  'sme-output': Sparkle,
  'gad-output': CheckCircle,
  'itso-output': ShieldCheck,
  'coordinator-output': BookOpenText,
  scorecard: Package,
  report: FilePdf,
  matrix: GitFork,
  'syllabus-output': BookOpenText,
};

function nodeCenter(node: EvaluationMapNode) {
  return { x: node.x + nodeWidth / 2, y: node.y + nodeHeight / 2 };
}

function edgePath(from: EvaluationMapNode, to: EvaluationMapNode) {
  const fromCenter = nodeCenter(from);
  const toCenter = nodeCenter(to);
  const startX = from.x + nodeWidth;
  const endX = to.x;
  const control = Math.max(40, (endX - startX) * 0.48);
  return `M ${startX} ${fromCenter.y} C ${startX + control} ${fromCenter.y}, ${endX - control} ${toCenter.y}, ${endX} ${toCenter.y}`;
}

function MapNode({
  node,
  active,
  selected,
  onSelect,
}: {
  node: EvaluationMapNode;
  active: boolean;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const isOutput = node.kind === 'output';
  const Icon = isOutput ? (outputIcons[node.id] ?? FileArrowDown) : kindMeta[node.kind].icon;

  const stateClass = active
    ? selected
      ? 'border-primary bg-primary text-primary-foreground ring-2 ring-primary/25 shadow-xs'
      : node.kind === 'reference'
        ? 'border-success/50 bg-success-soft text-text ring-1 ring-success/20'
        : 'border-primary/50 bg-primary-soft text-text ring-1 ring-primary/20'
    : 'border-border bg-surface text-text-muted opacity-45 hover:opacity-75';

  const content = (
    <>
      <span
        className={cn(
          'flex size-7 shrink-0 items-center justify-center rounded-xs border',
          selected
            ? 'border-primary-foreground/30 bg-primary-foreground/15 text-primary-foreground'
            : active
              ? node.kind === 'reference'
                ? 'border-success/30 bg-surface text-success'
                : 'border-primary/30 bg-surface text-primary'
              : 'border-border bg-surface-subtle text-text-muted',
        )}
      >
        <Icon className="size-3.5" aria-hidden="true" />
      </span>
      <span className="min-w-0 flex-1 text-left">
        <span className="flex items-center justify-between gap-1">
          <span
            className={cn(
              'text-xs font-semibold truncate',
              selected ? 'text-primary-foreground font-bold' : 'text-text',
            )}
          >
            {node.title}
          </span>
          {isOutput ? (
            <CaretRight
              className={cn(
                'size-3 shrink-0',
                selected ? 'text-primary-foreground' : 'text-text-muted',
              )}
              aria-hidden="true"
            />
          ) : null}
        </span>
        <span
          className={cn(
            'block text-[10px] truncate leading-tight mt-0.5',
            selected ? 'text-primary-soft' : 'text-text-muted',
          )}
        >
          {node.detail}
        </span>
        {node.status ? (
          <span
            className={cn(
              'mt-0.5 inline-block text-[9px] font-semibold uppercase tracking-wider',
              selected ? 'text-accent' : 'text-warning',
            )}
          >
            {node.status}
          </span>
        ) : null}
      </span>
    </>
  );

  const className = cn(
    'absolute z-10 flex h-[58px] items-center gap-2.5 rounded-sm border px-2.5 py-1.5 transition-all duration-150',
    stateClass,
    isOutput && 'hover:translate-x-0.5',
  );

  const position = {
    left: `${(node.x / canvasWidth) * 100}%`,
    top: node.y,
    width: `${(nodeWidth / canvasWidth) * 100}%`,
  };

  if (isOutput) {
    return (
      <button
        type="button"
        aria-pressed={selected}
        onClick={() => onSelect(node.id)}
        className={cn(
          className,
          'cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring select-none',
        )}
        style={position}
      >
        {content}
      </button>
    );
  }

  return (
    <div className={className} style={position}>
      {content}
    </div>
  );
}

const PRIMARY_OUTPUT_PRESETS = [
  { id: 'scorecard', label: 'Overall Scorecard' },
  { id: 'matrix', label: 'Monitoring Matrix' },
  { id: 'report', label: 'Evaluation PDF Report' },
  { id: 'syllabus-output', label: 'Syllabus Alignment' },
];

const SPECIALIST_PRESETS = [
  { id: 'sme-output', label: 'SME Scorecard' },
  { id: 'coordinator-output', label: 'Coordinator Review' },
  { id: 'gad-output', label: 'GAD Review' },
  { id: 'itso-output', label: 'ITSO Review' },
];

export function EvaluationMindMap() {
  const [selectedOutput, setSelectedOutput] = useState('scorecard');
  const { activeNodes, activeEdges } = useMemo(
    () => getActiveMapIds(selectedOutput),
    [selectedOutput],
  );
  const selectedNode =
    evaluationMapNodes.find((node) => node.id === selectedOutput) ?? evaluationMapNodes[0];

  // Upstream dependency breakdown for Inspector
  const activeReferences = useMemo(
    () =>
      evaluationMapNodes.filter(
        (n) => n.kind === 'reference' && activeNodes.has(n.id),
      ),
    [activeNodes],
  );

  const activeProcesses = useMemo(
    () =>
      evaluationMapNodes.filter(
        (n) => n.kind === 'process' && activeNodes.has(n.id),
      ),
    [activeNodes],
  );

  return (
    <section aria-labelledby="evaluation-map-title" className="px-4 sm:px-6 py-6 max-w-[108rem] mx-auto space-y-5">
      {/* ── Workstation Header & Context Strip ─────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded-sm border border-primary/20 bg-primary-soft px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-primary">
              Institutional Architecture Blueprint
            </span>
            <span className="text-xs text-text-muted">·</span>
            <span className="text-xs text-text-muted font-medium">Laguna State Polytechnic University</span>
          </div>
          <h1 id="evaluation-map-title" className="text-lg sm:text-xl font-bold text-text tracking-tight">
            Multi-Agent Knowledge Lineage & Data Residency Map
          </h1>
          <p className="text-xs text-text-muted max-w-3xl leading-relaxed">
            Trace verified data boundaries from institutional references through Layer 3 specialist agent executions to deterministic Layer 4 scorecard and monitoring matrix synthesis.
          </p>
        </div>

        {/* Governance Notice Banner */}
        <div className="flex max-w-sm items-start gap-2.5 rounded-sm border border-border bg-surface p-3 text-xs text-text shrink-0 shadow-none">
          <Info className="size-4 text-primary shrink-0 mt-0.5" aria-hidden="true" />
          <p className="text-[11px] leading-relaxed text-text-muted">
            <strong className="text-text font-semibold">Advisory Governance.</strong> Automated findings support review; human faculty judgment remains authoritative.
          </p>
        </div>
      </div>

      {/* ── Grouped Preset Selection & Legend Toolbar ───────────────────── */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 rounded-md border border-border bg-surface px-4 py-3">
        {/* Preset Chips Grouped */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Layer 4 Outputs */}
          <div className="flex items-center gap-1">
            <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider mr-1">
              Synthesized:
            </span>
            {PRIMARY_OUTPUT_PRESETS.map((preset) => {
              const isSelected = selectedOutput === preset.id;
              return (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => setSelectedOutput(preset.id)}
                  className={cn(
                    'rounded-xs px-2.5 py-1 text-xs font-semibold transition-colors cursor-pointer border select-none',
                    isSelected
                      ? 'border-primary bg-primary text-primary-foreground font-bold'
                      : 'border-border bg-surface text-text hover:bg-surface-subtle',
                  )}
                >
                  {preset.label}
                </button>
              );
            })}
          </div>

          <span className="hidden sm:inline text-border">|</span>

          {/* Layer 3 Specialist Outputs */}
          <div className="flex items-center gap-1">
            <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider mr-1">
              Specialist:
            </span>
            {SPECIALIST_PRESETS.map((preset) => {
              const isSelected = selectedOutput === preset.id;
              return (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => setSelectedOutput(preset.id)}
                  className={cn(
                    'rounded-xs px-2 py-1 text-xs font-semibold transition-colors cursor-pointer border select-none',
                    isSelected
                      ? 'border-primary bg-primary text-primary-foreground font-bold'
                      : 'border-border bg-surface text-text hover:bg-surface-subtle',
                  )}
                >
                  {preset.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Graph Legend */}
        <div
          className="flex flex-wrap items-center gap-3.5 text-xs font-medium text-text-muted shrink-0 pt-2 lg:pt-0 border-t lg:border-t-0 border-border"
          aria-label="Map legend"
        >
          <span className="inline-flex items-center gap-1.5">
            <span className="size-2 rounded-xs bg-success" /> Active Reference
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="size-2 rounded-xs bg-primary" /> Active Process
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="size-2 rounded-xs border border-border bg-surface" /> Inactive Path
          </span>
        </div>
      </div>

      {/* ── 3-Column Interactive Compact Map Canvas ───────────────────── */}
      <div className="overflow-x-auto rounded-md border border-border bg-surface shadow-none">
        <div
          className="relative min-h-[670px] w-full min-w-[980px] overflow-hidden"
          style={{
            backgroundColor: '#ffffff',
            backgroundImage:
              'linear-gradient(to right, #f1f4f9 1px, transparent 1px), linear-gradient(to bottom, #f1f4f9 1px, transparent 1px)',
            backgroundSize: '20px 20px',
          }}
        >
          {/* Column Header Titles with Layer Indicators */}
          <div className="absolute inset-x-0 top-0 z-20 grid grid-cols-3 border-b border-border bg-surface-subtle/95 px-5 py-2.5 backdrop-blur-xs">
            {(['reference', 'process', 'output'] as const).map((kind) => {
              const meta = kindMeta[kind];
              const Icon = meta.icon;
              return (
                <div
                  key={kind}
                  className="flex items-center justify-between pr-4 border-r last:border-r-0 border-border"
                >
                  <div className="flex items-center gap-2 text-xs font-bold text-text">
                    <Icon className="size-3.5 text-primary" aria-hidden="true" />
                    <span>{meta.label}</span>
                  </div>
                  <span className="text-[10px] font-mono font-semibold text-text-muted rounded-xs bg-surface border border-border px-1.5 py-0.2">
                    {meta.layer}
                  </span>
                </div>
              );
            })}
          </div>

          {/* SVG Connection Lines */}
          <svg
            className="pointer-events-none absolute inset-0 size-full"
            viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <defs>
              <marker
                id="arrow-active"
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                markerWidth="4.5"
                markerHeight="4.5"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#1b3b87" />
              </marker>
            </defs>
            {evaluationMapEdges.map((edge) => {
              const from = evaluationMapNodes.find((node) => node.id === edge.from)!;
              const to = evaluationMapNodes.find((node) => node.id === edge.to)!;
              const edgeId = `${edge.from}:${edge.to}`;
              const active = activeEdges.has(edgeId);

              return (
                <path
                  key={edgeId}
                  d={edgePath(from, to)}
                  fill="none"
                  stroke={active ? 'var(--primary)' : 'var(--border)'}
                  strokeWidth={active ? 2 : 1}
                  strokeDasharray={active ? undefined : '3 3'}
                  markerEnd={active ? 'url(#arrow-active)' : undefined}
                  opacity={active ? 0.95 : 0.3}
                  className="transition-all duration-200"
                />
              );
            })}
          </svg>

          {/* Render All Nodes */}
          {evaluationMapNodes.map((node) => (
            <MapNode
              key={node.id}
              node={node}
              active={activeNodes.has(node.id)}
              selected={selectedOutput === node.id}
              onSelect={setSelectedOutput}
            />
          ))}
        </div>
      </div>

      {/* ── Lineage Detail Inspector Panel ─────────────────────────────── */}
      <div className="rounded-md border border-border bg-surface p-4 sm:p-5 space-y-3.5">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
          <div className="flex items-center gap-2">
            <Sparkle className="size-4 text-primary" aria-hidden="true" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-text">
              Lineage Inspector: {selectedNode.title}
            </h3>
          </div>
          <Badge variant="info">
            {activeReferences.length} References · {activeProcesses.length} Processes
          </Badge>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          {/* Active References */}
          <div className="space-y-1.5">
            <span className="font-semibold text-text-muted text-[11px] uppercase tracking-wider">
              Ingestion Inputs Consumed ({activeReferences.length})
            </span>
            <div className="flex flex-wrap gap-1.5">
              {activeReferences.map((ref) => (
                <span
                  key={ref.id}
                  className="inline-flex items-center gap-1.5 rounded-xs border border-success/30 bg-success-soft px-2 py-0.5 font-medium text-text text-xs"
                >
                  <Database className="size-3 text-success" />
                  {ref.title}
                </span>
              ))}
            </div>
          </div>

          {/* Active Processes */}
          <div className="space-y-1.5">
            <span className="font-semibold text-text-muted text-[11px] uppercase tracking-wider">
              Specialist Processes Executed ({activeProcesses.length})
            </span>
            <div className="flex flex-wrap gap-1.5">
              {activeProcesses.map((proc) => (
                <span
                  key={proc.id}
                  className="inline-flex items-center gap-1.5 rounded-xs border border-primary/25 bg-primary-soft px-2 py-0.5 font-medium text-text text-xs"
                >
                  <GitBranch className="size-3 text-primary" />
                  {proc.title}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Data Residency & Architectural Invariants */}
        <div className="pt-2 border-t border-border flex flex-wrap items-center justify-between gap-3 text-[11px] text-text-muted">
          <div className="flex items-center gap-1.5">
            <ShieldCheck className="size-3.5 text-primary shrink-0" />
            <span>
              <strong>Local Data Residency:</strong> SLMs are direct evaluation input and are never embedded into vector storage.
            </span>
          </div>
          <span>FastAPI Modular Monolith · In-Process Layer 3/4 Execution</span>
        </div>
      </div>
    </section>
  );
}
