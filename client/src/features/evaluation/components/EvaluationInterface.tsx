import {
  BookOpen,
  CheckCircle2,
  FileText,
  Lightbulb,
  Scale,
  ShieldCheck,
  Target,
} from 'lucide-react';
import { useState, type PointerEvent } from 'react';
import { Button } from '@/shared/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table';
import { cn } from '@/shared/components/utils';
import { EvaluationStatusBanner } from './EvaluationStatusBanner';
import { FeedbackPanel } from './FeedbackPanel';
import { FlagList } from './FlagList';

const agents = [
  {
    id: 'coordinator',
    name: 'Program Coordinator',
    subtitle: 'Curriculum alignment',
    icon: BookOpen,
  },
  {
    id: 'sme',
    name: 'Subject Matter Expert (SME)',
    subtitle: 'Discipline accuracy',
    icon: Lightbulb,
  },
  {
    id: 'gad',
    name: 'GAD Unit',
    subtitle: 'Gender and development review',
    icon: Scale,
  },
  {
    id: 'itso',
    name: 'ITSO',
    subtitle: 'Innovation and compliance',
    icon: ShieldCheck,
  },
] as const;

type AgentId = (typeof agents)[number]['id'];

const agentScores: Record<
  AgentId,
  {
    score: number;
    verdict: string;
    summary: string;
    feedbackComments: readonly string[];
    evidenceFlags: readonly string[];
    rows: readonly {
      rating: string;
      criterion: string;
      status: string;
    }[];
  }
> = {
  coordinator: {
    score: 82,
    verdict: 'Alignment review needed',
    summary:
      'The module generally follows the syllabus sequence, but assessment evidence should better map to intended outcomes.',
    feedbackComments: [
      'Confirm that activities are mapped to the approved syllabus topics and weekly outcomes.',
      'Ask the reviewer to connect summative assessments to specific learning competencies.',
      'Check whether prerequisite concepts are introduced before applied tasks.',
    ],
    evidenceFlags: [
      'Course outcomes are visible in the learning module overview.',
      'Assessment instructions need clearer links to syllabus competencies.',
      'Module sequencing is mostly aligned with the expected course flow.',
    ],
    rows: [
      {
        rating: '4',
        criterion: 'Learning outcomes are aligned with the approved syllabus coverage.',
        status: 'Mostly aligned',
      },
      {
        rating: '3',
        criterion: 'Assessment tasks measure the stated course competencies.',
        status: 'Needs mapping',
      },
      {
        rating: '5',
        criterion: 'Lessons are sequenced according to prerequisite knowledge.',
        status: 'Acceptable',
      },
    ],
  },
  sme: {
    score: 88,
    verdict: 'Discipline content acceptable',
    summary:
      'Core explanations are accurate and well organized, with minor opportunities to strengthen examples and learner checks.',
    feedbackComments: [
      'Validate technical terms against the department reference material.',
      'Add one worked example before the independent learning activity.',
      'Keep the concept progression because it supports self-paced comprehension.',
    ],
    evidenceFlags: [
      'Content accuracy is supported by direct explanations and examples.',
      'One concept would benefit from a clearer transition before practice tasks.',
      'Instructional organization supports independent learner pacing.',
    ],
    rows: [
      {
        rating: '5',
        criterion: 'Discipline concepts are accurate and appropriate for the course level.',
        status: 'Acceptable',
      },
      {
        rating: '4',
        criterion: 'Examples reinforce the concept before learner application.',
        status: 'Minor revision',
      },
      {
        rating: '4',
        criterion: 'Instructional flow supports self-paced learning.',
        status: 'Acceptable',
      },
    ],
  },
  gad: {
    score: 79,
    verdict: 'Inclusivity review recommended',
    summary:
      'The module uses generally inclusive language, but examples should include broader representation and avoid narrow role assumptions.',
    feedbackComments: [
      'Review examples for balanced gender representation across roles and scenarios.',
      'Replace role-specific assumptions with neutral or inclusive alternatives.',
      'Add inclusive learner-facing language in activity instructions.',
    ],
    evidenceFlags: [
      'Inclusive wording appears in the main learning instructions.',
      'Some examples rely on narrow role assumptions that should be revised.',
      'Representation can be broadened in case-based activities.',
    ],
    rows: [
      {
        rating: '4',
        criterion: 'Language avoids biased assumptions and exclusionary framing.',
        status: 'Mostly acceptable',
      },
      {
        rating: '3',
        criterion: 'Examples represent learners and stakeholders equitably.',
        status: 'Review recommended',
      },
      {
        rating: '4',
        criterion: 'Activities remain accessible to diverse learner contexts.',
        status: 'Acceptable',
      },
    ],
  },
  itso: {
    score: 78,
    verdict: 'Review recommended',
    summary:
      'Innovation claims are promising, but documentation should better identify originality and ownership evidence.',
    feedbackComments: [
      'Confirm whether the digital artifact is original work, licensed material, or adapted from a cited source.',
      'Ask the faculty reviewer to add reuse permissions for screenshots and prototype references.',
      'Keep the advisory score pending until ownership evidence is attached to the source document.',
    ],
    evidenceFlags: [
      'Clear instructional purpose and deployment path are supported by the selected passage.',
      'Ownership, reuse permissions, and attribution need stronger documentation.',
      'Innovation indicators should be connected to measurable course deliverables.',
    ],
    rows: [
      {
        rating: '4',
        criterion: 'Originality and innovation claims are supported by concrete evidence.',
        status: 'Review recommended',
      },
      {
        rating: '3',
        criterion: 'Third-party materials include ownership, reuse, and attribution details.',
        status: 'Needs citation check',
      },
      {
        rating: '5',
        criterion: 'Data privacy exposure is limited in examples and learning activities.',
        status: 'Acceptable',
      },
    ],
  },
};

function Highlight({
  children,
  tone,
}: {
  children: string;
  tone: 'good' | 'risk' | 'warning';
}) {
  return (
    <span
      className={cn(
        'box-decoration-clone rounded-sm px-1 py-0.5 text-foreground',
        tone === 'good' && 'bg-emerald-100 ring-1 ring-emerald-300',
        tone === 'risk' && 'bg-red-100 ring-1 ring-red-300',
        tone === 'warning' && 'bg-amber-100 ring-1 ring-amber-300'
      )}
    >
      {children}
    </span>
  );
}

export function EvaluationInterface() {
  const [selectedAgentId, setSelectedAgentId] = useState<AgentId>('itso');
  const [leftPaneSize, setLeftPaneSize] = useState(48);
  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId) ?? agents[0];
  const selectedScore = agentScores[selectedAgent.id];
  const scoreRingStyle = {
    background: `conic-gradient(var(--foreground) ${selectedScore.score * 3.6}deg, var(--muted) 0deg)`,
  };

  const handleDividerPointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    const container = event.currentTarget.parentElement;

    if (!container) {
      return;
    }

    const bounds = container.getBoundingClientRect();

    const handlePointerMove = (moveEvent: globalThis.PointerEvent) => {
      const nextSize = ((moveEvent.clientX - bounds.left) / bounds.width) * 100;
      setLeftPaneSize(Math.min(64, Math.max(36, nextSize)));
    };

    const handlePointerUp = () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };

    event.currentTarget.setPointerCapture(event.pointerId);
    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
  };

  return (
    <section className="-mx-6 -my-7 flex h-[calc(100vh-4rem)] min-h-0 flex-col bg-background">
      <header className="flex min-h-24 shrink-0 items-center justify-between gap-4 border-b bg-background px-10">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.26em] text-muted-foreground">Selected Document</p>
          <h1 className="mt-2 truncate text-2xl font-semibold tracking-normal">
            Instructional Material Evaluation Draft
          </h1>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button type="button" variant="outline" className="gap-2">
            <FileText className="size-4" aria-hidden="true" />
            Source
          </Button>
          <Button type="button">Finalize Review</Button>
        </div>
      </header>

      <div
        className="grid min-h-0 flex-1"
        style={{
          gridTemplateColumns: `minmax(24rem, ${leftPaneSize}fr) 0.25rem minmax(28rem, ${100 - leftPaneSize}fr)`,
        }}
      >
        <section className="min-h-0 overflow-y-auto bg-background">
          <div className="mx-auto grid max-w-3xl gap-7 px-10 py-16">
            <div className="flex items-start justify-between gap-4 border-b pb-6">
              <div>
                <h2 className="text-base font-semibold">Course Pack: Outcomes-Based Learning Module</h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  Author: Faculty Reviewer - Date: May 19, 2026
                </p>
              </div>
              <Button type="button" variant="outline" className="shrink-0">
                {selectedAgent.name}
              </Button>
            </div>

            <article className="space-y-6 text-xl leading-9 text-muted-foreground">
              <p>
                <Highlight tone="good">
                  The proposed digital artifact has a clear instructional purpose and deployment path.
                </Highlight>{' '}
                The selected section is shown as an agent-specific evidence marker for human review and
                validation.
              </p>
              <p>
                <Highlight tone="risk">
                  Ownership, reuse permissions, and attribution expectations need to be stated more directly.
                </Highlight>{' '}
                The selected section is shown as an agent-specific evidence marker for human review and
                validation.
              </p>
              <p>
                <Highlight tone="warning">
                  Innovation indicators should be connected to measurable course deliverables.
                </Highlight>{' '}
                The selected section is shown as an agent-specific evidence marker for human review and
                validation.
              </p>
              <p>
                Additional document paragraphs remain visible without highlights so reviewers can compare flagged
                passages against the surrounding instructional context and decide whether the advisory finding is
                valid.
              </p>
              <p>
                The module may include screenshots, sample datasets, and prototype references. Reviewers should
                confirm whether all supporting materials are locally owned, licensed, or properly cited before final
                acceptance.
              </p>
            </article>

            <FlagList flags={selectedScore.evidenceFlags} />
          </div>
        </section>

        <button
          type="button"
          className="group relative min-h-0 cursor-col-resize bg-border outline-none transition-colors hover:bg-foreground/50 focus-visible:bg-foreground/50"
          onPointerDown={handleDividerPointerDown}
          aria-label="Resize document and score panels"
        >
          <span className="absolute inset-y-0 left-1/2 w-1 -translate-x-1/2" />
        </button>

        <section className="min-h-0 overflow-y-auto bg-card">
          <div className="flex min-h-44 items-center justify-between gap-6 border-b px-10">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.26em] text-muted-foreground">
                Score Matrix Dashboard
              </p>
              <h2 className="mt-3 text-2xl font-semibold tracking-normal">Synthesized Agent View</h2>
              <p className="mt-2 text-base text-muted-foreground">Advisory synthesis - Human review authoritative</p>
            </div>
            <div className="grid size-28 place-items-center rounded-full p-3" style={scoreRingStyle}>
              <div className="grid size-full place-items-center rounded-full bg-background">
                <div className="text-center">
                  <div className="text-3xl font-bold">{selectedScore.score}</div>
                  <div className="text-xs text-muted-foreground">score</div>
                </div>
              </div>
            </div>
          </div>

          <div className="px-10 py-8">
            <EvaluationStatusBanner />

            <p className="mb-4 mt-8 text-xs font-semibold uppercase tracking-[0.26em] text-muted-foreground">
              Evaluation Agent
            </p>
            <div className="grid gap-3 xl:grid-cols-2">
              {agents.map((agent) => {
                const Icon = agent.icon;
                const isActive = agent.id === selectedAgentId;

                return (
                  <button
                    key={agent.name}
                    type="button"
                    onClick={() => setSelectedAgentId(agent.id)}
                    className={cn(
                      'flex min-h-20 items-center gap-4 rounded-lg border p-4 text-left shadow-sm transition-colors',
                      isActive
                        ? 'border-foreground bg-foreground text-background'
                        : 'bg-background hover:bg-muted/60'
                    )}
                    aria-pressed={isActive}
                  >
                    <span
                      className={cn(
                        'grid size-12 shrink-0 place-items-center rounded-lg',
                        isActive ? 'bg-background/15' : 'bg-muted'
                      )}
                    >
                      <Icon className="size-5" aria-hidden="true" />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate font-semibold">{agent.name}</span>
                      <span className={cn('mt-1 block text-sm', isActive ? 'text-background/75' : 'text-muted-foreground')}>
                        {agent.subtitle}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>

            <section className="mt-10 grid gap-4">
              <div className="flex items-start gap-4">
                <CheckCircle2 className="mt-1 size-5 shrink-0 text-emerald-600" aria-hidden="true" />
                <div>
                  <h3 className="text-lg font-semibold">{selectedAgent.name}</h3>
                  <p className="mt-2 max-w-3xl text-muted-foreground">
                    {selectedScore.summary}
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <span className="rounded-md bg-foreground px-3 py-1.5 text-sm font-semibold text-background">
                  {selectedScore.score}% individual score
                </span>
                <span className="rounded-md border px-3 py-1.5 text-sm text-muted-foreground">
                  {selectedScore.verdict}
                </span>
              </div>

              <div className="rounded-lg border bg-background">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[8rem] uppercase tracking-[0.18em]">Rating</TableHead>
                      <TableHead className="uppercase tracking-[0.18em]">Evaluation Criterion</TableHead>
                      <TableHead className="w-[14rem] uppercase tracking-[0.18em]">Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {selectedScore.rows.map((row) => (
                      <TableRow key={row.criterion}>
                        <TableCell>
                          <span className="inline-grid size-9 place-items-center rounded-full bg-muted font-semibold">
                            {row.rating}
                          </span>
                        </TableCell>
                        <TableCell className="whitespace-normal text-muted-foreground">{row.criterion}</TableCell>
                        <TableCell className="whitespace-normal">
                          <span className="rounded-md border px-2 py-1 text-xs text-muted-foreground">
                            {row.status}
                          </span>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              <FeedbackPanel comments={selectedScore.feedbackComments} />
            </section>

            <section className="mt-8 rounded-lg border bg-background p-5">
              <div className="flex items-center gap-2">
                <Target className="size-4 text-muted-foreground" aria-hidden="true" />
                <h3 className="font-semibold">Reviewer Decision</h3>
              </div>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                Human reviewer may accept the advisory score, revise the agent finding, or return the document for
                clarification before final review.
              </p>
            </section>
          </div>
        </section>
      </div>
    </section>
  );
}
