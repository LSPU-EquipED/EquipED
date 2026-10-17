import { useEffect, useMemo, useState } from "react";
import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { documentsApi } from "@equiped/api-client";
import type { ListDocumentsParams } from "@equiped/api-client";
import type { ClientDocument } from "@equiped/types";
import {
  type DocumentSortOption,
  mapStatusToApi,
  type StorageProgramFilter,
  type StorageStatusFilter,
} from "../utils/storage.utils";

export type { StorageProgramFilter, StorageStatusFilter };

const EMPTY_DOCUMENTS: ClientDocument[] = [];
export function useSlmStorage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [programFilter, setProgramFilter] =
    useState<StorageProgramFilter>("ALL");
  const [statusFilter, setStatusFilter] = useState<StorageStatusFilter>("all");
  const [sortOption, setSortOption] =
    useState<DocumentSortOption>("uploaded-desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // Modals & Drawer state
  const [inspectingDoc, setInspectingDoc] = useState<ClientDocument | null>(
    null,
  );
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  const handleSetSearch = (val: string) => {
    setSearch(val);
    setPage(1);
  };

  const handleSetProgramFilter = (val: StorageProgramFilter) => {
    setProgramFilter(val);
    setPage(1);
  };

  const handleSetStatusFilter = (val: StorageStatusFilter) => {
    setStatusFilter(val);
    setPage(1);
  };

  const queryParams: ListDocumentsParams = useMemo(() => {
    const trimmed = search.trim();
    const apiStatus = mapStatusToApi(statusFilter);
    return {
      sourceType: "slm",
      sort: sortOption,
      program: programFilter !== "ALL" ? programFilter : undefined,
      status: apiStatus,
      search: trimmed || undefined,
      page,
      pageSize,
    };
  }, [search, programFilter, statusFilter, sortOption, page, pageSize]);

  const { data, error, isLoading, isFetching, isPlaceholderData, refetch } =
    useQuery({
      queryKey: ["slm-storage-repository", queryParams],
      queryFn: () => documentsApi.listDocuments(queryParams),
      placeholderData: keepPreviousData,
    });

  const documents = data?.items ?? EMPTY_DOCUMENTS;
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / pageSize) || 1;

  // Adjust page boundary if total reduced
  useEffect(() => {
    if (data && !isPlaceholderData && totalPages > 0 && page > totalPages) {
      setPage(totalPages);
    }
  }, [data, isPlaceholderData, page, totalPages]);

  const handleUploadComplete = () => {
    setIsUploadOpen(false);
    void queryClient.invalidateQueries({
      queryKey: ["slm-storage-repository"],
    });
  };

  return {
    sortOption,
    setSortOption: (value: DocumentSortOption) => {
      setSortOption(value);
      setPage(1);
    },
    resetFilters: () => {
      setSearch("");
      setProgramFilter("ALL");
      setStatusFilter("all");
      setPage(1);
    },
    isFetching,
    refetch,
    // Data & status
    documents,
    total,
    page,
    setPage,
    pageSize,
    setPageSize,
    totalPages,
    isLoading,
    error,
    // Filters & Search
    search,
    setSearch: handleSetSearch,
    programFilter,
    setProgramFilter: handleSetProgramFilter,
    statusFilter,
    setStatusFilter: handleSetStatusFilter,
    // Interactive state
    inspectingDoc,
    setInspectingDoc,
    isUploadOpen,
    setIsUploadOpen,
    handleUploadComplete,
  };
}
