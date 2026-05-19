import { Outlet } from '@tanstack/react-router';
import { AlertTriangle, BookOpenText, CheckCircle2, FileText, Lightbulb, Scale, ShieldCheck } from 'lucide-react';
import { useMemo, useRef, useState } from 'react';
import { Button } from '@/shared/components/ui/button';
import { Separator } from '@/shared/components/ui/separator';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/shared/components/ui/table';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/shared/components/ui/tooltip';
import { cn } from '@/shared/components/utils';
import { FeedbackPanel } from './FeedbackPanel';

type AgentId = 'coordinator' | 'sme' | 'gad' | 'itso';

type Criterion = {
  readonly label: string;
  readonly description: string;
  readonly score: number;
  readonly weight: number;
  readonly tone: 'strong' | 'watch' | 'review';
};

type Highlight = {
  readonly text: string;
  readonly tone: 'strong' | 'watch' | 'review';
};

type AgentEvaluation = {
  readonly id: AgentId;
  readonly label: string;
  readonly role: string;
  readonly score: number;
  readonly confidence: string;
  readonly summary: string;
  readonly icon: typeof BookOpenText;
  readonly criteria: readonly Criterion[];
  readonly highlights: readonly Highlight[];
  readonly comments: readonly string[];
};

const agents: readonly AgentEvaluation[] = [
  {
    id: 'coordinator',
    label: 'Program Coordinator',
    role: 'Curriculum alignment',
    score: 87,
    confidence: 'High confidence',
    summary: 'Well-organized course material with clear sequencing and measurable academic outcomes.',
    icon: BookOpenText,
    criteria: [
      { label: 'Organization & Presentation', description: 'Logical flow, formatting, and readability', score: 91, weight: 35, tone: 'strong' },
      { label: 'Assessment Quality', description: 'Alignment between tasks, outcomes, and rubrics', score: 84, weight: 30, tone: 'watch' },
      { label: 'Gender Sensitivity', description: 'Inclusive framing and neutral language', score: 88, weight: 20, tone: 'strong' },
      { label: 'Innovation & Compliance', description: 'Institutional fit and policy readiness', score: 83, weight: 15, tone: 'watch' },
    ],
    highlights: [
      { text: 'Course outcomes are mapped to weekly learning activities and institutional program goals.', tone: 'strong' },
      { text: 'Two assessment descriptions need clearer point allocation before faculty review.', tone: 'watch' },
      { text: 'The monitoring section should explicitly identify the evidence artifact owner.', tone: 'review' },
    ],
    comments: ['Strengthen assessment descriptors with point-level expectations.', 'Keep the existing sequence; it supports review traceability.'],
  },
  {
    id: 'sme',
    label: 'Subject Matter Expert (SME)',
    role: 'Discipline accuracy',
    score: 82,
    confidence: 'Moderate confidence',
    summary: 'Content is academically sound, with a few concepts needing richer examples and source anchoring.',
    icon: Lightbulb,
    criteria: [
      { label: 'Organization & Presentation', description: 'Concept progression and topic clarity', score: 85, weight: 25, tone: 'strong' },
      { label: 'Assessment Quality', description: 'Depth of higher-order learning checks', score: 79, weight: 35, tone: 'watch' },
      { label: 'Gender Sensitivity', description: 'Contextual examples and representation', score: 81, weight: 15, tone: 'watch' },
      { label: 'Innovation & Compliance', description: 'Currency of examples and references', score: 82, weight: 25, tone: 'watch' },
    ],
    highlights: [
      { text: 'Core definitions are accurate and appropriate for the expected student level.', tone: 'strong' },
      { text: 'The major project rubric would benefit from a clearer distinction between analysis and application.', tone: 'watch' },
      { text: 'Reference materials should include a more recent local example where available.', tone: 'review' },
    ],
    comments: ['Add one applied case per major topic.', 'Clarify how performance tasks measure synthesis rather than recall.'],
  },
  {
    id: 'gad',
    label: 'GAD Unit',
    role: 'Gender and development review',
    score: 90,
    confidence: 'High confidence',
    summary: 'Language is generally inclusive and learning activities avoid stereotypes while supporting participation.',
    icon: Scale,
    criteria: [
      { label: 'Organization & Presentation', description: 'Accessible and respectful document framing', score: 89, weight: 20, tone: 'strong' },
      { label: 'Assessment Quality', description: 'Fair assessment language and criteria', score: 87, weight: 25, tone: 'strong' },
      { label: 'Gender Sensitivity', description: 'Representation, inclusivity, and bias checks', score: 94, weight: 40, tone: 'strong' },
      { label: 'Innovation & Compliance', description: 'GAD policy alignment and evidence readiness', score: 88, weight: 15, tone: 'strong' },
    ],
    highlights: [
      { text: 'Activity instructions use neutral language and encourage equitable participation.', tone: 'strong' },
      { text: 'One scenario can be broadened to include community roles beyond traditional examples.', tone: 'watch' },
      { text: 'GAD compliance evidence is present but should be labeled in the appendix.', tone: 'review' },
    ],
    comments: ['Retain inclusive phrasing in activity prompts.', 'Broaden one scenario to show more varied learner contexts.'],
  },
  {
    id: 'itso',
    label: 'ITSO',
    role: 'Innovation and compliance',
    score: 78,
    confidence: 'Review recommended',
    summary: 'Innovation claims are promising, but documentation should better identify originality and ownership evidence.',
    icon: ShieldCheck,
    criteria: [
      { label: 'Organization & Presentation', description: 'Traceable innovation narrative', score: 80, weight: 25, tone: 'watch' },
      { label: 'Assessment Quality', description: 'Originality checks in student outputs', score: 76, weight: 20, tone: 'review' },
      { label: 'Gender Sensitivity', description: 'Inclusive access to technology activities', score: 84, weight: 15, tone: 'strong' },
      { label: 'Innovation & Compliance', description: 'IP awareness, attribution, and institutional controls', score: 74, weight: 40, tone: 'review' },
    ],
    highlights: [
      { text: 'The proposed digital artifact has a clear instructional purpose and deployment path.', tone: 'strong' },
      { text: 'Ownership, reuse permissions, and attribution expectations need to be stated more directly.', tone: 'review' },
      { text: 'Innovation indicators should be connected to measurable course deliverables.', tone: 'watch' },
    ],
    comments: ['Add explicit IP and attribution checkpoints.', 'Tie innovation claims to concrete student deliverables.'],
  },
];

const toneStyles = {
  strong: {
    text: 'text-emerald-700',
    bg: 'bg-emerald-100',
    bar: 'bg-emerald-500',
    mark: 'bg-emerald-100/90 ring-emerald-300',
    dot: 'bg-emerald-500',
  },
  watch: {
    text: 'text-amber-700',
    bg: 'bg-amber-100',
    bar: 'bg-amber-500',
    mark: 'bg-amber-100/90 ring-amber-300',
    dot: 'bg-amber-500',
  },
  review: {
    text: 'text-rose-700',
    bg: 'bg-rose-100',
    bar: 'bg-rose-500',
    mark: 'bg-rose-100/90 ring-rose-300',
    dot: 'bg-rose-500',
  },
} as const;

export function Scorecard() {
  const [activeAgentId, setActiveAgentId] = useState<AgentId>('coordinator');
  const [leftPanePercent, setLeftPanePercent] = useState(47);
  const splitPaneRef = useRef<HTMLDivElement | null>(null);
  const activeAgent = agents.find((agent) => agent.id === activeAgentId) ?? agents[0];
  const synthesizedScore = useMemo(() => Math.round(agents.reduce((total, agent) => total + agent.score, 0) / agents.length), []);

  const updatePaneSize = (clientX: number) => {
    const container = splitPaneRef.current;

    if (!container) {
      return;
    }

    const bounds = container.getBoundingClientRect();
    const nextPercent = ((clientX - bounds.left) / bounds.width) * 100;
    setLeftPanePercent(Math.min(70, Math.max(34, nextPercent)));
  };

  const handleResizePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    updatePaneSize(event.clientX);

    const handlePointerMove = (moveEvent: PointerEvent) => {
      updatePaneSize(moveEvent.clientX);
    };

    const handlePointerUp = () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp, { once: true });
  };

  return (
    <section className="-mx-6 -my-7 grid h-[calc(100vh-4rem)] min-h-0 grid-rows-[auto_minmax(0,1fr)] bg-background">
      <header className="grid min-h-24 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-b bg-background px-10">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.26em] text-muted-foreground">Selected Document</p>
          <h1 className="mt-2 truncate text-2xl font-semibold">Instructional Material Evaluation Draft</h1>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button variant="outline" className="h-11 gap-2 rounded-lg px-4">
            <FileText className="size-4" aria-hidden="true" />
            Source
          </Button>
          <Button className="h-11 rounded-lg px-5">Finalize Review</Button>
        </div>
      </header>

      <div
        ref={splitPaneRef}
        className="evaluation-split-pane grid min-h-0"
        style={
          {
            '--evaluation-left-pane': `${leftPanePercent}fr`,
            '--evaluation-right-pane': `${100 - leftPanePercent}fr`,
          } as React.CSSProperties
        }
      >
        <main className="min-h-0 overflow-y-auto bg-background px-12 py-16">
          <div className="mx-auto max-w-4xl">
            <div className="mb-11 grid gap-3 border-b pb-6 sm:grid-cols-[1fr_auto]">
              <div>
                <p className="text-lg font-semibold">Course Pack: Outcomes-Based Learning Module</p>
                <p className="mt-2 text-sm text-muted-foreground">Author: Faculty Reviewer - Date: May 19, 2026</p>
              </div>
              <div className="h-fit rounded-lg border bg-background px-4 py-3 text-base font-semibold">{activeAgent.label}</div>
            </div>

            <div className="space-y-6 text-[1.35rem] leading-[2.85rem] text-foreground">
              {activeAgent.highlights.map((highlight) => (
                <p key={highlight.text} className="m-0">
                  <span className={cn('rounded-[0.12rem] px-1 py-0.5 ring-1 transition-colors duration-300', toneStyles[highlight.tone].mark)}>
                    {highlight.text}
                  </span>{' '}
                  <span className="text-muted-foreground">
                    The selected section is shown as an agent-specific evidence marker for human review and validation.
                  </span>
                </p>
              ))}
              <p className="m-0 text-muted-foreground">
                Additional document paragraphs remain visible without highlights so reviewers can compare flagged passages against the surrounding academic context.
              </p>
            </div>
          </div>
        </main>

        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize document and analysis panels"
          className="group relative z-10 hidden cursor-col-resize touch-none bg-background lg:block"
          onPointerDown={handleResizePointerDown}
        >
          <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-border transition-colors group-hover:bg-foreground/50" />
          <div className="absolute inset-y-0 left-1/2 w-4 -translate-x-1/2 transition-colors group-hover:bg-foreground/5" />
        </div>

        <aside className="min-h-0 overflow-y-auto bg-background">
          <div className="border-b px-10 py-8">
            <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-5">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.26em] text-muted-foreground">Score Matrix Dashboard</p>
                <h2 className="mt-3 text-2xl font-semibold">Synthesized Agent View</h2>
                <p className="mt-3 text-lg text-muted-foreground">Advisory synthesis - Human review authoritative</p>
              </div>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div
                      className="grid size-32 shrink-0 place-items-center rounded-full"
                      style={{ background: `conic-gradient(#111827 ${synthesizedScore * 3.6}deg, #e5e7eb 0deg)` }}
                      aria-label={`Synthesized score ${synthesizedScore} percent`}
                    >
                      <div className="grid size-24 place-items-center rounded-full bg-background text-center shadow-inner">
                        <span className="text-3xl font-bold">{synthesizedScore}</span>
                        <span className="-mt-3 text-xs font-semibold text-muted-foreground">combined</span>
                      </div>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent sideOffset={8}>Average advisory score from all Layer 3 agents</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>

          <div className="px-10 py-8">
            <div className="grid gap-8">
              <section className="grid gap-4">
                <p className="text-xs font-semibold uppercase tracking-[0.26em] text-muted-foreground">Evaluation Agent</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  {agents.map((agent) => {
                    const Icon = agent.icon;
                    const isActive = agent.id === activeAgent.id;

                    return (
                      <button
                        key={agent.id}
                        type="button"
                        onClick={() => setActiveAgentId(agent.id)}
                        className={cn(
                          'flex min-h-20 items-center gap-4 rounded-lg border p-4 text-left transition-colors hover:border-foreground/30 hover:bg-muted/60',
                          isActive ? 'border-foreground/30 bg-foreground text-background shadow-sm' : 'border-border bg-background'
                        )}
                        aria-pressed={isActive}
                      >
                        <span className={cn('flex size-12 shrink-0 items-center justify-center rounded-md', isActive ? 'bg-background/15' : 'bg-muted')}>
                          <Icon className="size-5" aria-hidden="true" />
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate text-base font-semibold">{agent.label}</span>
                          <span className={cn('block truncate text-sm', isActive ? 'text-background/70' : 'text-muted-foreground')}>
                            {agent.role}
                          </span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              </section>

              <Separator />

              <section className="grid gap-4">
                <div className="flex items-start gap-4">
                  <CheckCircle2 className="mt-1 size-5 text-emerald-600" aria-hidden="true" />
                  <div>
                    <h3 className="text-xl font-semibold">{activeAgent.label}</h3>
                    <p className="mt-3 max-w-3xl text-base leading-7 text-muted-foreground">{activeAgent.summary}</p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-3 text-sm font-medium">
                  <span className="rounded-md bg-foreground px-3 py-1.5 text-background">{activeAgent.score}% individual score</span>
                  <span className="rounded-md border bg-background px-3 py-1.5 text-muted-foreground">{activeAgent.confidence}</span>
                </div>
              </section>

              <div className="overflow-hidden rounded-lg border">
                <Table>
                  <TableHeader className="bg-muted/60">
                    <TableRow className="hover:bg-muted/60">
                      <TableHead className="w-32 px-5 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Rating</TableHead>
                      <TableHead className="px-5 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Evaluation Criterion</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {activeAgent.criteria.map((criterion) => (
                      <TableRow key={criterion.label}>
                        <TableCell className="px-5 py-5 align-top whitespace-normal">
                          <div className={cn('w-fit rounded-md px-2.5 py-1.5 text-sm font-bold', toneStyles[criterion.tone].bg, toneStyles[criterion.tone].text)}>
                            {criterion.score}
                          </div>
                          <p className="mt-2 text-xs text-muted-foreground">{criterion.weight}% weight</p>
                        </TableCell>
                        <TableCell className="px-5 py-5 align-top whitespace-normal">
                          <div className="min-w-0">
                            <div className="flex items-center justify-between gap-3">
                              <h4 className="font-semibold">{criterion.label}</h4>
                              <span className={cn('size-2.5 shrink-0 rounded-full', toneStyles[criterion.tone].dot)} aria-hidden="true" />
                            </div>
                            <p className="mt-1 text-sm text-muted-foreground">{criterion.description}</p>
                            <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
                              <div className={cn('h-full rounded-full transition-all duration-500', toneStyles[criterion.tone].bar)} style={{ width: `${criterion.score}%` }} />
                            </div>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              <section className="grid gap-3">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="size-4 text-amber-600" aria-hidden="true" />
                  <h3 className="text-sm font-semibold">Feedback Comments</h3>
                </div>
                <FeedbackPanel comments={activeAgent.comments} />
              </section>
            </div>
          </div>
        </aside>
      </div>

      <Outlet />
    </section>
  );
}
