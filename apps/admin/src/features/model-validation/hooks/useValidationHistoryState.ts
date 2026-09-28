import { useEffect, useMemo, useState } from 'react';
import type { ModelValidationItem } from '../types';

export function useValidationHistoryState(items: ModelValidationItem[]) {
  const [expandedValidationId, setExpandedValidationId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSizeState] = useState(10);
  const [searchTerm, setSearchTermState] = useState('');
  const [statusFilter, setStatusFilterState] = useState('all');
  const [modelFilter, setModelFilterState] = useState('all');

  const hasActiveFilters =
    searchTerm.trim().length > 0 || statusFilter !== 'all' || modelFilter !== 'all';

  const filteredItems = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
    return items.filter((item) => {
      const matchesSearch =
        !normalizedSearch ||
        item.document_title?.toLowerCase().includes(normalizedSearch) ||
        item.validation_id.toLowerCase().includes(normalizedSearch);
      const matchesStatus = statusFilter === 'all' || item.status === statusFilter;
      const matchesModel = modelFilter === 'all' || item.model_variant === modelFilter;
      return Boolean(matchesSearch && matchesStatus && matchesModel);
    });
  }, [items, modelFilter, searchTerm, statusFilter]);

  const totalRecords = filteredItems.length;
  const totalPages = Math.max(1, Math.ceil(totalRecords / pageSize));
  const currentPage = Math.min(page, totalPages);
  const startRecord = totalRecords > 0 ? (currentPage - 1) * pageSize + 1 : 0;
  const endRecord = Math.min(currentPage * pageSize, totalRecords);
  const paginatedItems = useMemo(
    () => filteredItems.slice((currentPage - 1) * pageSize, currentPage * pageSize),
    [currentPage, filteredItems, pageSize],
  );

  useEffect(() => {
    if (!expandedValidationId) return undefined;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setExpandedValidationId(null);
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [expandedValidationId]);

  const selectedItem = items.find((item) => item.validation_id === expandedValidationId) ?? null;

  const resetFilters = () => {
    setSearchTermState('');
    setStatusFilterState('all');
    setModelFilterState('all');
    setPage(1);
  };

  const setPageSize = (value: number) => {
    setPageSizeState(value);
    setPage(1);
  };

  const setSearchTerm = (value: string) => {
    setSearchTermState(value);
    setPage(1);
  };

  const setStatusFilter = (value: string) => {
    setStatusFilterState(value);
    setPage(1);
  };

  const setModelFilter = (value: string) => {
    setModelFilterState(value);
    setPage(1);
  };

  return {
    expandedValidationId,
    setExpandedValidationId,
    pageSize,
    setPageSize,
    setPage,
    searchTerm,
    setSearchTerm,
    statusFilter,
    setStatusFilter,
    modelFilter,
    setModelFilter,
    hasActiveFilters,
    totalRecords,
    totalPages,
    currentPage,
    startRecord,
    endRecord,
    paginatedItems,
    selectedItem,
    resetFilters,
  };
}
