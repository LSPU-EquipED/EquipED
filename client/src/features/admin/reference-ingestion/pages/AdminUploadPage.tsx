import { Link } from '@tanstack/react-router';
import { ArrowLeft } from '@phosphor-icons/react';
import { cn } from '@/shared/components/utils';
import { BUTTON_STYLES } from '@/shared/constants/theme';
import { IngestionPipelineMonitor } from '../components/IngestionPipelineMonitor';
import { IngestionVerificationCard } from '../components/IngestionVerificationCard';
import { ReferenceClassificationStep } from '../components/ReferenceClassificationStep';
import { ReferenceFileDropzoneStep } from '../components/ReferenceFileDropzoneStep';
import { useAdminUploadFlow } from '../hooks/useAdminUploadFlow';

export function AdminUploadPage() {
  const uploadFlow = useAdminUploadFlow();

  return (
    <section className="px-4 sm:px-6 py-6 max-w-[108rem] mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded-sm border border-primary/20 bg-primary-soft px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-primary">
              Official Reference Intake
            </span>
            <span className="text-xs text-text-muted">·</span>
            <span className="text-xs text-text-muted font-medium">Laguna State Polytechnic University</span>
          </div>
          <h1 className="text-lg sm:text-xl font-bold text-text tracking-tight">
            Reference Document Ingestion Workbench
          </h1>
          <p className="text-xs text-text-muted max-w-2xl leading-relaxed">
            Ingest institutional syllabi, degree curriculum roadmaps, and university policy manuals into the local semantic vector store to support automated multi-agent evaluations.
          </p>
        </div>

        <Link
          to="/admin/references"
          className={cn(
            BUTTON_STYLES.base,
            BUTTON_STYLES.variants.secondary,
            BUTTON_STYLES.sizes.md,
            'text-xs sm:text-sm font-semibold h-10 px-4 shrink-0',
          )}
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          <span>Back to Reference Library</span>
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        <form onSubmit={uploadFlow.handleSubmit} className="lg:col-span-7 space-y-6">
          <ReferenceClassificationStep
            sourceType={uploadFlow.sourceType}
            onSourceTypeChange={uploadFlow.handleSourceTypeChange}
            program={uploadFlow.program}
            onProgramChange={uploadFlow.handleProgramChange}
            isProgramInvalid={uploadFlow.isProgramInvalid}
            policyArea={uploadFlow.policyArea}
            onPolicyAreaChange={uploadFlow.setPolicyArea}
          />

          <ReferenceFileDropzoneStep
            title={uploadFlow.title}
            onTitleChange={uploadFlow.setTitle}
            file={uploadFlow.file}
            fileInputRef={uploadFlow.fileInputRef}
            isDragging={uploadFlow.isDragging}
            onDragOver={uploadFlow.handleDragOver}
            onDragLeave={uploadFlow.handleDragLeave}
            onDrop={uploadFlow.handleDrop}
            onFileChange={uploadFlow.handleFileChange}
            fileValidationError={uploadFlow.fileValidationError}
            isLoading={uploadFlow.isLoading}
            canSubmit={uploadFlow.canSubmit}
            onReset={uploadFlow.handleReset}
            showReset={!!(uploadFlow.file || uploadFlow.title || uploadFlow.uploadResult)}
          />
        </form>

        <div className="lg:col-span-5 space-y-5">
          <IngestionVerificationCard
            file={uploadFlow.file}
            sourceType={uploadFlow.sourceType}
            title={uploadFlow.title}
            isCurriculum={uploadFlow.isCurriculum}
            program={uploadFlow.program}
            isPolicyAreaRequired={uploadFlow.isPolicyAreaRequired}
          />

          <IngestionPipelineMonitor
            errorMessage={uploadFlow.errorMessage}
            uploadResult={uploadFlow.uploadResult}
            onReset={uploadFlow.handleReset}
          />
        </div>
      </div>
    </section>
  );
}
