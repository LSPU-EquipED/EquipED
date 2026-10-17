import { TableSkeleton } from "@equiped/ui";

export function DocumentTableSkeleton({
  hasMultipleTypes = false,
}: {
  hasMultipleTypes?: boolean;
}) {
  const columns = [
    {
      label: "Module",
      headerClassName: hasMultipleTypes
        ? "sm:w-[40%] sm:min-w-[16rem] pl-4 sm:pl-6 pr-3.5 align-middle"
        : "sm:w-[44%] sm:min-w-[16rem] pl-4 sm:pl-6 pr-3.5 align-middle",
      cellClassName: hasMultipleTypes
        ? "sm:w-[40%] sm:min-w-[16rem] pl-4 sm:pl-6 pr-3.5 align-middle"
        : "sm:w-[44%] sm:min-w-[16rem] pl-4 sm:pl-6 pr-3.5 align-middle",
      skeletonClassName: "h-4 w-48",
    },
    {
      label: "Course",
      headerClassName: hasMultipleTypes
        ? "w-[24%] min-w-[12rem] px-3.5 align-middle"
        : "w-[28%] min-w-[13rem] px-3.5 align-middle",
      cellClassName: hasMultipleTypes
        ? "w-[24%] min-w-[12rem] px-3.5 align-middle"
        : "w-[28%] min-w-[13rem] px-3.5 align-middle",
      skeletonClassName: "h-4 w-36",
    },
    {
      label: "Program",
      headerClassName: "w-28 min-w-[6.5rem] px-3.5 align-middle",
      cellClassName: "w-28 min-w-[6.5rem] px-3.5 align-middle",
      skeletonClassName: "h-5 w-14",
    },
    ...(hasMultipleTypes
      ? [
          {
            label: "Type",
            headerClassName: "w-28 min-w-[6.5rem] px-3.5 align-middle",
            cellClassName: "w-28 min-w-[6.5rem] px-3.5 align-middle",
            skeletonClassName: "h-4 w-20",
          },
        ]
      : []),
    {
      label: "Uploaded",
      headerClassName: hasMultipleTypes
        ? "w-32 min-w-[7rem] px-3.5 align-middle"
        : "w-32 min-w-[8rem] px-3.5 align-middle",
      cellClassName: hasMultipleTypes
        ? "w-32 min-w-[7rem] px-3.5 align-middle"
        : "w-32 min-w-[8rem] px-3.5 align-middle",
      skeletonClassName: "h-4 w-20",
    },
    {
      label: "Actions",
      headerClassName:
        "w-24 min-w-[6rem] pl-2 pr-4 sm:pr-6 text-right align-middle",
      cellClassName: "w-24 min-w-[6rem] pl-2 pr-4 sm:pr-6 align-middle",
      skeletonClassName: "size-10 ml-auto",
    },
  ];

  return (
    <TableSkeleton
      ariaLabel="Loading document inventory"
      tableClassName="w-full table-fixed sm:min-w-[44rem]"
      columns={columns.map((column) => {
        if (column.label === "Module") return column;
        const responsive =
          column.label === "Actions" ? "w-20 min-w-20" : "hidden sm:table-cell";
        return {
          ...column,
          headerClassName: `${column.headerClassName} ${responsive}`,
          cellClassName: `${column.cellClassName} ${responsive}`,
        };
      })}
    />
  );
}
