// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useHistoryViewState } from "../useHistoryViewState";
afterEach(cleanup);
it("restores filters and pagination after viewing a result without leaking them to another account", () => {
  const client = new QueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const first = renderHook(() => useHistoryViewState("sme", "first-account"), {
    wrapper,
  });
  act(() =>
    first.result.current.update({
      status: "COMPLETED",
      role: "gad",
      search: "Networks",
      page: 3,
      pageSize: 20,
    }),
  );
  first.unmount();
  const restored = renderHook(
    () => useHistoryViewState("sme", "first-account"),
    { wrapper },
  );
  expect(restored.result.current).toMatchObject({
    status: "COMPLETED",
    role: "gad",
    search: "Networks",
    page: 3,
    pageSize: 20,
  });
  const other = renderHook(() => useHistoryViewState("sme", "other-account"), {
    wrapper,
  });
  expect(other.result.current).toMatchObject({
    status: "all",
    role: "sme",
    search: "",
    page: 1,
    pageSize: 10,
  });
});
