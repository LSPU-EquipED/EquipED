import { Check, Pencil, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';

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

      <div className="grid gap-4">
        {agents.map((rubric) => {
          const agentTables = getTablesForAgent(rubric.id);

          return (
            <section
              key={rubric.id}
              className="grid gap-4 rounded-sm border border-slate-200 bg-white p-5"
            >
              <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 pb-3">
                <h2 className="text-lg font-bold text-slate-800 tracking-tight">{rubric.agentName}</h2>
                <button
                  type="button"
                  className="ml-auto inline-flex h-9 items-center justify-center border border-slate-200 hover:bg-slate-50 text-slate-700 px-3 rounded-sm text-xs font-semibold tracking-wide uppercase transition-colors focus:outline-none focus:ring-2 focus:ring-slate-200"
                  onClick={() => addTable(rubric.id)}
                >
                  <Plus className="size-4 mr-1.5" aria-hidden="true" />
                  Add Table
                </button>
              </div>

              {agentTables.map((table) => {
                const tableRows = getRowsForTable(table.id);

                return (
                  <div key={table.id} className="grid gap-3 rounded-sm border border-slate-200 p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="relative max-w-sm flex-1">
                        <Pencil
                          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400"
                          aria-hidden="true"
                        />
                        <input
                          type="text"
                          value={table.title}
                          onChange={(event) => updateTableTitle(table.id, event.target.value)}
                          className="w-full h-10 pl-9 pr-3 border border-slate-200 bg-white rounded-sm text-sm font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
                          aria-label={`${rubric.agentName} table title`}
                        />
                      </div>
                      <button
                        type="button"
                        className="inline-flex h-10 items-center justify-center border border-slate-200 hover:bg-slate-50 text-slate-700 px-3.5 rounded-sm text-xs font-semibold tracking-wide uppercase transition-colors focus:outline-none focus:ring-2 focus:ring-slate-200"
                        onClick={() => addRow(rubric.id, table.id)}
                      >
                        <Plus className="size-4 mr-1.5" aria-hidden="true" />
                        Add Row
                      </button>
                      {agentTables.length > 1 && (
                        <button
                          type="button"
                          className="inline-flex size-10 items-center justify-center border border-transparent text-slate-500 hover:text-slate-750 hover:bg-slate-100/50 rounded-sm focus:outline-none transition-colors"
                          onClick={() => removeTable(table.id)}
                          aria-label={`Remove ${table.title} table`}
                        >
                          <Trash2 className="size-4" aria-hidden="true" />
                        </button>
                      )}
                    </div>

                    <div className="border border-slate-200 bg-white rounded-sm overflow-x-auto">
                      <table className="w-full text-left border-collapse border-spacing-0">
                        <thead className="bg-slate-50 text-slate-600 uppercase text-[11px] tracking-wider font-semibold border-b border-slate-200">
                          <tr>
                            <th className="py-3 px-4 font-semibold text-slate-500 w-[9rem]">Criterion ID</th>
                            <th className="py-3 px-4 font-semibold text-slate-500 min-w-[12rem]">Field</th>
                            <th className="py-3 px-4 font-semibold text-slate-500 min-w-[20rem]">Entry</th>
                            <th className="py-3 px-4 font-semibold text-slate-500 w-[4rem] text-right">Action</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200">
                          {tableRows.map((row) => {
                            const isEditing = editingRowIds.has(row.id);

                            return (
                              <tr key={row.id} className="hover:bg-slate-50/30">
                                <td className="py-2.5 px-4 text-sm font-medium">
                                  <input
                                    type="text"
                                    value={row.criterionId}
                                    readOnly={!isEditing}
                                    onChange={(event) =>
                                      updateRow(row.id, 'criterionId', event.target.value)
                                    }
                                    className="w-full h-8 border border-slate-205 bg-white rounded-sm text-xs px-2 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] read-only:border-transparent read-only:bg-transparent read-only:ring-0 font-bold text-slate-800 placeholder:text-slate-400"
                                    placeholder="ID"
                                    aria-label={`${table.title} criterion ID`}
                                  />
                                </td>
                                <td className="py-2.5 px-4 text-sm font-medium">
                                  <input
                                    type="text"
                                    value={row.field}
                                    readOnly={!isEditing}
                                    onChange={(event) =>
                                      updateRow(row.id, 'field', event.target.value)
                                    }
                                    className="w-full h-8 border border-slate-205 bg-white rounded-sm text-xs px-2 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] read-only:border-transparent read-only:bg-transparent read-only:ring-0 font-semibold text-slate-800 placeholder:text-slate-400"
                                    placeholder="Field"
                                    aria-label={`${table.title} field`}
                                  />
                                </td>
                                <td className="py-2.5 px-4 text-sm font-medium whitespace-normal">
                                  <input
                                    type="text"
                                    value={row.description}
                                    readOnly={!isEditing}
                                    onChange={(event) =>
                                      updateRow(row.id, 'description', event.target.value)
                                    }
                                    className="w-full h-8 border border-slate-205 bg-white rounded-sm text-xs px-2 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] read-only:border-transparent read-only:bg-transparent read-only:ring-0 font-medium text-slate-700 placeholder:text-slate-400"
                                    placeholder="Description"
                                    aria-label={`${table.title} entry`}
                                  />
                                </td>
                                <td className="py-2.5 px-4 text-sm text-right">
                                  <div className="flex justify-end gap-1">
                                    <button
                                      type="button"
                                      onClick={() => toggleRowEditing(row.id)}
                                      className="inline-flex size-8 items-center justify-center border border-transparent text-slate-500 hover:text-[#1b3b87] hover:bg-slate-100/50 rounded-sm focus:outline-none transition-colors"
                                      aria-label={`${isEditing ? 'Finish editing' : 'Edit'} ${row.criterionId || 'rubric'} row`}
                                    >
                                      {isEditing ? (
                                        <Check className="size-4" aria-hidden="true" />
                                      ) : (
                                        <Pencil className="size-4" aria-hidden="true" />
                                      )}
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => removeRow(row.id)}
                                      className="inline-flex size-8 items-center justify-center border border-transparent text-slate-500 hover:text-red-700 hover:bg-red-50/50 rounded-sm focus:outline-none transition-colors"
                                      aria-label={`Remove ${row.criterionId || 'rubric'} row`}
                                    >
                                      <Trash2 className="size-4" aria-hidden="true" />
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                          {tableRows.length === 0 && (
                            <tr>
                              <td
                                colSpan={4}
                                className="py-6 text-center text-xs font-semibold text-slate-400 uppercase tracking-wider bg-slate-50/10"
                              >
                                No rows in this table.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                );
              })}

              {agentTables.length === 0 && (
                <div className="flex min-h-24 items-center justify-center rounded-sm border border-dashed border-slate-200 bg-slate-50/30">
                  <button
                    type="button"
                    className="inline-flex h-9 items-center justify-center border border-slate-200 hover:bg-slate-50 text-slate-700 px-3 rounded-sm text-xs font-semibold tracking-wide uppercase transition-colors focus:outline-none"
                    onClick={() => addTable(rubric.id)}
                  >
                    <Plus className="size-4 mr-1.5" aria-hidden="true" />
                    Add Table
                  </button>
                </div>
              )}
            </section>
          );
        })}
      </div>
    </section>
  );
}
