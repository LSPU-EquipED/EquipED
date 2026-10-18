import type { ReactNode } from "react";
import { ArrowRight } from "@phosphor-icons/react";
import { Button } from "@equiped/ui";
import { TARGET_AGENT_META, type TargetAgent } from "@equiped/types";
import { formatDateWithFallback } from "../../utils/dateFormatting";
import { specialistPresentation } from "../../utils/workspacePresentation";
import moduleDossier from "../../../../assets/illustrations/specialists/workspace/module-dossier.svg";
interface ModuleSetupViewProps {
  agent: TargetAgent;
  item: {
    title: string;
    course_code?: string | null;
    program?: string | null;
    uploaded_at?: string | null;
  };
  fields: ReactNode;
  onStart: () => void;
  onSelect: () => void;
  canStart: boolean;
  pending?: boolean;
}
export function ModuleSetupView({
  agent,
  item,
  fields,
  onStart,
  onSelect,
  canStart,
  pending = false,
}: ModuleSetupViewProps) {
  const meta = TARGET_AGENT_META[agent];
  const presentation = specialistPresentation[agent];
  return (
    <section className="swp-setup">
      <div className="swp-setup-top">
        <div>
          <h1>{item.title}</h1>
        </div>
        <button type="button" className="swp-text-action" onClick={onSelect}>
          Change module
        </button>
      </div>
      <div className="swp-setup-body">
        <div className="swp-setup-fields">
          <h2>Prepare the review</h2>
          <p className="swp-secondary">
            {meta.requiresCurriculum
              ? "Confirm the program and choose a verified curriculum."
              : "Confirm the program. This specialist reviews the module text directly."}
          </p>
          {fields}
        </div>
        <aside
          className="swp-setup-art"
          aria-label="Module input and review focus"
        >
          <img src={moduleDossier} alt="" aria-hidden="true" />
          <dl className="swp-input-meta">
            <div>
              <dt>Course</dt>
              <dd>{item.course_code || "Not provided"}</dd>
            </div>
            <div>
              <dt>Program</dt>
              <dd>{item.program || "Not provided"}</dd>
            </div>
            <div>
              <dt>Added</dt>
              <dd>
                {formatDateWithFallback(item.uploaded_at, "Date unavailable")}
              </dd>
            </div>
          </dl>
          <div className="swp-focus">
            <h2>Review focus</h2>
            <ul>
              {presentation.focus.map((focus) => (
                <li key={focus}>{focus}</li>
              ))}
            </ul>
          </div>
        </aside>
      </div>
      <footer className="swp-setup-footer">
        <p>
          Generated findings are advisory and remain available for your review.
        </p>
        <Button disabled={!canStart || pending} onClick={onStart}>
          {pending ? "Preparing review…" : "Start evaluation"}
          <ArrowRight size={16} aria-hidden="true" />
        </Button>
      </footer>
    </section>
  );
}
