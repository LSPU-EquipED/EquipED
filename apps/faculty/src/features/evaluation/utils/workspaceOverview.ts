import type { DeskQueueItem } from "../types";
import { isActiveEvaluationStatus } from "./evaluationProgress";

/** Keeps every active review accessible before filling the remaining recent slots. */
export function getWorkspaceOverview(items: readonly DeskQueueItem[]) {
  const active: DeskQueueItem[] = [];
  const other: DeskQueueItem[] = [];
  let waiting = 0;
  let complete = 0;

  for (const item of items) {
    if (
      ["READY", "PENDING", "FAILED", ""].includes(
        (item.my_status || "").toUpperCase(),
      )
    ) {
      waiting += 1;
    }
    if (item.my_status === "COMPLETED") complete += 1;
    if (isActiveEvaluationStatus(item.my_status)) active.push(item);
    else other.push(item);
  }

  return {
    waiting,
    complete,
    activeCount: active.length,
    recentItems: [...active, ...other].slice(0, Math.max(3, active.length)),
  };
}
