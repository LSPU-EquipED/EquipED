import { PageContainer } from '@equiped/ui';
import { IngestionPipelineMonitor } from '../components/IngestionPipelineMonitor';
import { IngestionVerificationCard } from '../components/IngestionVerificationCard';
import { ReferenceClassificationStep } from '../components/ReferenceClassificationStep';
import { ReferenceFileDropzoneStep } from '../components/ReferenceFileDropzoneStep';
import { useAdminUploadFlow } from '../hooks/useAdminUploadFlow';

export function AdminUploadPage() {
  const uploadFlow = useAdminUploadFlow();

  return (
    <PageContainer as="section" className="space-y-6">
      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <form onSubmit={uploadFlow.handleSubmit} className="min-w-0 rounded-md border border-border bg-surface">
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

        <div className="space-y-4 lg:sticky lg:top-6">
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
    </PageContainer>
  );
}
