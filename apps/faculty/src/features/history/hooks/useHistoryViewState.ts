import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { TargetAgent } from "@equiped/types";

type HistoryViewState = {
  status: string;
  role: TargetAgent;
  search: string;
  page: number;
  pageSize: number;
};
export function useHistoryViewState(defaultRole: TargetAgent, userId?: string) {
  const queryClient = useQueryClient();
  const key = ["history-view-state", userId];
  const [state, setState] = useState<HistoryViewState>(
    () =>
      (userId
        ? queryClient.getQueryData<HistoryViewState>(key)
        : undefined) ?? {
        status: "all",
        role: defaultRole,
        search: "",
        page: 1,
        pageSize: 10,
      },
  );
  const update = (patch: Partial<HistoryViewState>) => {
    const next = { ...state, ...patch };
    if (userId) {
      queryClient.setQueryDefaults(key, { gcTime: Infinity });
      queryClient.setQueryData(key, next);
    }
    setState(next);
  };
  return { ...state, update };
}
