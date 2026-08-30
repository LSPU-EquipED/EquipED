import { useMemo, useState } from 'react';
import {
  BookOpenText,
  CheckCircle,
  CaretRight,
  Database,
  FileArrowDown,
  GitBranch,
  GitFork,
  Info,
  Package,
  ShieldCheck,
  Sparkle,
} from '@phosphor-icons/react';
import {
  evaluationMapEdges,
  evaluationMapNodes,
  getActiveMapIds,
  type EvaluationMapNode,
  type MapNodeKind,
} from '../evaluationMapData';

const nodeWidth = 310;
const nodeHeight = 82;
const canvasWidth = 1140;

const kindMeta: Record<MapNodeKind, { label: string; icon: typeof Database }> = {
  reference: { label: 'References · data', icon: Database },
  process: { label: 'Evaluation processes', icon: GitBranch },
  output: { label: 'Major features · outputs', icon: FileArrowDown },
};

const outputIcons: Record<string, typeof Package> = {
  'sme-output': Sparkle,
  'gad-output': CheckCircle,
  'itso-output': ShieldCheck,
  'coordinator-output': BookOpenText,
  scorecard: Package,
  report: FileArrowDown,
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
  const control = Math.max(54, (endX - startX) * 0.48);
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
      ? 'border-[#1b3b87] bg-[#1b3b87] text-white ring-4 ring-[#1b3b87]/10'
      : node.kind === 'reference'
        ? 'border-[#3b963e] bg-[#f0f9f1] text-slate-950 ring-2 ring-[#3b963e]/10'
        : 'border-[#1b3b87] bg-[#eef3ff] text-slate-950 ring-2 ring-[#1b3b87]/10'
    : 'border-slate-200 bg-white text-slate-500 opacity-55';

  const content = (
    <>
      <span
        className={`mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-sm border ${
          selected
            ? 'border-white/30 bg-white/15 text-white'
            : active
              ? 'border-current/20 bg-white text-current'
              : 'border-slate-200 bg-slate-50 text-slate-400'
        }`}
      >
        <Icon className="size-4" aria-hidden="true" />
      </span>
      <span className="min-w-0 flex-1 text-left">
        <span className="flex items-start justify-between gap-2">
          <span className="text-[13px] font-bold leading-5">{node.title}</span>
          {isOutput && <CaretRight className="mt-0.5 size-4 shrink-0" aria-hidden="true" />}
        </span>
        <span className={`mt-0.5 block text-[11px] leading-4 ${selected ? 'text-blue-100' : active ? 'text-slate-600' : 'text-slate-400'}`}>
          {node.detail}
        </span>
        {node.status && (
          <span className={`mt-1 inline-block text-[9px] font-bold uppercase tracking-[0.08em] ${selected ? 'text-[#f2c811]' : 'text-[#8a6d00]'}`}>
            {node.status}
          </span>
        )}
      </span>
    </>
  );

  const className = `absolute z-10 flex min-h-[82px] gap-3 rounded-md border p-3 transition-[opacity,background-color,border-color,box-shadow,transform] duration-300 ${stateClass} ${isOutput ? 'hover:translate-x-0.5' : ''}`;
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
        className={`${className} cursor-pointer focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#1b3b87]/25`}
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

export function EvaluationMindMap() {
  const [selectedOutput, setSelectedOutput] = useState('scorecard');
  const { activeNodes, activeEdges } = useMemo(
    () => getActiveMapIds(selectedOutput),
    [selectedOutput],
  );
  const selectedNode = evaluationMapNodes.find((node) => node.id === selectedOutput)!;

  return (
    <section aria-labelledby="evaluation-map-title" className="min-h-[calc(100vh-4rem)] bg-slate-50 px-5 py-6 lg:px-7">
      <div className="mx-auto max-w-[1500px]">
        <header className="grid gap-5 border-b border-slate-300 pb-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <div>
            <div className="mb-2 flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.16em] text-primary">
              <GitFork className="size-4" aria-hidden="true" /> Academic evaluation system
            </div>
            <h1 id="evaluation-map-title" className="text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">
              From institutional evidence to advisory output
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              Select a major output on the right. Every reference and process used to produce it will light up, revealing the evaluation path and its evidence boundaries.
            </p>
          </div>
          <div className="flex max-w-md items-start gap-2 border-l-4 border-[#f2c811] bg-white px-4 py-3 text-xs leading-5 text-slate-700">
            <Info className="mt-0.5 size-4 shrink-0 text-[#1b3b87]" aria-hidden="true" />
            <p><strong className="text-slate-950">Advisory only.</strong> Generated findings support academic review; CID and faculty human judgment remains authoritative.</p>
          </div>
        </header>

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
          <div aria-live="polite" className="flex items-center gap-2 text-sm text-slate-700">
            <span className="flex size-7 items-center justify-center rounded-sm bg-[#1b3b87] text-white">
              <Sparkle className="size-3.5" aria-hidden="true" />
            </span>
            Showing inputs for <strong className="text-slate-950">{selectedNode.title}</strong>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-2 text-[10px] font-bold uppercase tracking-[0.1em] text-slate-600" aria-label="Map legend">
            <span className="inline-flex items-center gap-1.5"><i className="size-2.5 rounded-full bg-[#3b963e]" /> Used reference</span>
            <span className="inline-flex items-center gap-1.5"><i className="size-2.5 rounded-full bg-[#1b3b87]" /> Active process</span>
            <span className="inline-flex items-center gap-1.5"><i className="size-2.5 rounded-full border border-slate-300 bg-white" /> Other path</span>
          </div>
        </div>

        <div className="mt-4 overflow-x-auto rounded-md border border-slate-300 bg-white">
          <div
            className="relative min-h-[1015px] w-full min-w-[1140px] overflow-hidden"
            style={{
              backgroundColor: '#fbfdff',
              backgroundImage: 'linear-gradient(#e8edf4 1px, transparent 1px), linear-gradient(90deg, #e8edf4 1px, transparent 1px)',
              backgroundSize: '24px 24px',
            }}
          >
            <div className="absolute inset-x-0 top-0 z-20 grid grid-cols-3 border-b border-slate-200 bg-white/95 px-6 py-3 backdrop-blur-sm">
              {(['reference', 'process', 'output'] as const).map((kind) => {
                const Icon = kindMeta[kind].icon;
                return (
                  <div key={kind} className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-700">
                    <Icon className="size-3.5 text-[#1b3b87]" aria-hidden="true" /> {kindMeta[kind].label}
                  </div>
                );
              })}
            </div>

            <svg className="pointer-events-none absolute inset-0 size-full" viewBox="0 0 1140 1015" preserveAspectRatio="none" aria-hidden="true">
              <defs>
                <marker id="arrow-active" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
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
                    stroke={active ? '#1b3b87' : '#cbd5e1'}
                    strokeWidth={active ? 2.25 : 1}
                    strokeDasharray={active ? undefined : '4 6'}
                    markerEnd={active ? 'url(#arrow-active)' : undefined}
                    opacity={active ? 0.92 : 0.38}
                    className="transition-all duration-300"
                  />
                );
              })}
            </svg>

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
      </div>
    </section>
  );
}
