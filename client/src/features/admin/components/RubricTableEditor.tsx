import { Check, Pencil, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table';

type AgentRubricId = 'sme' | 'coordinator' | 'gad' | 'itso';

type AgentRubric = {
  id: AgentRubricId;
  agentName: string;
};

type RubricTable = {
  id: string;
  agentId: AgentRubricId;
  title: string;
};

type RubricCriterion = {
  id: string;
  tableId: string;
  criterionId: string;
  field: string;
  description: string;
};

const agents: AgentRubric[] = [
  { id: 'sme', agentName: 'Subject Matter Expert' },
  { id: 'coordinator', agentName: 'Program Coordinator' },
  { id: 'gad', agentName: 'GAD' },
  { id: 'itso', agentName: 'ITSO' },
];

const initialTables: RubricTable[] = [
  { id: 'sme-table-1', agentId: 'sme', title: 'Organization and Presentation' },
  { id: 'coordinator-table-1', agentId: 'coordinator', title: 'Assessment' },
  { id: 'gad-table-1', agentId: 'gad', title: 'Inclusivity and Gender Sensitivity' },
  { id: 'itso-table-1', agentId: 'itso', title: 'IP and Data Privacy' },
];

const initialRows: RubricCriterion[] = [
  {
    id: 'sme-1',
    tableId: 'sme-table-1',
    criterionId: 'OP-01',
    field: 'Content accuracy',
    description: 'Concepts, examples, and explanations align with course outcomes.',
  },
  {
    id: 'sme-2',
    tableId: 'sme-table-1',
    criterionId: 'OP-02',
    field: 'Instructional organization',
    description: 'Lessons follow a coherent sequence with clear learner guidance.',
  },
  {
    id: 'coordinator-1',
    tableId: 'coordinator-table-1',
    criterionId: 'A-01',
    field: 'Syllabus alignment',
    description: 'Activities and assessments map to the approved syllabus coverage.',
  },
  {
    id: 'coordinator-2',
    tableId: 'coordinator-table-1',
    criterionId: 'A-02',
    field: 'Assessment design',
    description: 'Assessment tasks measure the intended learning outcomes.',
  },
  {
    id: 'gad-1',
    tableId: 'gad-table-1',
    criterionId: 'GAD-01',
    field: 'Inclusive language',
    description: 'Text avoids biased assumptions and uses inclusive examples.',
  },
  {
    id: 'gad-2',
    tableId: 'gad-table-1',
    criterionId: 'GAD-02',
    field: 'Representation',
    description: 'Learning material reflects equitable gender representation.',
  },
  {
    id: 'itso-1',
    tableId: 'itso-table-1',
    criterionId: 'ITSO-01',
    field: 'IP compliance',
    description: 'Cited materials and media follow intellectual property requirements.',
  },
  {
    id: 'itso-2',
    tableId: 'itso-table-1',
    criterionId: 'ITSO-02',
    field: 'Data privacy',
    description: 'Examples, forms, and activities avoid unnecessary personal data exposure.',
  },
];

function createEmptyRow(agentId: AgentRubricId, tableId: string): RubricCriterion {
  return {
    id: `${agentId}-${crypto.randomUUID()}`,
    tableId,
    criterionId: '',
    field: '',
    description: '',
  };
}

function createEmptyTable(agentId: AgentRubricId, tableNumber: number): RubricTable {
  return {
    id: `${agentId}-table-${crypto.randomUUID()}`,
    agentId,
    title: `Rubric Table ${tableNumber}`,
  };
}

export function RubricTableEditor() {
  const [tables, setTables] = useState<RubricTable[]>(initialTables);
  const [rows, setRows] = useState<RubricCriterion[]>(initialRows);
  const [editingRowIds, setEditingRowIds] = useState<Set<string>>(new Set());

  const getTablesForAgent = (agentId: AgentRubricId) =>
    tables.filter((table) => table.agentId === agentId);

  const getRowsForTable = (tableId: string) => rows.filter((row) => row.tableId === tableId);

  const updateTableTitle = (tableId: string, title: string) => {
    setTables((current) =>
      current.map((table) => (table.id === tableId ? { ...table, title } : table)),
    );
  };

  const updateRow = (
    rowId: string,
    key: keyof Omit<RubricCriterion, 'id' | 'tableId'>,
    value: string,
  ) => {
    setRows((current) => current.map((row) => (row.id === rowId ? { ...row, [key]: value } : row)));
  };

  const addTable = (agentId: AgentRubricId) => {
    const table = createEmptyTable(agentId, getTablesForAgent(agentId).length + 1);

    setTables((current) => [...current, table]);
    setRows((current) => [...current, createEmptyRow(agentId, table.id)]);
  };

  const addRow = (agentId: AgentRubricId, tableId: string) => {
    const row = createEmptyRow(agentId, tableId);

    setRows((current) => [...current, row]);
    setEditingRowIds((current) => new Set(current).add(row.id));
  };

  const removeTable = (tableId: string) => {
    setTables((current) => current.filter((table) => table.id !== tableId));
    setRows((current) => current.filter((row) => row.tableId !== tableId));
  };

  const removeRow = (rowId: string) => {
    setRows((current) => current.filter((row) => row.id !== rowId));
    setEditingRowIds((current) => {
      const next = new Set(current);
      next.delete(rowId);
      return next;
    });
  };

  const toggleRowEditing = (rowId: string) => {
    setEditingRowIds((current) => {
      const next = new Set(current);

      if (next.has(rowId)) {
        next.delete(rowId);
      } else {
        next.add(rowId);
      }

      return next;
    });
  };

  return (
    <section className="grid gap-5">
      <div>
        <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
          Admin
        </div>
        <h1 className="mt-1 text-2xl font-semibold tracking-normal">Rubrics</h1>
      </div>

      <div className="grid gap-4">
        {agents.map((rubric) => {
          const agentTables = getTablesForAgent(rubric.id);

          return (
            <section
              key={rubric.id}
              className="grid gap-3 rounded-lg border bg-card p-4 text-card-foreground shadow-sm"
            >
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="text-lg font-semibold tracking-normal">{rubric.agentName}</h2>
                <Button
                  type="button"
                  variant="outline"
                  className="ml-auto gap-2"
                  onClick={() => addTable(rubric.id)}
                >
                  <Plus className="size-4" aria-hidden="true" />
                  Add table
                </Button>
              </div>

              {agentTables.map((table) => {
                const tableRows = getRowsForTable(table.id);

                return (
                  <div key={table.id} className="grid gap-2 rounded-lg border p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="relative max-w-sm flex-1">
                        <Pencil
                          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
                          aria-hidden="true"
                        />
                        <Input
                          value={table.title}
                          onChange={(event) => updateTableTitle(table.id, event.target.value)}
                          className="h-10 pl-9 text-base font-semibold"
                          aria-label={`${rubric.agentName} table title`}
                        />
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        className="gap-2"
                        onClick={() => addRow(rubric.id, table.id)}
                      >
                        <Plus className="size-4" aria-hidden="true" />
                        Add row
                      </Button>
                      {agentTables.length > 1 && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => removeTable(table.id)}
                          aria-label={`Remove ${table.title} table`}
                        >
                          <Trash2 className="size-4" aria-hidden="true" />
                        </Button>
                      )}
                    </div>

                    <div className="rounded-lg border">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="w-[9rem]">Criterion ID</TableHead>
                            <TableHead className="min-w-[12rem]">Field</TableHead>
                            <TableHead className="min-w-[20rem]">Entry</TableHead>
                            <TableHead className="w-[4rem] text-right">Action</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {tableRows.map((row) => {
                            const isEditing = editingRowIds.has(row.id);

                            return (
                              <TableRow key={row.id}>
                                <TableCell>
                                  <Input
                                    value={row.criterionId}
                                    readOnly={!isEditing}
                                    onChange={(event) =>
                                      updateRow(row.id, 'criterionId', event.target.value)
                                    }
                                    aria-label={`${table.title} criterion ID`}
                                  />
                                </TableCell>
                                <TableCell>
                                  <Input
                                    value={row.field}
                                    readOnly={!isEditing}
                                    onChange={(event) =>
                                      updateRow(row.id, 'field', event.target.value)
                                    }
                                    aria-label={`${table.title} field`}
                                  />
                                </TableCell>
                                <TableCell className="whitespace-normal">
                                  <Input
                                    value={row.description}
                                    readOnly={!isEditing}
                                    onChange={(event) =>
                                      updateRow(row.id, 'description', event.target.value)
                                    }
                                    aria-label={`${table.title} entry`}
                                  />
                                </TableCell>
                                <TableCell className="text-right">
                                  <div className="flex justify-end gap-1">
                                    <Button
                                      type="button"
                                      variant="ghost"
                                      size="icon"
                                      onClick={() => toggleRowEditing(row.id)}
                                      aria-label={`${isEditing ? 'Finish editing' : 'Edit'} ${row.criterionId || 'rubric'} row`}
                                    >
                                      {isEditing ? (
                                        <Check className="size-4" aria-hidden="true" />
                                      ) : (
                                        <Pencil className="size-4" aria-hidden="true" />
                                      )}
                                    </Button>
                                    <Button
                                      type="button"
                                      variant="ghost"
                                      size="icon"
                                      onClick={() => removeRow(row.id)}
                                      aria-label={`Remove ${row.criterionId || 'rubric'} row`}
                                    >
                                      <Trash2 className="size-4" aria-hidden="true" />
                                    </Button>
                                  </div>
                                </TableCell>
                              </TableRow>
                            );
                          })}
                          {tableRows.length === 0 && (
                            <TableRow>
                              <TableCell
                                colSpan={4}
                                className="h-16 text-center text-muted-foreground"
                              >
                                No rows in this table.
                              </TableCell>
                            </TableRow>
                          )}
                        </TableBody>
                      </Table>
                    </div>
                  </div>
                );
              })}

              {agentTables.length === 0 && (
                <div className="flex min-h-24 items-center justify-center rounded-lg border border-dashed">
                  <Button
                    type="button"
                    variant="outline"
                    className="gap-2"
                    onClick={() => addTable(rubric.id)}
                  >
                    <Plus className="size-4" aria-hidden="true" />
                    Add table
                  </Button>
                </div>
              )}
            </section>
          );
        })}
      </div>
    </section>
  );
}
