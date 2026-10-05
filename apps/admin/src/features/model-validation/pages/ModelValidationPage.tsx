import { useRef, useState, type KeyboardEvent } from 'react';
import { cn, PageContainer } from '@equiped/ui';
import { AgentProgressPanel } from '../components/AgentProgressPanel';
import { ValidationHistoryTable } from '../components/ValidationHistoryTable';
import { ValidationPerformanceMetrics } from '../components/ValidationPerformanceMetrics';
import { ValidationPreparationForm } from '../components/ValidationPreparationForm';
import { useModelValidationFormState } from '../hooks/useModelValidationFormState';
import {
  useModelValidationHistory,
  useModelValidationMetrics,
} from '../hooks/useModelValidationQueries';
import { terminalStatuses } from '../utils/helpers';

export type ValidationTab = 'history' | 'analytics' | 'new-run';

const workspaceOptions = [
  { value: 'history' as const, label: 'History' },
  { value: 'analytics' as const, label: 'Analytics' },
  { value: 'new-run' as const, label: 'New benchmark' },
];

export function ModelValidationPage() {
  const [activeTab, setActiveTab] = useState<ValidationTab>('history');
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const history = useModelValidationHistory();
  const activeValidations =
    history.data?.items.filter((item) => !terminalStatuses.has(item.status)) ?? [];
  const metricSummary = useModelValidationMetrics(activeValidations.length > 0);
  const formState = useModelValidationFormState();

  function handleTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let nextIndex: number;
    switch (event.key) {
      case 'ArrowRight':
        nextIndex = (index + 1) % workspaceOptions.length;
        break;
      case 'ArrowLeft':
        nextIndex = (index - 1 + workspaceOptions.length) % workspaceOptions.length;
        break;
      case 'Home':
        nextIndex = 0;
        break;
      case 'End':
        nextIndex = workspaceOptions.length - 1;
        break;
      default:
        return;
    }
    event.preventDefault();
    setActiveTab(workspaceOptions[nextIndex].value);
    tabRefs.current[nextIndex]?.focus();
  }

  return (
    <PageContainer as="section" className="!space-y-4 !py-4 sm:!py-5">
      <div
        role="tablist"
        aria-label="Validation workspace"
        className="grid grid-cols-3 border-b border-border"
      >
        {workspaceOptions.map(({ value, label }, index) => (
          <button
            key={value}
            ref={(element) => {
              tabRefs.current[index] = element;
            }}
            type="button"
            role="tab"
            id={`validation-tab-${value}`}
            aria-controls={`validation-panel-${value}`}
            aria-selected={activeTab === value}
            tabIndex={activeTab === value ? 0 : -1}
            onClick={() => setActiveTab(value)}
            onKeyDown={(event) => handleTabKeyDown(event, index)}
            className={cn(
              '-mb-px min-h-10 min-w-0 cursor-pointer border-b-2 px-2 py-2 text-sm font-semibold transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring motion-reduce:transition-none sm:px-6',
              activeTab === value
                ? 'border-primary bg-primary-soft text-primary'
                : 'border-transparent text-text-muted hover:bg-surface-subtle hover:text-text',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {activeTab === 'history' ? (
        <div
          id="validation-panel-history"
          role="tabpanel"
          aria-labelledby="validation-tab-history"
          tabIndex={0}
        >
          <div className="space-y-5">
            {activeValidations.map((validation) => (
              <AgentProgressPanel key={validation.validation_id} validation={validation} />
            ))}

            <ValidationHistoryTable
              history={history}
              onRerun={async (item) => {
                await formState.preloadFromRun(item);
                setActiveTab('new-run');
              }}
            />
          </div>
        </div>
      ) : null}

      {activeTab === 'analytics' ? (
        <div
          id="validation-panel-analytics"
          role="tabpanel"
          aria-labelledby="validation-tab-analytics"
          tabIndex={0}
        >
          <ValidationPerformanceMetrics metricSummary={metricSummary} />
        </div>
      ) : null}

      {activeTab === 'new-run' ? (
        <div
          id="validation-panel-new-run"
          role="tabpanel"
          aria-labelledby="validation-tab-new-run"
          tabIndex={0}
        >
          <div className="space-y-5">
            {activeValidations.map((validation) => (
              <AgentProgressPanel key={validation.validation_id} validation={validation} compact />
            ))}

            <ValidationPreparationForm form={formState} />
          </div>
        </div>
      ) : null}
    </PageContainer>
  );
}
