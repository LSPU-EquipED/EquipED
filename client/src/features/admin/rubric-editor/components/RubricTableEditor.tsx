import { useMemo, useState } from 'react';
import {
  ArrowDown,
  ArrowRightLeft,
  ArrowUp,
  Check,
  CheckCircle,
  FileCheck,
  History,
  Lock,
  Pencil,
  Plus,
  Trash2,
} from 'lucide-react';
import {
  getRubricOperationError,
  getValidationReportFromError,
  useActivateRevision,
  useCreateCriterion,
  useCreateDomain,
  useCreateDraft,
  useDeleteCriterion,
  useDeleteDomain,
  useDeleteDraft,
  useMoveCriterion,
  usePublishRevision,
  useReorderRubricTree,
  useRetireRevision,
  useRubricRevisions,
  useUpdateCriterion,
  useUpdateDomain,
  useValidateDraft,
} from '../hooks/useRubrics';
import {
  AGENT_LABELS,
  AGENT_ORDER,
  AGENT_STRATEGY_CAPABILITIES,
  type AgentId,
  type RubricCriterion,
  type RubricDomain,
  type RubricSet,
  type StrategyConfig,
  type ValidationReport,
} from '../types';
import { CriterionModal } from './CriterionModal';
import { DomainModal } from './DomainModal';
import { MoveCriterionModal } from './MoveCriterionModal';
import { PublishRevisionModal } from './PublishRevisionModal';
import { RevisionHistoryPanel } from './RevisionHistoryPanel';
import { ValidationReportCard } from './ValidationReportCard';

function formatStrategyBadge(strategyConfig?: StrategyConfig | null): {
  label: string;
  detail: string;
} {
  if (!strategyConfig) {
    return { label: 'Unset', detail: 'No strategy configuration' };
  }

  switch (strategyConfig.strategy) {
    case 'llm_rubric_guidance': {
      const hasDesc = Boolean(strategyConfig.level_descriptors?.length);
      return {
        label: 'LLM Guidance',
        detail: hasDesc ? 'Guidance + 4 score descriptors' : 'Guidance prompt',
      };
    }
    case 'count_band': {
      const mode = strategyConfig.mode === 'minimum_count' ? 'Min Count' : 'Max Count';
      return {
        label: `Count Band (${mode})`,
        detail: `T4:${strategyConfig.threshold_4} T3:${strategyConfig.threshold_3} T2:${strategyConfig.threshold_2}`,
      };
    }
    case 'ratio_band': {
      const mode = strategyConfig.mode === 'coverage_percentage' ? 'Coverage %' : 'Absolute Diff';
      const sample = strategyConfig.short_sample ? ' + Short-sample' : '';
      return {
        label: `Ratio Band (${mode}${sample})`,
        detail: `T4:${strategyConfig.threshold_4} T3:${strategyConfig.threshold_3} T2:${strategyConfig.threshold_2}`,
      };
    }
    case 'curriculum_alignment': {
      return {
        label: 'Curriculum Alignment',
        detail: 'Objective mapping against syllabus roadmap',
      };
    }
    default:
      return { label: 'Unknown', detail: '' };
  }
}

export function RubricTableEditor() {
  const [selectedAgent, setSelectedAgent] = useState<AgentId>('sme');
  const [selectedRevisionId, setSelectedRevisionId] = useState<string | null>(null);
  const [showHistorySidebar, setShowHistorySidebar] = useState<boolean>(false);
  const [validationReport, setValidationReport] = useState<ValidationReport | null>(null);

  // Modals state
  const [domainModal, setDomainModal] = useState<{
    isOpen: boolean;
    domain?: RubricDomain | null;
  }>({ isOpen: false });

  const [criterionModal, setCriterionModal] = useState<{
    isOpen: boolean;
    domainId?: string;
    domainTitle?: string;
    criterion?: RubricCriterion | null;
  }>({ isOpen: false });

  const [moveModal, setMoveModal] = useState<{
    isOpen: boolean;
    criterion: RubricCriterion | null;
    currentDomainId: string;
  }>({ isOpen: false, criterion: null, currentDomainId: '' });

  const [publishModalOpen, setPublishModalOpen] = useState<boolean>(false);

  // Queries & Mutations
  const revisionsQuery = useRubricRevisions();
  const createDraftMutation = useCreateDraft();
  const deleteDraftMutation = useDeleteDraft();
  const validateDraftMutation = useValidateDraft();
  const publishRevisionMutation = usePublishRevision();
  const activateRevisionMutation = useActivateRevision();
  const retireRevisionMutation = useRetireRevision();
  const reorderTreeMutation = useReorderRubricTree();
  const createDomainMutation = useCreateDomain();
  const updateDomainMutation = useUpdateDomain();
  const deleteDomainMutation = useDeleteDomain();
  const createCriterionMutation = useCreateCriterion();
  const updateCriterionMutation = useUpdateCriterion();
  const moveCriterionMutation = useMoveCriterion();
  const deleteCriterionMutation = useDeleteCriterion();

  const allRevisions = useMemo(
    () => revisionsQuery.data?.revisions ?? [],
    [revisionsQuery.data?.revisions],
  );
  const activePointers = useMemo(
    () => revisionsQuery.data?.active_pointers ?? {},
    [revisionsQuery.data?.active_pointers],
  );

  const agentRevisions = useMemo(
    () => allRevisions.filter((r) => r.agent_id === selectedAgent),
    [allRevisions, selectedAgent],
  );

  // Active or draft revision resolution
  const currentRevision = useMemo<RubricSet | null>(() => {
    if (selectedRevisionId) {
      const match = agentRevisions.find((r) => r.rubric_set_id === selectedRevisionId);
      if (match) return match;
    }

    // Default to draft if exists, else active pointer, else newest revision
    const draft = agentRevisions.find((r) => r.status === 'draft');
    if (draft) return draft;

    const activeId = activePointers[selectedAgent];
    if (activeId) {
      const active = agentRevisions.find((r) => r.rubric_set_id === activeId);
      if (active) return active;
    }

    return agentRevisions[0] ?? null;
  }, [agentRevisions, selectedRevisionId, activePointers, selectedAgent]);

  const isDraft = currentRevision?.status === 'draft';
  const isPublished = currentRevision?.status === 'published';
  const isRetired = currentRevision?.status === 'retired';
  const isActive =
    currentRevision &&
    (activePointers[selectedAgent] === currentRevision.rubric_set_id ||
      Boolean(currentRevision.is_active));

  const hasDraftForAgent = agentRevisions.some((r) => r.status === 'draft');
  const agentCaps = AGENT_STRATEABILITY_CAPABILITIES_FALLBACK(selectedAgent);

  function AGENT_STRATEABILITY_CAPABILITIES_FALLBACK(agent: string) {
    return (
      AGENT_STRATEGY_CAPABILITIES[agent] ?? {
        allowedStrategies: ['llm_rubric_guidance'],
        maxCriteria: 20,
        description: '',
      }
    );
  }

  // Atomic domain reorder (Up / Down)
  const handleMoveDomain = (domainIndex: number, direction: 'up' | 'down') => {
    if (!currentRevision || !isDraft) return;
    const targetIndex = direction === 'up' ? domainIndex - 1 : domainIndex + 1;
    if (targetIndex < 0 || targetIndex >= currentRevision.domains.length) return;

    const newDomains = [...currentRevision.domains];
    const temp = newDomains[domainIndex];
    newDomains[domainIndex] = newDomains[targetIndex];
    newDomains[targetIndex] = temp;

    const reorderPayload = {
      domains: newDomains.map((d) => ({
        rubric_domain_id: d.rubric_domain_id,
        criterion_ids: d.criteria.map((c) => c.rubric_criterion_id),
      })),
    };

    reorderTreeMutation.mutate({
      rubricSetId: currentRevision.rubric_set_id,
      body: reorderPayload,
    });
  };

  // Atomic criterion reorder (Up / Down)
  const handleMoveCriterion = (
    domain: RubricDomain,
    criterionIndex: number,
    direction: 'up' | 'down',
  ) => {
    if (!currentRevision || !isDraft) return;
    const targetIndex = direction === 'up' ? criterionIndex - 1 : criterionIndex + 1;
    if (targetIndex < 0 || targetIndex >= domain.criteria.length) return;

    const newCriteria = [...domain.criteria];
    const temp = newCriteria[criterionIndex];
    newCriteria[criterionIndex] = newCriteria[targetIndex];
    newCriteria[targetIndex] = temp;

    const reorderPayload = {
      domains: currentRevision.domains.map((d) => ({
        rubric_domain_id: d.rubric_domain_id,
        criterion_ids:
          d.rubric_domain_id === domain.rubric_domain_id
            ? newCriteria.map((c) => c.rubric_criterion_id)
            : d.criteria.map((c) => c.rubric_criterion_id),
      })),
    };

    reorderTreeMutation.mutate({
      rubricSetId: currentRevision.rubric_set_id,
      body: reorderPayload,
    });
  };

  // Run Draft Validation
  const handleValidateDraft = async () => {
    if (!currentRevision) return;
    try {
      const report = await validateDraftMutation.mutateAsync(currentRevision.rubric_set_id);
      setValidationReport(report);
    } catch (err) {
      const extracted = getValidationReportFromError(err);
      if (extracted) {
        setValidationReport(extracted);
      }
    }
  };

  // Handle Publish
  const handlePublish = async (activate: boolean) => {
    if (!currentRevision) return;
    try {
      const published = await publishRevisionMutation.mutateAsync({
        rubricSetId: currentRevision.rubric_set_id,
        activate,
      });
      setPublishModalOpen(false);
      setValidationReport(null);
      setSelectedRevisionId(published.rubric_set_id);
    } catch {
      // Handled in modal
    }
  };

  // Create Draft
  const handleCreateDraft = async () => {
    try {
      const newDraft = await createDraftMutation.mutateAsync(selectedAgent);
      setSelectedRevisionId(newDraft.rubric_set_id);
      setValidationReport(null);
    } catch {
      // Error handled by alert
    }
  };

  // Delete Draft
  const handleDeleteDraft = async (rubricSetId: string) => {
    if (
      !window.confirm(
        'Are you sure you want to delete this draft revision? This action cannot be undone.',
      )
    ) {
      return;
    }
    try {
      await deleteDraftMutation.mutateAsync(rubricSetId);
      setSelectedRevisionId(null);
      setValidationReport(null);
    } catch {
      // Error handled by alert
    }
  };

  // Activate Revision
  const handleActivateRevision = async (rubricSetId: string) => {
    try {
      await activateRevisionMutation.mutateAsync(rubricSetId);
      setSelectedRevisionId(rubricSetId);
    } catch {
      // Error handled by alert
    }
  };

  // Retire Revision
  const handleRetireRevision = async (rubricSetId: string) => {
    if (
      !window.confirm(
        'Are you sure you want to retire this published revision? Retired revisions cannot be reactivated.',
      )
    ) {
      return;
    }
    try {
      await retireRevisionMutation.mutateAsync(rubricSetId);
      setSelectedRevisionId(rubricSetId);
    } catch {
      // Error handled by alert
    }
  };

  // General mutation error banner
  const generalMutationError =
    createDraftMutation.error ||
    deleteDraftMutation.error ||
    validateDraftMutation.error ||
    publishRevisionMutation.error ||
    activateRevisionMutation.error ||
    retireRevisionMutation.error ||
    reorderTreeMutation.error ||
    deleteDomainMutation.error ||
    deleteCriterionMutation.error;

  if (revisionsQuery.isLoading) {
    return (
      <div
        className="flex items-center justify-center p-12 text-sm font-bold text-text-muted uppercase tracking-wider"
        role="status"
      >
        Loading CID rubric revisions…
      </div>
    );
  }

  if (revisionsQuery.isError) {
    return (
      <div
        role="alert"
        aria-live="assertive"
        className="rounded-sm border border-destructive/30 bg-destructive-soft p-5 text-sm font-bold text-destructive"
      >
        {getRubricOperationError(revisionsQuery.error, 'Failed to load evaluation rubrics.')}
      </div>
    );
  }

  return (
    <section className="grid gap-6">
      {/* Top Navigation: Agent Selector Tabs */}
      <div className="border-b border-border bg-surface">
        <nav className="flex flex-wrap gap-1 px-4 pt-3" aria-label="Evaluation Form Agent Selector">
          {AGENT_ORDER.map((agentId) => {
            const isTabSelected = selectedAgent === agentId;
            const hasDraft = allRevisions.some(
              (r) => r.agent_id === agentId && r.status === 'draft',
            );
            const activeRevId = activePointers[agentId];
            const activeRev = allRevisions.find((r) => r.rubric_set_id === activeRevId);

            return (
              <button
                key={agentId}
                type="button"
                onClick={() => {
                  setSelectedAgent(agentId);
                  setSelectedRevisionId(null);
                  setValidationReport(null);
                }}
                className={`relative flex items-center gap-2 px-4 py-3 text-xs font-bold uppercase tracking-wider transition-colors border-b-2 ${
                  isTabSelected
                    ? 'border-primary text-primary bg-surface-subtle/50'
                    : 'border-transparent text-text-muted hover:text-text hover:border-border'
                }`}
                aria-selected={isTabSelected}
                role="tab"
              >
                <span>{AGENT_LABELS[agentId]}</span>
                {activeRev && (
                  <span className="rounded-sm bg-surface-subtle px-1.5 py-0.5 text-[10px] font-semibold text-text-muted tabular-nums">
                    v{activeRev.version_number}
                  </span>
                )}
                {hasDraft && (
                  <span
                    title="Draft revision available"
                    className="size-2 rounded-full bg-warning"
                    aria-label="Draft exists"
                  />
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Global Error Banner */}
      {generalMutationError && (
        <div
          role="alert"
          aria-live="assertive"
          className="rounded-sm border border-destructive/30 bg-destructive-soft p-4 text-xs font-semibold text-destructive"
        >
          {getRubricOperationError(generalMutationError)}
        </div>
      )}

      {/* Layout Split: Form Editor + Revision History Sidebar */}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,22rem)]">
        {/* Main Editor Section */}
        <div className="grid gap-5">
          {/* Header Card: Selected Revision Status & Action Toolbar */}
          <div className="rounded-sm border border-border bg-surface p-5">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border pb-4">
              <div>
                <div className="flex flex-wrap items-center gap-2.5">
                  <h1 className="text-base font-bold text-text tracking-tight">
                    {AGENT_LABELS[selectedAgent]} Evaluation Form
                  </h1>
                  {currentRevision && (
                    <span className="text-xs font-bold text-text-muted uppercase tracking-wider tabular-nums">
                      · v{currentRevision.version_number}
                    </span>
                  )}
                  {isActive && (
                    <span className="inline-flex items-center gap-1 rounded-sm bg-success-soft px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider text-success border border-success/20">
                      <CheckCircle className="size-3.5" />
                      Active Pointer
                    </span>
                  )}
                  {isDraft && (
                    <span className="inline-flex items-center gap-1 rounded-sm bg-warning-soft px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider text-warning border border-warning/20">
                      Draft (Editable)
                    </span>
                  )}
                  {isPublished && (
                    <span className="inline-flex items-center gap-1 rounded-sm bg-primary-soft px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider text-primary border border-primary/20">
                      <Lock className="size-3" />
                      Published (Immutable)
                    </span>
                  )}
                  {isRetired && (
                    <span className="inline-flex items-center gap-1 rounded-sm bg-surface-subtle px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider text-text-muted border border-border">
                      Retired
                    </span>
                  )}
                </div>

                <p className="mt-1 text-xs text-text-muted font-medium">{agentCaps?.description}</p>
              </div>

              {/* Action Toolbar */}
              <div className="flex flex-wrap items-center gap-2">
                {isDraft ? (
                  <>
                    <button
                      type="button"
                      onClick={handleValidateDraft}
                      disabled={validateDraftMutation.isPending}
                      className="inline-flex h-9 items-center justify-center gap-1.5 rounded-sm border border-border bg-surface px-3 text-xs font-bold uppercase tracking-wider text-text hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                    >
                      <FileCheck className="size-4 text-text-muted" />
                      Validate
                    </button>
                    <button
                      type="button"
                      onClick={() => setPublishModalOpen(true)}
                      className="inline-flex h-9 items-center justify-center gap-1.5 rounded-sm bg-primary px-3.5 text-xs font-bold uppercase tracking-wider text-primary-foreground hover:bg-primary-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      Publish Revision
                    </button>
                    <button
                      type="button"
                      onClick={() => setDomainModal({ isOpen: true })}
                      className="inline-flex h-9 items-center justify-center gap-1.5 rounded-sm border border-primary bg-surface px-3 text-xs font-bold uppercase tracking-wider text-primary hover:bg-primary-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <Plus className="size-4" />
                      Add Domain
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        currentRevision && handleDeleteDraft(currentRevision.rubric_set_id)
                      }
                      disabled={deleteDraftMutation.isPending}
                      className="inline-flex h-9 items-center justify-center gap-1.5 rounded-sm border border-destructive/30 text-destructive hover:bg-destructive-soft px-3 text-xs font-bold uppercase tracking-wider focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive disabled:opacity-50"
                    >
                      <Trash2 className="size-4" />
                      Delete Draft
                    </button>
                  </>
                ) : (
                  <>
                    {!hasDraftForAgent && (
                      <button
                        type="button"
                        onClick={handleCreateDraft}
                        disabled={createDraftMutation.isPending}
                        className="inline-flex h-9 items-center justify-center gap-1.5 rounded-sm bg-primary px-3.5 text-xs font-bold uppercase tracking-wider text-primary-foreground hover:bg-primary-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                      >
                        <Plus className="size-4" />
                        Create Editable Draft
                      </button>
                    )}
                    {isPublished && !isActive && (
                      <>
                        <button
                          type="button"
                          onClick={() =>
                            currentRevision && handleActivateRevision(currentRevision.rubric_set_id)
                          }
                          disabled={activateRevisionMutation.isPending}
                          className="inline-flex h-9 items-center justify-center gap-1.5 rounded-sm bg-success px-3 text-xs font-bold uppercase tracking-wider text-white hover:bg-success/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-success disabled:opacity-50"
                        >
                          <Check className="size-4" />
                          Activate (Rollback)
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            currentRevision && handleRetireRevision(currentRevision.rubric_set_id)
                          }
                          disabled={retireRevisionMutation.isPending}
                          className="inline-flex h-9 items-center justify-center gap-1.5 rounded-sm border border-border bg-surface px-3 text-xs font-bold uppercase tracking-wider text-text hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                        >
                          Retire
                        </button>
                      </>
                    )}
                  </>
                )}

                <button
                  type="button"
                  onClick={() => setShowHistorySidebar((prev) => !prev)}
                  className="lg:hidden inline-flex h-9 items-center justify-center gap-1.5 rounded-sm border border-border bg-surface px-3 text-xs font-bold uppercase tracking-wider text-text hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <History className="size-4" />
                  History
                </button>
              </div>
            </div>

            {/* Immutability / Notice Banner */}
            {!isDraft && currentRevision && (
              <div className="mt-4 flex items-start gap-2.5 rounded-sm border border-border bg-surface-subtle p-3 text-xs text-text">
                <Lock className="size-4 shrink-0 text-text-muted mt-0.5" />
                <div>
                  <span className="font-bold text-text">
                    {isPublished
                      ? 'Published Revision (Read-Only)'
                      : 'Retired Revision (Historical Reference)'}
                  </span>
                  <p className="mt-0.5 text-text-muted">
                    {isPublished
                      ? 'Published form revisions cannot be directly modified. Create a new draft to add, edit, delete, or reorder criteria.'
                      : 'Retired revisions remain in database history for audit purposes and cannot be reactivated.'}
                  </p>
                </div>
              </div>
            )}

            {/* Validation Report Card */}
            {validationReport && (
              <div className="mt-4">
                <ValidationReportCard
                  report={validationReport}
                  onDismiss={() => setValidationReport(null)}
                />
              </div>
            )}
          </div>

          {/* Form Ledger Domains and Criteria */}
          {currentRevision ? (
            <div className="grid gap-5">
              {currentRevision.domains.map((domain, domainIndex) => {
                const isFirstDomain = domainIndex === 0;
                const isLastDomain = domainIndex === currentRevision.domains.length - 1;

                return (
                  <section
                    key={domain.rubric_domain_id}
                    className="rounded-sm border border-border bg-surface p-5 shadow-2xs"
                    aria-label={`Domain ${domain.code}: ${domain.title}`}
                  >
                    {/* Domain Header */}
                    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="rounded-sm bg-primary px-2.5 py-1 text-xs font-bold text-primary-foreground uppercase tracking-wider">
                          {domain.code}
                        </span>
                        <h2 className="text-sm font-bold text-text tracking-tight">
                          {domain.title}
                        </h2>
                        <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider tabular-nums">
                          ({domain.criteria.length} criteria)
                        </span>
                      </div>

                      {/* Domain Action Buttons */}
                      {isDraft && (
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => handleMoveDomain(domainIndex, 'up')}
                            disabled={isFirstDomain || reorderTreeMutation.isPending}
                            className="inline-flex size-8 items-center justify-center rounded-sm border border-border text-text-muted hover:bg-surface-subtle hover:text-text focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-30 disabled:cursor-not-allowed"
                            aria-label={`Move ${domain.code} domain up`}
                            title="Move Domain Up"
                          >
                            <ArrowUp className="size-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleMoveDomain(domainIndex, 'down')}
                            disabled={isLastDomain || reorderTreeMutation.isPending}
                            className="inline-flex size-8 items-center justify-center rounded-sm border border-border text-text-muted hover:bg-surface-subtle hover:text-text focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-30 disabled:cursor-not-allowed"
                            aria-label={`Move ${domain.code} domain down`}
                            title="Move Domain Down"
                          >
                            <ArrowDown className="size-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => setDomainModal({ isOpen: true, domain })}
                            className="inline-flex size-8 items-center justify-center rounded-sm border border-border text-text-muted hover:bg-surface-subtle hover:text-text focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                            aria-label={`Edit ${domain.code} domain`}
                            title="Edit Domain"
                          >
                            <Pencil className="size-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              if (
                                window.confirm(
                                  `Delete domain "${domain.title}" and its ${domain.criteria.length} criteria?`,
                                )
                              ) {
                                deleteDomainMutation.mutate(domain.rubric_domain_id);
                              }
                            }}
                            className="inline-flex size-8 items-center justify-center rounded-sm border border-transparent text-destructive hover:bg-destructive-soft focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-destructive"
                            aria-label={`Delete ${domain.code} domain`}
                            title="Delete Domain"
                          >
                            <Trash2 className="size-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              setCriterionModal({
                                isOpen: true,
                                domainId: domain.rubric_domain_id,
                                domainTitle: domain.title,
                              })
                            }
                            className="ml-2 inline-flex h-8 items-center justify-center gap-1 rounded-sm bg-primary px-2.5 text-[11px] font-bold uppercase tracking-wider text-primary-foreground hover:bg-primary-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          >
                            <Plus className="size-3.5" />
                            Add Criterion
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Criteria Table */}
                    <div className="mt-3 overflow-x-auto rounded-sm border border-border">
                      <table className="w-full text-left border-collapse border-spacing-0">
                        <thead className="bg-surface-subtle text-[11px] uppercase tracking-wider font-bold text-text-muted border-b border-border">
                          <tr>
                            {isDraft && <th className="py-2.5 px-3 w-16 text-center">Order</th>}
                            <th className="py-2.5 px-3 w-28">Criterion ID</th>
                            <th className="py-2.5 px-4 min-w-[14rem]">Entry</th>
                            <th className="py-2.5 px-4 min-w-[12rem]">Strategy / Config</th>
                            <th className="py-2.5 px-4 min-w-[12rem]">Scoring rule</th>
                            {isDraft && <th className="py-2.5 px-3 w-28 text-right">Actions</th>}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border text-xs">
                          {domain.criteria.map((criterion, critIndex) => {
                            const isFirstCrit = critIndex === 0;
                            const isLastCrit = critIndex === domain.criteria.length - 1;
                            const strategyBadge = formatStrategyBadge(criterion.strategy_config);

                            return (
                              <tr
                                key={criterion.rubric_criterion_id}
                                className="hover:bg-surface-subtle/50 transition-colors"
                              >
                                {/* Order Controls */}
                                {isDraft && (
                                  <td className="py-2.5 px-3 text-center align-top">
                                    <div className="flex items-center justify-center gap-0.5">
                                      <button
                                        type="button"
                                        onClick={() => handleMoveCriterion(domain, critIndex, 'up')}
                                        disabled={isFirstCrit || reorderTreeMutation.isPending}
                                        className="inline-flex size-6 items-center justify-center rounded-sm text-text-muted hover:bg-surface-subtle hover:text-text disabled:opacity-20 disabled:cursor-not-allowed"
                                        aria-label={`Move ${criterion.criterion_code} criterion up`}
                                        title="Move Up"
                                      >
                                        <ArrowUp className="size-3" />
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() =>
                                          handleMoveCriterion(domain, critIndex, 'down')
                                        }
                                        disabled={isLastCrit || reorderTreeMutation.isPending}
                                        className="inline-flex size-6 items-center justify-center rounded-sm text-text-muted hover:bg-surface-subtle hover:text-text disabled:opacity-20 disabled:cursor-not-allowed"
                                        aria-label={`Move ${criterion.criterion_code} criterion down`}
                                        title="Move Down"
                                      >
                                        <ArrowDown className="size-3" />
                                      </button>
                                    </div>
                                  </td>
                                )}

                                {/* Code */}
                                <td className="py-2.5 px-3 align-top">
                                  <input
                                    type="text"
                                    value={criterion.criterion_code}
                                    readOnly
                                    className="w-full border border-transparent bg-transparent rounded-sm text-xs font-bold text-text"
                                    aria-label={`${domain.code} criterion ID`}
                                  />
                                </td>

                                {/* Entry (Title & Description) */}
                                <td className="py-2.5 px-4 align-top">
                                  <p className="font-bold text-text">{criterion.title}</p>
                                  <p className="mt-1 text-text-muted whitespace-pre-wrap leading-relaxed">
                                    {criterion.description}
                                  </p>
                                </td>
                                {/* Strategy & Config */}
                                <td className="py-2.5 px-4 align-top">
                                  <div className="grid gap-1">
                                    <span className="w-fit rounded-sm bg-primary-soft border border-primary/20 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-primary">
                                      {strategyBadge.label}
                                    </span>
                                    <span className="text-[11px] text-text-muted font-mono tabular-nums">
                                      {strategyBadge.detail}
                                    </span>
                                  </div>
                                </td>

                                {/* Scoring Rule */}
                                <td className="py-2.5 px-4 align-top">
                                  {criterion.scoring_rule ? (
                                    <p className="text-text whitespace-pre-wrap leading-relaxed">
                                      {criterion.scoring_rule}
                                    </p>
                                  ) : (
                                    <span className="text-text-muted italic">No rule summary</span>
                                  )}
                                </td>

                                {/* Draft Actions */}
                                {isDraft && (
                                  <td className="py-2.5 px-3 text-right align-top">
                                    <div className="flex items-center justify-end gap-1">
                                      <button
                                        type="button"
                                        onClick={() =>
                                          setCriterionModal({
                                            isOpen: true,
                                            domainId: domain.rubric_domain_id,
                                            domainTitle: domain.title,
                                            criterion,
                                          })
                                        }
                                        className="inline-flex size-7 items-center justify-center rounded-sm text-text-muted hover:bg-surface-subtle hover:text-text focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                        aria-label={`Edit ${criterion.criterion_code} row`}
                                        title="Edit Criterion"
                                      >
                                        <Pencil className="size-3.5" />
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() =>
                                          setMoveModal({
                                            isOpen: true,
                                            criterion,
                                            currentDomainId: domain.rubric_domain_id,
                                          })
                                        }
                                        className="inline-flex size-7 items-center justify-center rounded-sm text-text-muted hover:bg-surface-subtle hover:text-text focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                        aria-label={`Move ${criterion.criterion_code} to another domain`}
                                        title="Move Criterion"
                                      >
                                        <ArrowRightLeft className="size-3.5" />
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() => {
                                          if (
                                            window.confirm(
                                              `Delete criterion ${criterion.criterion_code}?`,
                                            )
                                          ) {
                                            deleteCriterionMutation.mutate(
                                              criterion.rubric_criterion_id,
                                            );
                                          }
                                        }}
                                        className="inline-flex size-7 items-center justify-center rounded-sm text-destructive hover:bg-destructive-soft focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-destructive"
                                        aria-label={`Delete ${criterion.criterion_code} row`}
                                        title="Delete Criterion"
                                      >
                                        <Trash2 className="size-3.5" />
                                      </button>
                                    </div>
                                  </td>
                                )}
                              </tr>
                            );
                          })}

                          {domain.criteria.length === 0 && (
                            <tr>
                              <td
                                colSpan={isDraft ? 6 : 4}
                                className="py-6 text-center text-xs font-semibold text-text-muted uppercase tracking-wider bg-surface-subtle/20"
                              >
                                No criteria in this domain. Click &quot;Add Criterion&quot; to
                                create one.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </section>
                );
              })}

              {currentRevision.domains.length === 0 && (
                <div className="rounded-sm border border-border bg-surface p-8 text-center">
                  <p className="text-sm font-bold text-text">No domains in this form.</p>
                  {isDraft && (
                    <button
                      type="button"
                      onClick={() => setDomainModal({ isOpen: true })}
                      className="mt-3 inline-flex h-9 items-center justify-center gap-1.5 rounded-sm bg-primary px-4 text-xs font-bold uppercase tracking-wider text-primary-foreground hover:bg-primary-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <Plus className="size-4" />
                      Add First Domain
                    </button>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-sm border border-border bg-surface p-8 text-center">
              <p className="text-sm font-bold text-text">
                No active or draft form found for {AGENT_LABELS[selectedAgent]}.
              </p>
              <button
                type="button"
                onClick={handleCreateDraft}
                className="mt-3 inline-flex h-9 items-center justify-center gap-1.5 rounded-sm bg-primary px-4 text-xs font-bold uppercase tracking-wider text-primary-foreground hover:bg-primary-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Plus className="size-4" />
                Create New Form Draft
              </button>
            </div>
          )}
        </div>

        {/* Right Sidebar: Revision History */}
        <div className={`grid gap-4 ${showHistorySidebar ? 'block' : 'hidden lg:block'}`}>
          <RevisionHistoryPanel
            agentId={selectedAgent}
            agentLabel={AGENT_LABELS[selectedAgent]}
            revisions={agentRevisions}
            activePointerId={activePointers[selectedAgent]}
            selectedRevisionId={currentRevision?.rubric_set_id}
            onSelectRevision={(revId) => {
              setSelectedRevisionId(revId);
              setValidationReport(null);
            }}
            onCreateDraft={handleCreateDraft}
            onDeleteDraft={handleDeleteDraft}
            onActivateRevision={handleActivateRevision}
            onRetireRevision={handleRetireRevision}
            isActionPending={
              createDraftMutation.isPending ||
              deleteDraftMutation.isPending ||
              activateRevisionMutation.isPending ||
              retireRevisionMutation.isPending
            }
          />
        </div>
      </div>

      {/* Domain Modal */}
      {currentRevision && (
        <DomainModal
          isOpen={domainModal.isOpen}
          domain={domainModal.domain}
          onClose={() => setDomainModal({ isOpen: false })}
          isPending={createDomainMutation.isPending || updateDomainMutation.isPending}
          error={createDomainMutation.error || updateDomainMutation.error}
          onSave={async ({ code, title }) => {
            if (domainModal.domain) {
              await updateDomainMutation.mutateAsync({
                domainId: domainModal.domain.rubric_domain_id,
                body: { code, title },
              });
            } else {
              await createDomainMutation.mutateAsync({
                rubricSetId: currentRevision.rubric_set_id,
                body: { code, title },
              });
            }
            setDomainModal({ isOpen: false });
          }}
        />
      )}

      {/* Criterion Modal */}
      {currentRevision && (
        <CriterionModal
          isOpen={criterionModal.isOpen}
          agentId={selectedAgent}
          domainTitle={criterionModal.domainTitle ?? ''}
          criterion={criterionModal.criterion}
          onClose={() => setCriterionModal({ isOpen: false })}
          isPending={createCriterionMutation.isPending || updateCriterionMutation.isPending}
          error={createCriterionMutation.error || updateCriterionMutation.error}
          onSave={async (data) => {
            if (criterionModal.criterion) {
              await updateCriterionMutation.mutateAsync({
                criterionId: criterionModal.criterion.rubric_criterion_id,
                body: data,
              });
            } else if (criterionModal.domainId) {
              await createCriterionMutation.mutateAsync({
                domainId: criterionModal.domainId,
                body: data,
              });
            }
            setCriterionModal({ isOpen: false });
          }}
        />
      )}

      {/* Move Criterion Modal */}
      {currentRevision && (
        <MoveCriterionModal
          isOpen={moveModal.isOpen}
          criterion={moveModal.criterion}
          currentDomainId={moveModal.currentDomainId}
          availableDomains={currentRevision.domains}
          onClose={() => setMoveModal({ isOpen: false, criterion: null, currentDomainId: '' })}
          isPending={moveCriterionMutation.isPending}
          error={moveCriterionMutation.error}
          onMove={async (destinationDomainId) => {
            if (!moveModal.criterion) return;
            await moveCriterionMutation.mutateAsync({
              criterionId: moveModal.criterion.rubric_criterion_id,
              body: { destination_domain_id: destinationDomainId },
            });
            setMoveModal({ isOpen: false, criterion: null, currentDomainId: '' });
          }}
        />
      )}

      {/* Publish Revision Modal */}
      {currentRevision && (
        <PublishRevisionModal
          isOpen={publishModalOpen}
          versionNumber={currentRevision.version_number}
          agentLabel={AGENT_LABELS[selectedAgent]}
          onClose={() => setPublishModalOpen(false)}
          onPublish={handlePublish}
          isPending={publishRevisionMutation.isPending}
          error={publishRevisionMutation.error}
        />
      )}
    </section>
  );
}
