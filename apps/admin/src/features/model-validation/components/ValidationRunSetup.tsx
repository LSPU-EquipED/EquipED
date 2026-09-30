import { UploadSimple } from '@phosphor-icons/react';
import { Dropdown, ProgramSelector } from '@equiped/ui';
import { LSPU_SCC_COLLEGE_PROGRAMS } from '@equiped/types';
import type { TargetAgent } from '../types';
import type { ModelValidationFormState } from '../hooks/useModelValidationFormState';

export function ValidationRunSetup({
  form,
}: {
  form: Pick<
    ModelValidationFormState,
    | 'fileInputRef'
    | 'file'
    | 'title'
    | 'setTitle'
    | 'program'
    | 'uploaded'
    | 'modelChoice'
    | 'setModelChoice'
    | 'adapterOptions'
    | 'adapterChoices'
    | 'targetAgent'
    | 'setTargetAgent'
    | 'handleFile'
    | 'handleProgramChange'
  >;
}) {
  const {
    fileInputRef,
    file,
    title,
    setTitle,
    program,
    uploaded,
    modelChoice,
    setModelChoice,
    adapterOptions,
    adapterChoices,
    targetAgent,
    setTargetAgent,
    handleFile,
    handleProgramChange,
  } = form;

  const adapters = adapterChoices.data?.adapters ?? [];
  const chosen =
    modelChoice === 'base'
      ? null
      : modelChoice === 'published'
        ? (adapters.find((a) => a.published) ?? null)
        : (adapters.find((a) => a.adapter_id === modelChoice) ?? null);
  const notLoadedFilename = chosen && chosen.loaded !== true ? chosen.gguf_filename : null;

  return (
    <>
      {/* Run configuration: which model, and which agent(s) to benchmark */}
      <section className="space-y-4 bg-surface p-5">
        <div>
          <p className="text-xs font-semibold text-primary">1. Define the run</p>
          <h3 className="mt-1 text-base font-semibold text-text">Run configuration</h3>
          <p className="mt-1 text-xs leading-relaxed text-text-muted">
            Choose the evaluator agent, then the base model or one of its adapter versions.
          </p>
        </div>

        <div className="grid gap-3.5 sm:grid-cols-2">
          <Dropdown
            id="validation-target"
            label="Target"
            value={targetAgent ?? ''}
            onChange={(value) => setTargetAgent(value as TargetAgent)}
            options={[
              { value: 'sme', label: 'SME only' },
              { value: 'gad', label: 'GAD only' },
              { value: 'itso', label: 'ITSO only' },
            ]}
            placeholder="Choose an agent"
            size="md"
            className="w-full"
          />
          <Dropdown
            id="validation-model"
            label="Model"
            value={targetAgent ? modelChoice : ''}
            onChange={(value) => setModelChoice(value)}
            options={targetAgent ? adapterOptions : []}
            placeholder={targetAgent ? 'Choose a model' : 'Choose an agent first'}
            disabled={!targetAgent}
            size="md"
            className="w-full"
          />
        </div>

        {notLoadedFilename ? (
          <p className="text-xs text-text-muted">
            This version is not loaded on the server. Ask the host owner to load{' '}
            <code className="font-mono">{notLoadedFilename}</code>.
          </p>
        ) : null}
      </section>

      {/* Document attachment */}
      <section className="space-y-4 bg-surface p-5">
        <div>
          <p className="text-xs font-semibold text-primary">2. Attach the SLM</p>
          <h3 className="mt-1 text-base font-semibold text-text">Document details</h3>
          <p className="mt-1 text-xs leading-relaxed text-text-muted">
            This document is evaluated directly and is never added to vector storage.
          </p>
        </div>

        <div className="space-y-3.5">
          <div className="space-y-1.5">
            <label htmlFor="validation-title" className="text-xs font-semibold text-text">
              SLM title <span className="text-destructive">*</span>
            </label>
            <input
              id="validation-title"
              className="h-10 w-full rounded-sm border border-input bg-surface px-3 text-sm font-semibold text-text placeholder:text-text-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="e.g. CS101 Algorithms Benchmark SLM"
              required
              disabled={!!uploaded}
            />
          </div>

          <ProgramSelector
            id="validation-program"
            label="Confirmed program"
            value={program}
            onChange={handleProgramChange}
            groups={LSPU_SCC_COLLEGE_PROGRAMS}
            placeholder="Select the SLM program (BSCS or BSInfoTech)"
            required
            hint="Recorded as the confirmed program for this validation."
          />

          {/* PDF Dropzone */}
          <div className="pt-1">
            <label className="flex min-h-24 cursor-pointer flex-col items-center justify-center gap-1.5 rounded-sm border border-dashed border-border bg-surface-subtle/50 px-4 py-4 text-center hover:bg-surface-subtle hover:border-border-strong transition-colors focus-within:ring-2 focus-within:ring-ring">
              <UploadSimple className="size-5 text-primary" aria-hidden="true" />
              <span className="text-xs font-semibold text-text truncate max-w-full">
                {file ? file.name : 'Choose an SLM PDF document'}
              </span>
              <span className="text-[10px] text-text-muted">PDF input for this run</span>
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf"
                className="sr-only"
                onChange={handleFile}
                disabled={!!uploaded}
                required={!uploaded}
              />
            </label>
          </div>
        </div>
      </section>
    </>
  );
}
