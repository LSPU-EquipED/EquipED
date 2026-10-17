import type { DocumentSort } from "@equiped/api-client";
export type DocumentSortOption = DocumentSort;

export type StorageProgramFilter = "ALL" | "BSCS" | "BSInfoTech";
export type StorageStatusFilter = "all" | "PROCESSED" | "PROCESSING" | "FAILED";

export function mapStatusToApi(
  filter: StorageStatusFilter,
): "ready" | "processing" | "failed" | undefined {
  switch (filter) {
    case "PROCESSED":
      return "ready";
    case "PROCESSING":
      return "processing";
    case "FAILED":
      return "failed";
    default:
      return undefined;
  }
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}
