import { Dropdown } from "@equiped/ui";
import type {
  DocumentSortOption,
  StorageProgramFilter,
  StorageStatusFilter,
} from "../utils/storage.utils";
export type { DocumentSortOption };

interface StorageToolbarProps {
  programFilter: StorageProgramFilter;
  setProgramFilter: (value: StorageProgramFilter) => void;
  statusFilter: StorageStatusFilter;
  setStatusFilter: (value: StorageStatusFilter) => void;
  sortOption?: DocumentSortOption;
  setSortOption?: (value: DocumentSortOption) => void;
}

export function StorageToolbar({
  programFilter,
  setProgramFilter,
  statusFilter,
  setStatusFilter,
  sortOption = "uploaded-desc",
  setSortOption,
}: StorageToolbarProps) {
  return (
    <div className="grid min-w-0 grid-cols-2 gap-3 sm:grid-cols-3">
      <Dropdown
        id="storage-program-filter"
        label="Program"
        size="md"
        value={programFilter}
        onChange={setProgramFilter}
        options={[
          { value: "ALL", label: "All programs" },
          { value: "BSCS", label: "BSCS" },
          { value: "BSInfoTech", label: "BSInfoTech" },
        ]}
        className="w-full"
        menuClassName="w-full"
      />
      <Dropdown
        id="storage-status-filter"
        label="File status"
        size="md"
        value={statusFilter}
        onChange={setStatusFilter}
        options={[
          { value: "all", label: "All files" },
          { value: "PROCESSED", label: "Processed" },
          { value: "PROCESSING", label: "Processing" },
          { value: "FAILED", label: "Upload failed" },
        ]}
        className="w-full"
        menuClassName="w-full"
      />
      {setSortOption && (
        <Dropdown
          id="storage-sort-select"
          label="Sort"
          size="md"
          value={sortOption}
          onChange={setSortOption}
          options={[
            { value: "uploaded-desc", label: "Newest first" },
            { value: "uploaded-asc", label: "Oldest first" },
            { value: "title-asc", label: "Title A–Z" },
            { value: "title-desc", label: "Title Z–A" },
            { value: "course-asc", label: "Course code" },
            { value: "pages-desc", label: "Most pages" },
          ]}
          containerClassName="col-span-2 sm:col-span-1"
          className="w-full"
          menuClassName="w-full"
        />
      )}
    </div>
  );
}
