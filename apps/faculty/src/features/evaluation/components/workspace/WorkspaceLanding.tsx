import { ArrowRight, Plus } from "@phosphor-icons/react";
import { Button } from "@equiped/ui";
import type { TargetAgent } from "@equiped/types";
import type { DeskQueueItem } from "../../types";
import { specialistModuleState } from "../../utils/specialistModuleState";
import { getWorkspaceOverview } from "../../utils/workspaceOverview";
import { formatDateWithFallback } from "../../utils/dateFormatting";
import { specialistPresentation } from "../../utils/workspacePresentation";

export function WorkspaceLanding({
  agent,
  items,
  onSelect,
  onOpen,
  onLibrary,
}: {
  agent: TargetAgent;
  items: DeskQueueItem[];
  onSelect: () => void;
  onOpen: (item: DeskQueueItem) => void;
  onLibrary: () => void;
}) {
  const presentation = specialistPresentation[agent];
  const empty = items.length === 0;
  const { waiting, complete, activeCount, recentItems } =
    getWorkspaceOverview(items);
  return (
    <div className={`swp-landing${empty ? " is-empty" : ""}`}>
      <section className="swp-welcome" aria-label="Specialist workspace">
        <div className="swp-welcome-copy">
          <h1>
            {empty ? "Your next review starts here." : presentation.heading}
          </h1>
          <p>
            {empty
              ? "Add a learning module to your library, then bring it here for specialist review."
              : presentation.description}
          </p>
          {empty ? (
            <Button onClick={onLibrary}>
              Open module library
              <ArrowRight size={16} aria-hidden="true" />
            </Button>
          ) : (
            <Button onClick={onSelect}>
              <Plus size={16} aria-hidden="true" />
              Select module
            </Button>
          )}
        </div>
        <div className="swp-welcome-art">
          <img src={presentation.image} alt="" aria-hidden="true" />
        </div>
      </section>
      {!empty && (
        <dl className="swp-counts" aria-label="Workspace summary">
          <div>
            <dt>Modules</dt>
            <dd>{items.length}</dd>
          </div>
          <div>
            <dt>Awaiting review</dt>
            <dd>{waiting}</dd>
          </div>
          <div>
            <dt>Completed here</dt>
            <dd>{complete}</dd>
          </div>
        </dl>
      )}
      {!empty && (
        <section className="swp-recent" aria-labelledby="recent-modules-title">
          <div className="swp-section-heading">
            <h2 id="recent-modules-title">Recent modules</h2>
            <span>
              {activeCount
                ? `${activeCount} evaluation${activeCount === 1 ? "" : "s"} in progress`
                : complete === items.length
                  ? "All modules reviewed here"
                  : `${recentItems.length} of ${items.length} modules`}
            </span>
          </div>
          <ul className="swp-module-list">
            {recentItems.map((item) => {
              const status = specialistModuleState(item.my_status);
              return (
                <li key={item.document_id}>
                  <div className="swp-module-copy">
                    <h3>{item.title}</h3>
                    <p>
                      {item.course_code} <span aria-hidden="true">·</span>{" "}
                      {item.program} <span aria-hidden="true">·</span>{" "}
                      {formatDateWithFallback(
                        item.uploaded_at,
                        "Date unavailable",
                      )}
                    </p>
                  </div>
                  <span className={`swp-module-status ${status.color}`}>
                    <span aria-hidden="true" />
                    {status.label}
                  </span>
                  <button
                    type="button"
                    className="swp-text-action"
                    onClick={() => onOpen(item)}
                    aria-label={`${status.action} ${item.title}`}
                  >
                    {status.action}
                    <ArrowRight size={15} aria-hidden="true" />
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </div>
  );
}
