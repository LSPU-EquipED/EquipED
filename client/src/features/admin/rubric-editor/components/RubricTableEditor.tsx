import { Check, Pencil, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import {
  getRubricOperationError,
  useRubricSets,
  useUpdateCriterion,
  useUpdateDomain,
} from '../hooks/useRubrics';
import { AGENT_LABELS, type RubricCriterion } from '../types';

const STRUCTURAL_DISABLED_HINT = 'Structural editing (add / remove / rename) is coming soon';

type Draft = { title: string; description: string };

export function RubricTableEditor() {
  const { data, isLoading, isError, error } = useRubricSets();
  const updateCriterion = useUpdateCriterion();
  const updateDomain = useUpdateDomain();

  const [editingRowIds, setEditingRowIds] = useState<Set<string>>(new Set());
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});

  const startEditing = (criterion: RubricCriterion) => {
    setDrafts((current) => ({
      ...current,
      [criterion.rubric_criterion_id]: {
        title: criterion.title,
        description: criterion.description,
      },
    }));
    setEditingRowIds((current) => new Set(current).add(criterion.rubric_criterion_id));
  };

  const finishEditing = (criterion: RubricCriterion) => {
    const draft = drafts[criterion.rubric_criterion_id];
    const title = draft?.title.trim() ?? criterion.title;
    const description = draft?.description.trim() ?? criterion.description;

    if (
      title &&
      description &&
      (title !== criterion.title || description !== criterion.description)
    ) {
      updateCriterion.mutate({
        criterionId: criterion.rubric_criterion_id,
        body: { title, description },
      });
    }

    setEditingRowIds((current) => {
      const next = new Set(current);
      next.delete(criterion.rubric_criterion_id);
      return next;
    });
  };

  const updateDraft = (criterionId: string, key: keyof Draft, value: string) => {
    setDrafts((current) => ({
      ...current,
      [criterionId]: { ...current[criterionId], [key]: value },
    }));
  };

  const saveDomainTitle = (domainId: string, currentTitle: string, nextTitle: string) => {
    const trimmed = nextTitle.trim();
    if (trimmed && trimmed !== currentTitle) {
      updateDomain.mutate({ domainId, body: { title: trimmed } });
    }
  };

  if (isLoading) {
    return (
      <p className="text-sm font-medium text-slate-500 p-5" role="status">
        Loading rubrics…
      </p>
    );
  }

  if (isError) {
    return (
      <p
        role="alert"
        aria-live="assertive"
        className="text-sm font-semibold text-[#b91c1c] border border-[#b91c1c]/30 bg-[#b91c1c]/5 rounded-sm p-4"
      >
        {getRubricOperationError(error)}
      </p>
    );
  }

  const rubricSets = data?.rubric_sets ?? [];
  const mutationError = updateCriterion.isError
    ? updateCriterion.error
    : updateDomain.isError
      ? updateDomain.error
      : null;

  return (
    <section className="grid gap-5">
      {mutationError && (
        <p
          role="alert"
          aria-live="assertive"
          className="text-sm font-semibold text-[#b91c1c] border border-[#b91c1c]/30 bg-[#b91c1c]/5 rounded-sm p-3"
        >
          {getRubricOperationError(mutationError)}
        </p>
      )}

      <div className="grid gap-4">
        {rubricSets.map((rubricSet) => (
          <section
            key={rubricSet.rubric_set_id}
            className="grid gap-4 rounded-sm border border-slate-200 bg-white p-5"
          >
            <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 pb-3">
              <h2 className="text-lg font-bold text-slate-800 tracking-tight">
                {AGENT_LABELS[rubricSet.agent_id] ?? rubricSet.agent_id}
              </h2>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                {rubricSet.name} · v{rubricSet.version_number} · {rubricSet.status}
              </span>
              <button
                type="button"
                disabled
                title={STRUCTURAL_DISABLED_HINT}
                className="ml-auto inline-flex h-9 items-center justify-center border border-slate-200 text-slate-400 px-3 rounded-sm text-xs font-semibold tracking-wide uppercase cursor-not-allowed"
              >
                <Plus className="size-4 mr-1.5" aria-hidden="true" />
                Add Table
              </button>
            </div>

            {rubricSet.domains.map((domain) => (
              <div
                key={domain.rubric_domain_id}
                className="grid gap-3 rounded-sm border border-slate-200 p-4"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <div className="relative max-w-sm flex-1">
                    <Pencil
                      className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400"
                      aria-hidden="true"
                    />
                    <input
                      key={domain.title}
                      type="text"
                      defaultValue={domain.title}
                      onBlur={(event) =>
                        saveDomainTitle(domain.rubric_domain_id, domain.title, event.target.value)
                      }
                      className="w-full h-10 pl-9 pr-3 border border-slate-200 bg-white rounded-sm text-sm font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1b3b87]"
                      aria-label={`${domain.code} domain title`}
                    />
                  </div>
                  <button
                    type="button"
                    disabled
                    title={STRUCTURAL_DISABLED_HINT}
                    className="inline-flex h-10 items-center justify-center border border-slate-200 text-slate-400 px-3.5 rounded-sm text-xs font-semibold tracking-wide uppercase cursor-not-allowed"
                  >
                    <Plus className="size-4 mr-1.5" aria-hidden="true" />
                    Add Row
                  </button>
                  <button
                    type="button"
                    disabled
                    title={STRUCTURAL_DISABLED_HINT}
                    className="inline-flex size-10 items-center justify-center border border-transparent text-slate-300 rounded-sm cursor-not-allowed"
                    aria-label={`Remove ${domain.title} table`}
                  >
                    <Trash2 className="size-4" aria-hidden="true" />
                  </button>
                </div>

                <div className="border border-slate-200 bg-white rounded-sm overflow-x-auto">
                  <table className="w-full text-left border-collapse border-spacing-0">
                    <thead className="bg-slate-50 text-slate-600 uppercase text-[11px] tracking-wider font-semibold border-b border-slate-200">
                      <tr>
                        <th className="py-3 px-4 font-semibold text-slate-500 w-[9rem]">
                          Criterion ID
                        </th>
                        <th className="py-3 px-4 font-semibold text-slate-500 min-w-[12rem]">
                          Field
                        </th>
                        <th className="py-3 px-4 font-semibold text-slate-500 min-w-[20rem]">
                          Entry
                        </th>
                        <th className="py-3 px-4 font-semibold text-slate-500 w-[4rem] text-right">
                          Action
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      {domain.criteria.map((criterion) => {
                        const isEditing = editingRowIds.has(criterion.rubric_criterion_id);
                        const draft = drafts[criterion.rubric_criterion_id];
                        const titleValue = isEditing && draft ? draft.title : criterion.title;
                        const descriptionValue =
                          isEditing && draft ? draft.description : criterion.description;

                        return (
                          <tr key={criterion.rubric_criterion_id} className="hover:bg-slate-50/30">
                            <td className="py-2.5 px-4 text-sm font-medium">
                              <input
                                type="text"
                                value={criterion.criterion_code}
                                readOnly
                                className="w-full h-8 border border-transparent bg-transparent rounded-sm text-xs px-2 font-bold text-slate-800"
                                aria-label={`${domain.code} criterion ID`}
                              />
                            </td>
                            <td className="py-2.5 px-4 text-sm font-medium">
                              <input
                                type="text"
                                value={titleValue}
                                readOnly={!isEditing}
                                onChange={(event) =>
                                  updateDraft(
                                    criterion.rubric_criterion_id,
                                    'title',
                                    event.target.value,
                                  )
                                }
                                className="w-full h-8 border border-slate-200 bg-white rounded-sm text-xs px-2 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] read-only:border-transparent read-only:bg-transparent read-only:ring-0 font-semibold text-slate-800"
                                aria-label={`${criterion.criterion_code} title`}
                              />
                            </td>
                            <td className="py-2.5 px-4 text-sm font-medium whitespace-normal">
                              <input
                                type="text"
                                value={descriptionValue}
                                readOnly={!isEditing}
                                onChange={(event) =>
                                  updateDraft(
                                    criterion.rubric_criterion_id,
                                    'description',
                                    event.target.value,
                                  )
                                }
                                className="w-full h-8 border border-slate-200 bg-white rounded-sm text-xs px-2 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] read-only:border-transparent read-only:bg-transparent read-only:ring-0 font-medium text-slate-700"
                                aria-label={`${criterion.criterion_code} description`}
                              />
                            </td>
                            <td className="py-2.5 px-4 text-sm text-right">
                              <div className="flex justify-end gap-1">
                                <button
                                  type="button"
                                  onClick={() =>
                                    isEditing ? finishEditing(criterion) : startEditing(criterion)
                                  }
                                  className="inline-flex size-8 items-center justify-center border border-transparent text-slate-500 hover:text-[#1b3b87] hover:bg-slate-100/50 rounded-sm focus:outline-none transition-colors"
                                  aria-label={`${isEditing ? 'Finish editing' : 'Edit'} ${criterion.criterion_code} row`}
                                >
                                  {isEditing ? (
                                    <Check className="size-4" aria-hidden="true" />
                                  ) : (
                                    <Pencil className="size-4" aria-hidden="true" />
                                  )}
                                </button>
                                <button
                                  type="button"
                                  disabled
                                  title={STRUCTURAL_DISABLED_HINT}
                                  className="inline-flex size-8 items-center justify-center border border-transparent text-slate-300 rounded-sm cursor-not-allowed"
                                  aria-label={`Remove ${criterion.criterion_code} row`}
                                >
                                  <Trash2 className="size-4" aria-hidden="true" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                      {domain.criteria.length === 0 && (
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
            ))}
          </section>
        ))}

        {rubricSets.length === 0 && (
          <p className="text-sm font-medium text-slate-500 p-5">No active rubric sets found.</p>
        )}
      </div>
    </section>
  );
}
