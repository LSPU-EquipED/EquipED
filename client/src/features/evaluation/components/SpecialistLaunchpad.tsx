import { BookOpen, Play } from '@phosphor-icons/react';
import { Badge } from '@/shared/components/Badge';
import { Button } from '@/shared/components/Button';
import type { ClientDocument } from '@/shared/types/documents';
import type { TargetAgentMeta } from '@/shared/types/evaluations';
import type { DeskQueueItem } from '../types';

function formatUploadDate(dateString?: string | null): string {
  if (!dateString) return '—';
  try {
    const d = new Date(dateString);
    if (Number.isNaN(d.getTime())) return '—';
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return '—';
  }
}

export interface SpecialistLaunchpadProps {
  activeItem: DeskQueueItem | null;
  activeDocument: ClientDocument | null;
  meta: TargetAgentMeta;
  onLaunch: () => void;
}

export function SpecialistLaunchpad({
  activeItem,
  activeDocument,
  meta,
  onLaunch,
}: SpecialistLaunchpadProps) {
  return (
    <div className="rounded-md border border-border bg-surface p-6 sm:p-8 space-y-6 max-w-4xl mx-auto">
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Badge variant="info">{meta.shortLabel} Desk Review</Badge>
          <Badge variant="neutral">Unevaluated</Badge>
        </div>
        <h2 className="text-lg font-bold text-text">
          {activeItem?.title || activeDocument?.title}
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
          <div className="rounded-sm border border-border bg-surface-subtle p-3">
            <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block">
              Course Code
            </span>
            <span className="text-xs font-mono font-bold text-text mt-0.5 block">
              {activeItem?.course_code || activeDocument?.courseCode || 'N/A'}
            </span>
          </div>
          <div className="rounded-sm border border-border bg-surface-subtle p-3">
            <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block">
              Program
            </span>
            <span className="text-xs font-mono font-bold text-text mt-0.5 block">
              {activeItem?.program || activeDocument?.program || 'General'}
            </span>
          </div>
          <div className="rounded-sm border border-border bg-surface-subtle p-3">
            <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block">
              Academic Year
            </span>
            <span className="text-xs font-mono font-bold text-text mt-0.5 block">
              {activeDocument?.academicYear || 'N/A'}
            </span>
          </div>
          <div className="rounded-sm border border-border bg-surface-subtle p-3">
            <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted block">
              Uploaded
            </span>
            <span className="text-xs font-mono font-bold text-text mt-0.5 block">
              {formatUploadDate(activeItem?.uploaded_at || activeDocument?.uploadedAt)}
            </span>
          </div>
        </div>
      </div>

      {/* Syllabus Alignment Notice */}
      <div className="rounded-sm border border-primary/20 bg-primary/5 p-4 flex items-start gap-3.5">
        <BookOpen className="size-5 text-primary shrink-0 mt-0.5" aria-hidden="true" />
        <div className="space-y-1 text-xs">
          <span className="font-bold text-text block">
            Syllabus Alignment Notice
          </span>
          <p className="text-text-muted leading-relaxed">
            Module content will be automatically verified against approved syllabus learning outcomes, course competencies, and {meta.fullName} rubric criteria. Grounded excerpts and citations will be captured during evaluation.
          </p>
        </div>
      </div>

      {/* Primary Action Button */}
      <div className="pt-2">
        <Button
          type="button"
          variant="primary"
          size="md"
          onClick={onLaunch}
          className="font-bold uppercase tracking-wider text-xs gap-2"
        >
          <Play className="size-3.5 fill-current" weight="fill" aria-hidden="true" />
          <span>Launch Evaluation (~20-30s)</span>
        </Button>
      </div>
    </div>
  );
}
